#!/usr/bin/env python3
"""Full metric comparison between Dataset/clean_bonafide/ (real audio)
and one of its synthesized/cloned versions in Dataset/clean_synthesize/
-- i.e. "does cloning this system produced still pass as the real
speaker." Parametrized by system name so it's reusable across
SV2TTS/F5-TTS/Seed-VC/etc without rewriting.

For every synthesized clip that exists for the given system, scores it
against its own real source clip (genuine, label=1) and a sample of
real clips from other speakers (impostor, label=0) with all 3 judges,
using the same trial-construction approach as
verify/clean_synthesize_metrics.py. Computes every metric this project
has built: EER (+95% CI), TAR@1%/0.1%/0.01%FAR (+95% CI on TAR@1%),
minDCF, d-prime, overlap coefficient, full ROC-AUC, partial AUC at
1%/0.1%FAR, target/impostor score summary stats. Also produces ROC
(with bootstrap bands), DET, and score-distribution plots.

Also breaks the same trials down by descent x gender (FakeAVCeleb-
sourced clips only -- the only entries in clean_bonafide with that
metadata) into a separate EER/TAR@1% table and bar chart, supplementary
to the overall pooled table/plots above.

Output, all under results/cleanbonafidevscleansynth/<SystemName>/:
  csvs/<SystemName>__<SystemName>__<Model>.csv   raw score,label,group rows
  results_table.csv                               the overall metrics table
  results_table_by_group.csv                      EER/TAR@1% by descent x gender
  plots/roc.png, plots/det.png, plots/dist.png
  plots/eer_by_group.png

Run:
    conda run -n antifake2026 python analysis/clean_bonafide_vs_synth.py --system sv2tts
"""
import argparse
import csv
import glob
import json
import os
import random
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.metrics import roc_curve

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from verify import verify_speechbrain, verify_resemblyzer, verify_wavlm
from analysis.metrics import (
    min_dcf, d_prime, overlap_coefficient, full_roc_auc, partial_auc, bootstrap_ci,
    stoi_score, pesq_score, si_sdr,
)
from analysis.results_table import compute_eer, tar_at_far
from analysis import robust_stats as rs

QUALITY_SCORE_SR = 16000  # clean_bonafide's native rate; PESQ only supports 8k/16k

VERIFIERS = {
    "SpeechBrain": verify_speechbrain,
    "Resemblyzer": verify_resemblyzer,
    "WavLM": verify_wavlm,
}
MODEL_DISPLAY_NAMES = {"SpeechBrain": "SB-ECAPA", "Resemblyzer": "Resemblyzer", "WavLM": "WavLM"}

MANIFEST_PATH = os.path.join(config.RAW_DIR, "clean_bonafide", "manifest.json")
IMPOSTORS_PER_CLIP = 10
SEED = 11
SYSTEM_DIRS = {
    "sv2tts": config.CLEAN_SYNTHESIZE_SV2TTS_DIR,
    "f5tts": config.CLEAN_SYNTHESIZE_F5TTS_DIR,
    "seedvc": config.CLEAN_SYNTHESIZE_SEEDVC_DIR,
    # Cloaking methods: same trial construction applies unchanged --
    # each cloaked clip is compared against its own real source clip
    # (genuine) and other speakers' real clips (impostor), exactly like
    # the TTS systems above.
    "POP": os.path.join(config.RAW_DIR, "cloaked_bonafide", "POP"),
    "protectyouraudio": os.path.join(config.RAW_DIR, "cloaked_bonafide", "ProtectYourAudio"),
    "attackvc": os.path.join(config.RAW_DIR, "cloaked_bonafide", "attackvc"),
    "antifake": os.path.join(config.RAW_DIR, "cloaked_bonafide", "Antifake"),
    # Protective-efficacy step: these clone POP-*cloaked* audio (not the
    # clean original) with the same TTS/VC systems above, so scoring
    # them here against clean_bonafide (via the same by_stem/entry["file"]
    # lookup as every other system) measures whether POP's perturbation
    # degrades what a downstream cloning attacker actually extracts --
    # unlike tab:results/tab:ablation (POP-cloaked vs. its own genuine
    # source, which measures imperceptibility, not this).
    "pop_sv2tts": config.CLOAKED_SYNTHESIZE_POP_SV2TTS_DIR,
    "pop_f5tts": config.CLOAKED_SYNTHESIZE_POP_F5TTS_DIR,
    "pop_seedvc": config.CLOAKED_SYNTHESIZE_POP_SEEDVC_DIR,
    # Same protective-efficacy step, for attack-vc's cloaked output.
    "attackvc_sv2tts": config.CLOAKED_SYNTHESIZE_ATTACKVC_SV2TTS_DIR,
    "attackvc_seedvc": config.CLOAKED_SYNTHESIZE_ATTACKVC_SEEDVC_DIR,
    "attackvc_f5tts": config.CLOAKED_SYNTHESIZE_ATTACKVC_F5TTS_DIR,
    # Same protective-efficacy step, for AntiFake's cloaked output.
    "antifake_sv2tts": config.CLOAKED_SYNTHESIZE_ANTIFAKE_SV2TTS_DIR,
    "antifake_seedvc": config.CLOAKED_SYNTHESIZE_ANTIFAKE_SEEDVC_DIR,
    "antifake_f5tts": config.CLOAKED_SYNTHESIZE_ANTIFAKE_F5TTS_DIR,
    # Same protective-efficacy step, for ProtectYourAudio's cloaked output.
    "protectyouraudio_sv2tts": config.CLOAKED_SYNTHESIZE_PROTECTYOURAUDIO_SV2TTS_DIR,
    "protectyouraudio_seedvc": config.CLOAKED_SYNTHESIZE_PROTECTYOURAUDIO_SEEDVC_DIR,
    "protectyouraudio_f5tts": config.CLOAKED_SYNTHESIZE_PROTECTYOURAUDIO_F5TTS_DIR,
}

# The "Data" column prefix each system_name gets in results_table.csv /
# results_table_by_group.csv, chosen per what's actually being compared
# -- NOT one constant string for every system_name (a bug this replaces:
# sv2tts/f5tts/seedvc really are clean_bonafide-vs-clean_synthesize, but
# POP/protectyouraudio/attackvc/antifake are clean_bonafide-vs-cloaked
# audio directly (no synthesis at all), and pop_sv2tts/pop_f5tts/
# pop_seedvc are clean_bonafide-vs-audio-synthesized-from-cloaked-audio
# -- three different comparisons that must not share one label).
DATA_LABEL_PREFIXES = {
    "sv2tts": "CleanBonafideVsCleanSynth",
    "f5tts": "CleanBonafideVsCleanSynth",
    "seedvc": "CleanBonafideVsCleanSynth",
    "POP": "CleanBonafideVsCloakedBonafide",
    "protectyouraudio": "CleanBonafideVsCloakedBonafide",
    "attackvc": "CleanBonafideVsCloakedBonafide",
    "antifake": "CleanBonafideVsCloakedBonafide",
    "pop_sv2tts": "CleanBonafideVsCloakedSynth",
    "pop_f5tts": "CleanBonafideVsCloakedSynth",
    "pop_seedvc": "CleanBonafideVsCloakedSynth",
    "attackvc_sv2tts": "CleanBonafideVsCloakedSynth",
    "attackvc_seedvc": "CleanBonafideVsCloakedSynth",
    "attackvc_f5tts": "CleanBonafideVsCloakedSynth",
    "antifake_sv2tts": "CleanBonafideVsCloakedSynth",
    "antifake_seedvc": "CleanBonafideVsCloakedSynth",
    "antifake_f5tts": "CleanBonafideVsCloakedSynth",
    "protectyouraudio_sv2tts": "CleanBonafideVsCloakedSynth",
    "protectyouraudio_seedvc": "CleanBonafideVsCloakedSynth",
    "protectyouraudio_f5tts": "CleanBonafideVsCloakedSynth",
}

# Cloaking methods perturb the *same* recording rather than
# resynthesizing it (unlike the TTS systems in SYSTEM_DIRS above, which
# have different linguistic content each time), so sample-aligned
# signal-quality metrics (STOI/PESQ/SI-SDR) are well-defined for these
# and meaningless for the TTS systems -- see analysis/metrics.py's
# module docstring. Only computed for systems in this set.
CONTENT_PRESERVING_SYSTEMS = {"POP", "protectyouraudio", "attackvc", "antifake"}

# Descent x gender breakdown, additional to (not a replacement for) the
# overall pooled table below -- only FakeAVCeleb-sourced entries carry
# this demographic metadata (see data/prepare_manifest.py); LibriSpeech
# and ASVspoof2021 entries have neither, so they're excluded from this
# breakdown rather than lumped into a fake "unknown" group.
FAKEAVCELEB_GROUPS = [
    "African-men", "African-women",
    "Asian(East)-men", "Asian(East)-women",
    "Asian(South)-men", "Asian(South)-women",
    "Caucasian(American)-men", "Caucasian(American)-women",
    "Caucasian(European)-men", "Caucasian(European)-women",
]


class EmbeddingCache:
    def __init__(self, verifier_module):
        self.module = verifier_module
        self.cache = {}

    def get(self, path):
        if path not in self.cache:
            self.cache[path] = self.module.embed(path)
        return self.cache[path]

    def similarity(self, path_a, path_b):
        a, b = self.get(path_a), self.get(path_b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def load_manifest_by_stem():
    with open(MANIFEST_PATH) as f:
        entries = json.load(f)["entries"]
    by_stem, by_speaker = {}, {}
    for e in entries:
        stem = os.path.splitext(os.path.basename(e["file"]))[0]
        by_stem[stem] = e
        by_speaker.setdefault(e["speaker_id"], []).append(e["file"])
    return by_stem, by_speaker


# Trial-level identifiers, so a score file can be audited and re-sliced
# after the fact (matched-stem comparisons across conditions, paired
# cluster bootstrap by stem, "which clips did this condition lose").
# The first three columns keep their original order, so any reader that
# picks columns by name (or position) keeps working.
#   stem      the clip being scored (the synthesized/cloaked clip's name)
#   trial     "genuine", or "impostor_1".."impostor_10" (draw order)
#   ref_stem  the real recording it was compared against (its own source
#             clip for a genuine trial, another speaker's for an impostor)
#   sampling  tag of the impostor-sampling scheme (see SAMPLING_TAG)
CSV_COLUMNS = ["score", "label", "group", "stem", "trial", "ref_stem", "sampling"]

# Impostors are drawn per clip, from a generator seeded by the clip's own
# name (and SEED), so a given clip gets exactly the same 10 impostor
# recordings in every condition and for every verifier -- independent of
# processing order, of which other clips exist, and of which failed. (The
# earlier scheme used one sequential generator shared across clips and
# verifiers, so verifiers/conditions were scored on different trials.)
SAMPLING_TAG = "per-clip-v1"
FAILURE_COLUMNS = ["stem", "trial", "ref_stem", "reason"]


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)
        writer.writerows(rows)


def write_failures(csv_path, failures):
    """One file per scored CSV, in a failures/ subfolder (kept out of the
    csv_dir root so analysis/common.py's *.csv glob never mistakes it for
    a score file). Written even when empty, so 'no failures' is on record.
    """
    fail_dir = os.path.join(os.path.dirname(csv_path), "failures")
    os.makedirs(fail_dir, exist_ok=True)
    out = os.path.join(fail_dir, os.path.basename(csv_path))
    with open(out, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(FAILURE_COLUMNS)
        writer.writerows(failures)
    return out


def csv_has_ids(csv_path):
    """True if an existing score CSV already carries the trial-ID columns
    (older files have only score,label,group and must be re-scored)."""
    with open(csv_path) as f:
        header = f.readline().strip().split(",")
    return all(c in header for c in ("stem", "trial", "ref_stem"))


def csv_current(csv_path):
    """True if the score CSV has trial IDs AND was produced with the
    current per-clip impostor sampling (older files must be re-scored)."""
    with open(csv_path) as f:
        header = f.readline().strip().split(",")
    return csv_has_ids(csv_path) and "sampling" in header


def _stem(path):
    return os.path.splitext(os.path.basename(path))[0]


def score_all(system_name, synth_dir, csv_dir):
    by_stem, by_speaker = load_manifest_by_stem()
    speakers = list(by_speaker.keys())

    synth_files = sorted(glob.glob(os.path.join(synth_dir, "*.wav")))
    print(f"{system_name}: {len(synth_files)} synthesized clips found")

    for model_name, module in VERIFIERS.items():
        csv_path = os.path.join(csv_dir, f"{system_name}__{system_name}__{model_name}.csv")

        # Skip already-fully-scored models on retry (matches
        # verify/run_all.py's convention) -- this GPU has a known VRAM
        # plateau on long runs (see run_f5tts_batched.sh), so a retry
        # after a mid-run OOM shouldn't have to redo verifiers that
        # already finished.
        expected_rows = len(synth_files) * (1 + IMPOSTORS_PER_CLIP)
        if os.path.exists(csv_path):
            with open(csv_path) as f:
                existing_rows = sum(1 for _ in f) - 1
            if not csv_current(csv_path):
                print(f"  [rescore] {model_name}: {csv_path} predates trial IDs / per-clip impostor sampling; re-scoring")
            elif existing_rows >= expected_rows:
                print(f"  [skip] {model_name}: {csv_path} already fully scored ({existing_rows} rows)")
                continue

        cache = EmbeddingCache(module)
        rows = []
        failures = []
        for j, synth_wav in enumerate(synth_files):
            stem = os.path.splitext(os.path.basename(synth_wav))[0]
            entry = by_stem.get(stem)
            if entry is None:
                continue
            group = f"{entry['descent']}-{entry['gender']}" if "descent" in entry else ""

            # A handful of synthesized clips are pathologically long
            # (TTS babbling/repetition failures, e.g. 100+s against a
            # ~20s median) and OOM transformer-attention verifiers
            # (O(n^2) in sequence length) on this GPU. Skip rather than
            # abort the whole run -- matches verify/run_all.py's
            # per-file try/except convention.
            try:
                genuine_score = cache.similarity(synth_wav, entry["file"])
            except Exception as e:
                print(f"  [warn] {model_name}: failed on {stem} ({e}); skipping this clip")
                failures.append((stem, "genuine", stem, str(e)[:200]))
                try:
                    import torch
                    torch.cuda.empty_cache()
                except Exception:
                    pass
                continue
            rows.append((f"{genuine_score:.6f}", 1, group, stem, "genuine", stem, SAMPLING_TAG))

            # per-clip generator: same clip -> same impostors everywhere
            rng = random.Random(f"{SEED}:{stem}")
            other_speakers = [s for s in speakers if s != entry["speaker_id"]]
            impostor_speakers = rng.sample(other_speakers, min(IMPOSTORS_PER_CLIP, len(other_speakers)))
            for k, spk in enumerate(impostor_speakers, 1):
                impostor_file = rng.choice(by_speaker[spk])
                try:
                    impostor_score = cache.similarity(synth_wav, impostor_file)
                except Exception as e:
                    print(f"  [warn] {model_name}: failed on {stem} vs impostor ({e}); skipping this trial")
                    failures.append((stem, f"impostor_{k}", _stem(impostor_file), str(e)[:200]))
                    try:
                        import torch
                        torch.cuda.empty_cache()
                    except Exception:
                        pass
                    continue
                rows.append((f"{impostor_score:.6f}", 0, group, stem, f"impostor_{k}", _stem(impostor_file), SAMPLING_TAG))

            if (j + 1) % 200 == 0:
                print(f"  {model_name}: scored {j + 1}/{len(synth_files)}")
                # Release PyTorch's cached-but-unused GPU memory. The GPU is
                # shared with long synthesis jobs, and the cache otherwise
                # grows to several GB after a few long clips.
                try:
                    import torch
                    torch.cuda.empty_cache()
                except Exception:
                    pass

        write_csv(csv_path, rows)
        fail_path = write_failures(csv_path, failures)
        n_genuine = sum(1 for r in rows if r[1] == 1)
        n_impostor = sum(1 for r in rows if r[1] == 0)
        print(f"  wrote {csv_path} ({n_genuine} genuine, {n_impostor} impostor; "
              f"{len(failures)} failures logged in {fail_path})")


def _eer_metric_fn(labels, scores):
    far, tar, _ = roc_curve(labels, scores)
    return compute_eer(far, tar)


def _tar_at_1pct_metric_fn(labels, scores):
    far, tar, _ = roc_curve(labels, scores)
    return tar_at_far(far, tar, 0.01)


def compute_quality_metrics_ungated(compare_dir):
    """STOI/PESQ/SI-SDR between clean_bonafide (reference) and every
    same-stem file in compare_dir, with NO content-preserving check --
    only call this when the caller has independently verified compare_dir
    holds sample-aligned, same-content audio (e.g. a cloaked_bonafide
    directory, or a restoration technique's output applied directly to
    cloaked_bonafide, both of which perturb/filter the original recording
    in place rather than resynthesizing it). Calling this against a TTS/VC
    clone's output (different or reference-driven fixed linguistic
    content -- see CONTENT_PRESERVING_SYSTEMS below) produces meaningless
    near-floor numbers, since STOI/PESQ/SI-SDR assume the two signals say
    the same words. Returns None if no same-stem files were found.
    """
    import librosa

    by_stem, _ = load_manifest_by_stem()
    synth_files = sorted(glob.glob(os.path.join(compare_dir, "*.wav")))

    stois, pesqs, sisdrs = [], [], []
    for synth_wav in synth_files:
        stem = os.path.splitext(os.path.basename(synth_wav))[0]
        entry = by_stem.get(stem)
        if entry is None:
            continue

        try:
            clean_audio, _ = librosa.load(entry["file"], sr=QUALITY_SCORE_SR, mono=True)
            cloaked_audio, _ = librosa.load(synth_wav, sr=QUALITY_SCORE_SR, mono=True)
            stois.append(stoi_score(clean_audio, cloaked_audio, QUALITY_SCORE_SR))
            pesqs.append(pesq_score(clean_audio, cloaked_audio, QUALITY_SCORE_SR))
            sisdrs.append(si_sdr(clean_audio, cloaked_audio))
        except Exception as e:
            print(f"  [warn] quality metrics failed on {stem}: {e}")

    if not stois:
        return None

    return {
        "STOI_mean": round(float(np.mean(stois)), 4),
        "STOI_median": round(float(np.median(stois)), 4),
        "PESQ_mean": round(float(np.mean(pesqs)), 4),
        "PESQ_median": round(float(np.median(pesqs)), 4),
        # SI-SDR is NaN for clips whose timing misalignment is time-varying
        # (see metrics.align_signals); average only the valid ones and say
        # how many that was, instead of reporting a number that reflects
        # timing jitter rather than distortion.
        "SI_SDR_mean_dB": round(float(np.nanmean(sisdrs)), 4) if np.isfinite(sisdrs).any() else float("nan"),
        "SI_SDR_median_dB": round(float(np.nanmedian(sisdrs)), 4) if np.isfinite(sisdrs).any() else float("nan"),
        "SI_SDR_valid_share": round(float(np.isfinite(sisdrs).mean()), 3),
        "quality_N": len(stois),
    }


def compute_quality_metrics(system_name, synth_dir):
    """STOI/PESQ/SI-SDR between clean_bonafide (reference) and the
    cloaked clip (degraded), for content-preserving cloaking methods
    only -- undefined for TTS systems, which resynthesize different
    text each time (see CONTENT_PRESERVING_SYSTEMS above and
    analysis/metrics.py's module docstring). Returns None if not
    applicable, so callers can skip adding these columns entirely.
    """
    if system_name not in CONTENT_PRESERVING_SYSTEMS:
        return None
    return compute_quality_metrics_ungated(synth_dir)


def build_results_table(system_name, csv_dir, out_dir, quality=None):
    rows = []
    for model_name in VERIFIERS:
        csv_path = os.path.join(csv_dir, f"{system_name}__{system_name}__{model_name}.csv")
        df = pd.read_csv(csv_path)
        labels = df.label.to_numpy()
        scores = df.score.to_numpy()
        n_target, n_impostor = int((labels == 1).sum()), int((labels == 0).sum())

        far, tar, _ = roc_curve(labels, scores)
        eer = compute_eer(far, tar)
        # Low-FAR TAR at an actually attainable threshold (no ROC
        # interpolation), with the false-accept count it rests on.
        att = {fp: rs.attainable_tar_at_far(labels, scores, fp) for fp in config.FAR_OPERATING_POINTS}
        tar_far = {fp: att[fp]["tar"] for fp in att}
        if "stem" in df.columns:
            # Cluster bootstrap: resample whole clips (stems) with all of
            # their trials, since a clip's ~10 impostor trials share a query.
            ci = rs.cluster_bootstrap(rs.load_trials(csv_path),
                                      {"EER": rs.eer_metric, "TAR@1%": rs.tar_metric(0.01)})
            eer_lo, eer_hi = ci["EER"]["lo"], ci["EER"]["hi"]
            tar1_lo, tar1_hi = ci["TAR@1%"]["lo"], ci["TAR@1%"]["hi"]
            ci_method = "cluster-by-stem"
        else:
            eer_lo, eer_hi = bootstrap_ci(labels, scores, _eer_metric_fn)
            tar1_lo, tar1_hi = bootstrap_ci(labels, scores, _tar_at_1pct_metric_fn)
            ci_method = "score-level (legacy; too narrow)"
        target_scores, impostor_scores = scores[labels == 1], scores[labels == 0]

        row = {
            "Data": f"{DATA_LABEL_PREFIXES[system_name]}/{system_name}",
            "SV": MODEL_DISPLAY_NAMES[model_name],
            "EER": round(eer, 4),
            "EER_CI95": f"[{eer_lo:.4f}, {eer_hi:.4f}]",
            "TAR@1%": round(tar_far[0.01], 4),
            "TAR@1%_CI95": f"[{tar1_lo:.4f}, {tar1_hi:.4f}]",
            "TAR@0.1%": round(tar_far[0.001], 4),
            "TAR@0.01%": round(tar_far[0.0001], 4),
            "nFA@0.1%": att[0.001]["n_fa"],
            "nFA@0.01%": att[0.0001]["n_fa"],
            "CI_method": ci_method,
            "minDCF": round(min_dcf(labels, scores), 4),
            "d_prime": round(d_prime(labels, scores), 4),
            "overlap_coef": round(overlap_coefficient(labels, scores), 4),
            "ROC_AUC": round(full_roc_auc(labels, scores), 4),
            "pAUC@1%FAR": round(partial_auc(labels, scores, far_max=0.01), 4),
            "pAUC@0.1%FAR": round(partial_auc(labels, scores, far_max=0.001), 4),
            "target_mean": round(float(target_scores.mean()), 4),
            "target_median": round(float(np.median(target_scores)), 4),
            "impostor_mean": round(float(impostor_scores.mean()), 4),
            "impostor_median": round(float(np.median(impostor_scores)), 4),
            "#T/#I": f"{n_target}/{n_impostor}",
        }
        # Same STOI/PESQ/SI-SDR values repeated on every verifier's row
        # -- these metrics don't depend on which verifier scored the
        # trials, so there's one value per system, not per verifier.
        if quality is not None:
            row.update(quality)
        rows.append(row)

    result_df = pd.DataFrame(rows)
    out_csv = os.path.join(out_dir, "results_table.csv")
    result_df.to_csv(out_csv, index=False)
    print(f"\nWrote {out_csv}\n")
    print(result_df.to_string(index=False))
    return result_df


def build_group_breakdown(system_name, csv_dir, out_dir):
    """Same EER/TAR@1% metrics as build_results_table, but broken out
    by descent x gender, restricted to the FakeAVCeleb-sourced subset
    (the only entries carrying that metadata). Supplementary to, not a
    replacement for, the overall pooled results_table.csv.
    """
    rows = []
    for model_name in VERIFIERS:
        csv_path = os.path.join(csv_dir, f"{system_name}__{system_name}__{model_name}.csv")
        df = pd.read_csv(csv_path)
        for group in FAKEAVCELEB_GROUPS:
            subset = df[df.group == group]
            if subset.empty:
                continue
            labels = subset.label.to_numpy()
            scores = subset.score.to_numpy()
            n_target, n_impostor = int((labels == 1).sum()), int((labels == 0).sum())

            far, tar, _ = roc_curve(labels, scores)
            eer = compute_eer(far, tar)
            tar1 = rs.attainable_tar_at_far(labels, scores, 0.01)["tar"]

            rows.append({
                "Data": f"{DATA_LABEL_PREFIXES[system_name]}/{system_name}",
                "SV": MODEL_DISPLAY_NAMES[model_name],
                "Group": group,
                "EER": round(eer, 4),
                "TAR@1%": round(tar1, 4),
                "#T/#I": f"{n_target}/{n_impostor}",
            })

    result_df = pd.DataFrame(rows)
    out_csv = os.path.join(out_dir, "results_table_by_group.csv")
    result_df.to_csv(out_csv, index=False)
    print(f"\nWrote {out_csv}\n")
    print(result_df.to_string(index=False))
    return result_df


def plot_all(system_name, csv_dir, plots_dir, n_boot=200):
    from analysis.metrics import bootstrap_roc_band

    dfs = []
    for model_name in VERIFIERS:
        csv_path = os.path.join(csv_dir, f"{system_name}__{system_name}__{model_name}.csv")
        d = pd.read_csv(csv_path)
        d["model"] = model_name
        dfs.append(d)
    df = pd.concat(dfs, ignore_index=True)

    color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    # ROC with bootstrap bands
    plt.figure(figsize=(8, 6))
    far_grid = np.logspace(-4, 0, 200)
    for i, model_name in enumerate(VERIFIERS):
        subset = df[df.model == model_name]
        color = color_cycle[i % len(color_cycle)]
        median_tar, lo, hi = bootstrap_roc_band(subset.label, subset.score, far_grid, n_boot=n_boot)
        plt.fill_between(far_grid, lo, hi, color=color, alpha=0.15, linewidth=0)
        plt.plot(far_grid, median_tar, color=color, label=MODEL_DISPLAY_NAMES[model_name])
    plt.xscale("log")
    plt.xlabel("FAR (log scale)")
    plt.ylabel("TAR")
    plt.ylim(0, 1.02)
    plt.title(f"clean_bonafide vs. {system_name}: ROC (bootstrap 95% CI)")
    plt.legend()
    plt.grid(True, which="both", alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "roc.png"), dpi=200)
    plt.close()

    # DET
    tick_percents = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 40, 60, 80]
    tick_pos = norm.ppf([v / 100 for v in tick_percents])
    tick_labels = [f"{v:g}" for v in tick_percents]
    plt.figure(figsize=(8, 7))
    for i, model_name in enumerate(VERIFIERS):
        subset = df[df.model == model_name]
        far, tar, _ = roc_curve(subset.label, subset.score)
        frr = 1 - tar
        far_c = np.clip(far, 1e-4, 1 - 1e-4)
        frr_c = np.clip(frr, 1e-4, 1 - 1e-4)
        plt.plot(norm.ppf(far_c), norm.ppf(frr_c), color=color_cycle[i % len(color_cycle)],
                 label=MODEL_DISPLAY_NAMES[model_name])
    plt.xticks(tick_pos, tick_labels)
    plt.yticks(tick_pos, tick_labels)
    plt.xlim(norm.ppf(0.0008), norm.ppf(0.85))
    plt.ylim(norm.ppf(0.0008), norm.ppf(0.85))
    plt.xlabel("FAR (%)")
    plt.ylabel("FRR (%)")
    plt.title(f"clean_bonafide vs. {system_name}: DET curve")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "det.png"), dpi=200)
    plt.close()

    # score distributions
    plt.figure(figsize=(10, 7))
    for model_name in VERIFIERS:
        subset = df[df.model == model_name]
        for label, name in [(1, "genuine"), (0, "impostor")]:
            scores = subset[subset.label == label].score
            if scores.empty:
                continue
            plt.hist(scores, bins=30, histtype="step", density=True, linewidth=1.3,
                     label=f"{MODEL_DISPLAY_NAMES[model_name]} {name}")
    plt.xlabel("Cosine similarity score")
    plt.ylabel("Density")
    plt.title(f"clean_bonafide vs. {system_name}: score distributions")
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "dist.png"), dpi=200)
    plt.close()


def plot_group_breakdown(system_name, csv_dir, plots_dir):
    dfs = []
    for model_name in VERIFIERS:
        csv_path = os.path.join(csv_dir, f"{system_name}__{system_name}__{model_name}.csv")
        d = pd.read_csv(csv_path)
        d["model"] = model_name
        dfs.append(d)
    df = pd.concat(dfs, ignore_index=True)

    plot_rows = []
    for model_name in VERIFIERS:
        for group in FAKEAVCELEB_GROUPS:
            subset = df[(df.model == model_name) & (df.group == group)]
            if subset.empty:
                continue
            far, tar, _ = roc_curve(subset.label, subset.score)
            plot_rows.append({"group": group, "model": model_name, "eer": compute_eer(far, tar)})

    if not plot_rows:
        print("No FakeAVCeleb-sourced clips found -- skipping group breakdown plot.")
        return

    plot_df = pd.DataFrame(plot_rows)
    groups = [g for g in FAKEAVCELEB_GROUPS if g in plot_df.group.unique()]
    x = np.arange(len(groups))
    width = 0.8 / len(VERIFIERS)

    plt.figure(figsize=(12, 6))
    for i, model_name in enumerate(VERIFIERS):
        vals = [
            plot_df.loc[(plot_df.group == g) & (plot_df.model == model_name), "eer"].pipe(
                lambda s: s.iloc[0] if not s.empty else np.nan
            )
            for g in groups
        ]
        plt.bar(x + i * width, vals, width, label=MODEL_DISPLAY_NAMES[model_name])

    plt.xticks(x + width, groups, rotation=45, ha="right")
    plt.ylabel("EER")
    plt.title(f"clean_bonafide vs. {system_name}: EER by descent x gender (FakeAVCeleb subset)")
    plt.legend()
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "eer_by_group.png"), dpi=200)
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", required=True, choices=list(SYSTEM_DIRS.keys()))
    parser.add_argument("--out-dir", default=None,
                         help="override the default results/cleanbonafidevscleansynth/<SYSTEM> output location")
    args = parser.parse_args()

    system_name = args.system
    synth_dir = SYSTEM_DIRS[system_name]

    out_root = args.out_dir or os.path.join(config.RESULTS_DIR, "cleanbonafidevscleansynth", system_name.upper())
    csv_dir = os.path.join(out_root, "csvs")
    plots_dir = os.path.join(out_root, "plots")
    os.makedirs(csv_dir, exist_ok=True)
    os.makedirs(plots_dir, exist_ok=True)

    score_all(system_name, synth_dir, csv_dir)
    quality = compute_quality_metrics(system_name, synth_dir)
    build_results_table(system_name, csv_dir, out_root, quality=quality)
    build_group_breakdown(system_name, csv_dir, out_root)

    global plt
    import matplotlib.pyplot as plt
    plot_all(system_name, csv_dir, plots_dir)
    plot_group_breakdown(system_name, csv_dir, plots_dir)
    print(f"\nAll outputs written under {out_root}")


if __name__ == "__main__":
    main()
