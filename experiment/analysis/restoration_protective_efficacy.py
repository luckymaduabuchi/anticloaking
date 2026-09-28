#!/usr/bin/env python3
"""Protective-efficacy evaluation for the adaptive-attacker restoration
study (Paper \\S sec:restoration): scores clones made from *restored*
cloaked audio against the genuine clean_bonafide original, using the
exact same trial-construction/scoring machinery as
clean_bonafide_vs_synth.py's pop_sv2tts/attackvc_sv2tts systems (one
genuine + ten impostor trials per clip, all three verifiers).

Reused, not reimplemented: score_all/build_results_table/
build_group_breakdown from clean_bonafide_vs_synth.py. This script only
adds a generic (label, synth_dir) driving loop plus per-combination
output paths, since the restoration study has many more (technique,
cloak method, variant, synthesizer) combinations than the shared
SYSTEM_DIRS dict is set up to hardcode one at a time.

A restoration technique's *cell* reverses the cloak's protective effect
if its EER/TAR@FAR moves back toward the clean-audio ceiling
(tab:synth-ceiling) relative to the no-restoration cloaked-source
baseline (tab:protective-efficacy / tab:protective-efficacy-attackvc);
if it stays close to (or worse than) the no-restoration baseline, the
cloak's protection survived restoration.

Run (inside antifake2026 env):
    conda run -n antifake2026 python analysis/restoration_protective_efficacy.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from analysis import clean_bonafide_vs_synth as base

RESULTS_ROOT = os.path.join(config.RESULTS_DIR, "groundtruthvscloaking")
RESTORATION_ROOT = "/home/vm-user/Desktop/Antifake2026/Dataset/restoration techniques"

# (label, synth_dir, out_dir, restored_dir) tuples to evaluate.
# restored_dir is the *pre-clone* restoration-technique output (same
# recording/content as clean_bonafide, just filtered/perturbed) -- used
# for STOI/PESQ/SI-SDR quality metrics, which are only well-defined
# against sample-aligned same-content audio. synth_dir (the SV2TTS/
# Seed-VC/F5-TTS clone actually scored for EER/TAR/etc.) is NOT
# content-aligned with clean_bonafide (every synthesizer in this project
# uses a fixed reference script/content, see
# clean_bonafide_vs_synth.compute_quality_metrics_ungated's docstring),
# so quality is computed from restored_dir, never from synth_dir. Add a
# new tuple here as each additional restoration-technique/variant/
# synthesizer combination finishes its downstream cloning.
JOBS = []

# Every (label, out_dir, restored_dir) combination whose downstream
# cloning is complete, REGARDLESS of already-scored status -- JOBS above
# only holds not-yet-scored ones. Used by backfill_quality() to add
# STOI/PESQ/SI-SDR to already-scored results_table.csv files that
# predate quality metrics being wired into this script (all SV2TTS
# restoration results scored before this addition).
ALL_KNOWN = []

def already_scored(out_dir):
    return os.path.isfile(os.path.join(out_dir, "results_table.csv"))


def restoration_root_dir(technique, method, gain=None):
    """Pre-clone restoration output dir for (technique, cloak-method[, gain]),
    matching the on-disk layout under Dataset/restoration techniques/ (the
    --source-dir convention already used by run_pop_restoration_f5tts.sh /
    run_attackvc_restoration_f5tts.sh)."""
    if technique in ("downsampling", "upsampling"):
        variant = "downsample" if technique == "downsampling" else "upsample"
        return os.path.join(RESTORATION_ROOT, "resampling", method, variant)
    if technique in ("low_pass", "lowpass_gain"):
        if gain is None or gain == "1.0":
            return os.path.join(RESTORATION_ROOT, "low_pass", method)
        return os.path.join(RESTORATION_ROOT, "low_pass_gain", method, f"gain_{gain}")
    return os.path.join(RESTORATION_ROOT, technique, method)


LOWPASS_ATTACKVC_ROOT = os.path.join(config.RESTORED_SYNTHESIZE_DIR, "Low_pass", "attackvc")
for gain_dir in sorted(os.listdir(LOWPASS_ATTACKVC_ROOT)) if os.path.isdir(LOWPASS_ATTACKVC_ROOT) else []:
    # gain_dir looks like "gain 1.2" (space); a stray, incomplete
    # underscore-named duplicate ("gain_1.2") also exists on disk from an
    # earlier naming mismatch -- skip anything that isn't exactly "gain X.X".
    if not re.fullmatch(r"gain \d+\.\d+", gain_dir):
        continue
    gain_value = gain_dir.replace("gain ", "")
    sv2tts_dir = os.path.join(LOWPASS_ATTACKVC_ROOT, gain_dir, "sv2tts")
    if os.path.isdir(sv2tts_dir):
        label = f"lowpass_attackvc_gain{gain_value}_sv2tts"
        out_dir = os.path.join(
            RESULTS_ROOT, "groundtruthvsattackvc", "groundtruthvsrestoredsynthesis",
            "lowpass_gain", f"gain_{gain_value}", "sv2tts",
        )
        _restored = restoration_root_dir("low_pass", "attackvc", gain_value)
        ALL_KNOWN.append((label, out_dir, _restored))
        if not already_scored(out_dir):
            JOBS.append((label, sv2tts_dir, out_dir, _restored))

ADAPTIVE_POP_SV2TTS = os.path.join(config.ADAPTIVE_FILTER_CENTROID_SYNTH_DIR, "POP", "sv2tts")
ADAPTIVE_POP_OUT = os.path.join(
    RESULTS_ROOT, "groundtruthvsPOP", "groundtruthvsrestoredsynthesis",
    "adaptive_filter_centroid", "sv2tts",
)
if os.path.isdir(ADAPTIVE_POP_SV2TTS):
    _restored = restoration_root_dir("adaptive_filter_centroid", "POP")
    ALL_KNOWN.append(("adaptivefilter_pop_sv2tts", ADAPTIVE_POP_OUT, _restored))
    if not already_scored(ADAPTIVE_POP_OUT):
        JOBS.append(("adaptivefilter_pop_sv2tts", ADAPTIVE_POP_SV2TTS, ADAPTIVE_POP_OUT, _restored))

# ---------------------------------------------------------------------------
# Everything below fills in the other half of every restoration technique
# (whichever cloak method -- POP or attack-vc -- wasn't scored above), plus
# every other restoration technique's SV2TTS clone, for both cloak methods.
# Paths are the *actual* on-disk directory names under
# Dataset/restored_synthesize/, which in several cases do not match
# config.py's own *_SYNTH_DIR constants (inconsistent casing/naming
# introduced across different ad hoc synthesis scripts over the course of
# the project); rather than fix every constant, we point directly at the
# verified, populated directories. SKIPPED = combinations whose downstream
# cloning is not yet complete as of this run; re-run this script once they
# finish and they will be picked up automatically.
# ---------------------------------------------------------------------------
SKIPPED = []


def add_job_if_complete(label, synth_dir, expected_total, cloak_group, technique_result_path, restored_dir=None):
    n = len([f for f in os.listdir(synth_dir) if f.endswith(".wav")]) if os.path.isdir(synth_dir) else 0
    out_dir = os.path.join(RESULTS_ROOT, cloak_group, "groundtruthvsrestoredsynthesis", *technique_result_path)
    if n >= expected_total:
        ALL_KNOWN.append((label, out_dir, restored_dir))
        if not already_scored(out_dir):
            JOBS.append((label, synth_dir, out_dir, restored_dir))
    else:
        SKIPPED.append((label, synth_dir, n, expected_total))


TOTALS = {"POP": 4864, "attackvc": 4863, "Antifake": 4844}
GROUP = {"POP": "groundtruthvsPOP", "attackvc": "groundtruthvsattackvc", "Antifake": "groundtruthvsAntifake"}

# A handful of combinations stabilized below their nominal corpus size
# after two retry passes confirmed the remaining gap is a small, genuine
# per-clip failure rate (not transient GPU contention) -- same pattern
# as POP's own 4,864/4,867 and attack-vc's 4,863/4,867 cloak-generation
# ceilings elsewhere in this project. Override the expected total to the
# observed ceiling so these are picked up rather than skipped forever.
CEILING_OVERRIDES = {
    "lowpass_pop_gain1.8_sv2tts": 4862,
    "lowpass_pop_gain2.0_sv2tts": 4849,
    "highpass_attackvc_sv2tts": 4848,
    "upsampling_pop_sv2tts": 4838,
    "spectral_subtraction_antifake_sv2tts": 4826,
    "re_recording_antifake_sv2tts": 4829,
    "second_cloak_noise_pop_sv2tts": 4777,
    # attack-vc, Seed-VC/F5-TTS clones -- confirmed via on-disk audit.
    "adaptive_filter_centroid_attackvc_f5tts": 4851,
    "highpass_attackvc_f5tts": 4862,
    "spectral_subtraction_attackvc_f5tts": 4862,
    "lowpass_attackvc_gain1.4_f5tts": 4862,
}


def expected_total(label, method):
    return CEILING_OVERRIDES.get(label, TOTALS[method])


# Low-pass+gain, POP side (attack-vc side already handled above).
LOWPASS_POP_ROOT = os.path.join(config.RESTORED_SYNTHESIZE_DIR, "Low_pass", "POP")
for gain in ("1.0", "1.2", "1.4", "1.6", "1.8", "2.0"):
    gain_dir = os.path.join(LOWPASS_POP_ROOT, f"gain_{gain}")
    # gain_1.0 was an early one-off run with wavs written directly into the
    # gain dir (no "sv2tts" subfolder); every other gain has one.
    sv2tts_dir = gain_dir if gain == "1.0" else os.path.join(gain_dir, "sv2tts")
    label = f"lowpass_pop_gain{gain}_sv2tts"
    add_job_if_complete(
        label, sv2tts_dir, expected_total(label, "POP"), "groundtruthvsPOP",
        ("lowpass_gain", f"gain_{gain}", "sv2tts"),
        restored_dir=restoration_root_dir("low_pass", "POP", gain),
    )

# Adaptive-filter-centroid, attack-vc + Antifake sides (POP side already
# handled above).
add_job_if_complete(
    "adaptivefilter_attackvc_sv2tts",
    os.path.join(config.ADAPTIVE_FILTER_CENTROID_SYNTH_DIR, "attackvc", "sv2tts"),
    TOTALS["attackvc"], "groundtruthvsattackvc",
    ("adaptive_filter_centroid", "sv2tts"),
    restored_dir=restoration_root_dir("adaptive_filter_centroid", "attackvc"),
)
add_job_if_complete(
    "adaptivefilter_antifake_sv2tts",
    os.path.join(config.ADAPTIVE_FILTER_CENTROID_SYNTH_DIR, "Antifake", "sv2tts"),
    TOTALS["Antifake"], "groundtruthvsAntifake",
    ("adaptive_filter_centroid", "sv2tts"),
    restored_dir=restoration_root_dir("adaptive_filter_centroid", "Antifake"),
)

# Remaining restoration techniques: all cloak methods with complete
# downstream cloning found on disk, on-disk directory name may differ
# from config.py's constant (noted per entry). Discovered as of this
# run: downsampling, ensemble-averaging, mel-spectrogram-inversion,
# quantization, and high-pass all also have complete AntiFake-cloaked
# SV2TTS output (never previously scored); upsampling's AntiFake output
# is still in progress and will show up in SKIPPED until it finishes.
OTHER_TECHNIQUES = [
    # (technique result-folder name, on-disk restored_synthesize dirname)
    ("downsampling", "Downsampling"),                 # matches config's naming pattern
    ("upsampling", "Upsampling"),
    ("ensemble_averaging_perturbed", "ensemble_averaging_perturbed"),  # lowercase on disk; config says "Ensemble_averaging_perturbed"
    ("mel_spectrogram_inversion", "Mel_spectrogram"),  # config says "Mel_spectrogram_inversion"
    ("quantization", "quantization"),                 # lowercase on disk; config says "Quantization"
    ("re_recording", "SimulatedReRecord"),             # config says "Re_recording"
    ("spectral_subtraction", "SpectralSubtraction"),   # config says "Spectral_subtraction"
    ("highpass", "Highpass"),
]

for technique, dirname in OTHER_TECHNIQUES:
    root = os.path.join(config.RESTORED_SYNTHESIZE_DIR, dirname)
    for method in ("POP", "attackvc", "Antifake"):
        sv2tts_dir = os.path.join(root, method, "sv2tts")
        label = f"{technique}_{method.lower()}_sv2tts"
        group = GROUP.get(method, f"groundtruthvs{method}")
        add_job_if_complete(
            label, sv2tts_dir, expected_total(label, method), group,
            (technique, "sv2tts"),
            restored_dir=restoration_root_dir(technique, method),
        )

# Low-pass+gain, AntiFake side: a single one-off gain (1.0, no sweep),
# stored without the underscore in the gain-value folder name
# ("gain1.0" not "gain_1.0") unlike POP/attack-vc's convention.
add_job_if_complete(
    "lowpass_antifake_gain1.0_sv2tts",
    os.path.join(config.RESTORED_SYNTHESIZE_DIR, "Low_pass", "Antifake", "gain1.0", "sv2tts"),
    TOTALS["Antifake"], "groundtruthvsAntifake",
    ("lowpass_gain", "gain_1.0", "sv2tts"),
    restored_dir=restoration_root_dir("low_pass", "Antifake"),
    )

# Second-cloak application, corrected to cloak-agnostic additive noise
# (Paper \S sec:restoration-secondcloak) -- uniquely covers all three
# cloak methods, including AntiFake.
for method in ("POP", "attackvc", "Antifake"):
    sv2tts_dir = os.path.join(config.SECOND_CLOAK_NOISE_SYNTH_DIR, method, "sv2tts")
    label = f"second_cloak_noise_{method.lower()}_sv2tts"
    add_job_if_complete(
        label, sv2tts_dir, expected_total(label, method), GROUP[method],
        ("second_cloak_noise", "sv2tts"),
        restored_dir=restoration_root_dir("second_cloak_noise", method),
    )

# ---------------------------------------------------------------------------
# attack-vc restoration, Seed-VC and F5-TTS clones (SV2TTS already scored
# above/elsewhere). Same techniques, same on-disk dirnames as the SV2TTS
# jobs -- just a different synth subfolder, verified present via direct
# on-disk audit before wiring in (Downsampling, Upsampling,
# ensemble_averaging_perturbed, Mel_spectrogram, quantization,
# SimulatedReRecord, SpectralSubtraction, Highpass, Second_cloak_noise all
# have clean technique/attackvc/{seedvc,f5tts}/ siblings; a couple of
# techniques' F5-TTS output stabilized a few clips short of 4863 after
# retries, same permanent-failure pattern as everywhere else in this
# project -- see CEILING_OVERRIDES).
# ---------------------------------------------------------------------------
ATTACKVC_MULTI_SYNTH_TECHNIQUES = [
    ("adaptive_filter_centroid", os.path.join(config.ADAPTIVE_FILTER_CENTROID_SYNTH_DIR, "attackvc")),
    ("downsampling", os.path.join(config.RESTORED_SYNTHESIZE_DIR, "Downsampling", "attackvc")),
    ("upsampling", os.path.join(config.RESTORED_SYNTHESIZE_DIR, "Upsampling", "attackvc")),
    ("ensemble_averaging_perturbed", os.path.join(config.RESTORED_SYNTHESIZE_DIR, "ensemble_averaging_perturbed", "attackvc")),
    ("mel_spectrogram_inversion", os.path.join(config.RESTORED_SYNTHESIZE_DIR, "Mel_spectrogram", "attackvc")),
    ("quantization", os.path.join(config.RESTORED_SYNTHESIZE_DIR, "quantization", "attackvc")),
    ("re_recording", os.path.join(config.RESTORED_SYNTHESIZE_DIR, "SimulatedReRecord", "attackvc")),
    ("spectral_subtraction", os.path.join(config.RESTORED_SYNTHESIZE_DIR, "SpectralSubtraction", "attackvc")),
    ("highpass", os.path.join(config.RESTORED_SYNTHESIZE_DIR, "Highpass", "attackvc")),
    ("second_cloak_noise", os.path.join(config.SECOND_CLOAK_NOISE_SYNTH_DIR, "attackvc")),
]

for technique, base_dir in ATTACKVC_MULTI_SYNTH_TECHNIQUES:
    for synth in ("seedvc", "f5tts"):
        synth_dir = os.path.join(base_dir, synth)
        label = f"{technique}_attackvc_{synth}"
        add_job_if_complete(
            label, synth_dir, expected_total(label, "attackvc"), "groundtruthvsattackvc",
            (technique, synth),
            restored_dir=restoration_root_dir(technique, "attackvc"),
        )

# Low-pass+gain, attack-vc, Seed-VC and F5-TTS: on-disk locations differ
# from the flat gain_X/<synth> layout the SV2TTS loop above uses -- an
# external reorganization (observed on-disk, not made by any script in
# this repo) nested Seed-VC/F5-TTS output under extra "Seedvc"/"F5TTS"
# parent directories (Seedvc/gain_X/seedvc/, F5TTS/gain_X/f5tts/).
# F5TTS/gain_X/sv2tts/ is a stray, incomplete duplicate (4302-4770 of
# 4863, confirmed via on-disk audit) apparently dragged along by the same
# reorganization -- deliberately NOT used here; the complete,
# already-scored SV2TTS data remains at the original "gain X.X" (space)
# path the loop above points to.
LOWPASS_ATTACKVC_SEEDVC_ROOT = os.path.join(LOWPASS_ATTACKVC_ROOT, "Seedvc")
LOWPASS_ATTACKVC_F5TTS_ROOT = os.path.join(LOWPASS_ATTACKVC_ROOT, "F5TTS")
for gain in ("1.0", "1.2", "1.4", "1.6", "1.8", "2.0"):
    seedvc_dir = os.path.join(LOWPASS_ATTACKVC_SEEDVC_ROOT, f"gain_{gain}", "seedvc")
    label = f"lowpass_attackvc_gain{gain}_seedvc"
    add_job_if_complete(
        label, seedvc_dir, expected_total(label, "attackvc"), "groundtruthvsattackvc",
        ("lowpass_gain", f"gain_{gain}", "seedvc"),
        restored_dir=restoration_root_dir("low_pass", "attackvc", gain),
    )
    f5tts_dir = os.path.join(LOWPASS_ATTACKVC_F5TTS_ROOT, f"gain_{gain}", "f5tts")
    label = f"lowpass_attackvc_gain{gain}_f5tts"
    add_job_if_complete(
        label, f5tts_dir, expected_total(label, "attackvc"), "groundtruthvsattackvc",
        ("lowpass_gain", f"gain_{gain}", "f5tts"),
        restored_dir=restoration_root_dir("low_pass", "attackvc", gain),
    )


def backfill_quality():
    """Add STOI/PESQ/SI-SDR to already-scored results_table.csv files
    that predate quality metrics being wired into this script (every
    SV2TTS restoration result scored before this addition). Only
    rewrites the quality columns -- EER/TAR/etc. and results_table_by_group.csv
    are untouched, since those don't need to be recomputed."""
    import pandas as pd

    updated, skipped_no_restored, skipped_no_file, already_has = 0, 0, 0, 0
    for label, out_dir, restored_dir in ALL_KNOWN:
        csv_path = os.path.join(out_dir, "results_table.csv")
        if not os.path.isfile(csv_path):
            skipped_no_file += 1
            continue
        df = pd.read_csv(csv_path)
        if "STOI_mean" in df.columns:
            already_has += 1
            continue
        if not restored_dir:
            skipped_no_restored += 1
            continue
        quality = base.compute_quality_metrics_ungated(restored_dir)
        if quality is None:
            print(f"  [skip] {label}: no quality metrics computable from {restored_dir}")
            continue
        for k, v in quality.items():
            df[k] = v
        df.to_csv(csv_path, index=False)
        print(f"  [backfilled] {label}  STOI={quality['STOI_mean']} PESQ={quality['PESQ_mean']} SI-SDR={quality['SI_SDR_mean_dB']}dB")
        updated += 1

    print(f"\nBackfill complete: {updated} updated, {already_has} already had quality, "
          f"{skipped_no_restored} had no restored_dir, {skipped_no_file} had no results yet.")


def main():
    if "--backfill-quality" in sys.argv:
        backfill_quality()
        return

    if SKIPPED:
        print(f"Skipping {len(SKIPPED)} combination(s) whose downstream cloning isn't complete yet:")
        for label, synth_dir, n, expected in SKIPPED:
            print(f"  [skip] {label}: {n}/{expected}  ({synth_dir})")
        print()

    for label, synth_dir, out_dir, restored_dir in JOBS:
        print(f"\n{'=' * 70}\n{label}  ({synth_dir})\n{'=' * 70}")
        csv_dir = os.path.join(out_dir, "csvs")
        os.makedirs(csv_dir, exist_ok=True)

        base.DATA_LABEL_PREFIXES[label] = "CleanBonafideVsRestoredCloakedSynth"
        base.score_all(label, synth_dir, csv_dir)
        # Quality (STOI/PESQ/SI-SDR) is computed from the *restored*
        # audio (pre-clone, same content as clean_bonafide), never from
        # synth_dir -- see the JOBS docstring above.
        quality = base.compute_quality_metrics_ungated(restored_dir) if restored_dir else None
        base.build_results_table(label, csv_dir, out_dir, quality=quality)
        base.build_group_breakdown(label, csv_dir, out_dir)

    print(f"\nAll {len(JOBS)} restoration protective-efficacy jobs complete.")


if __name__ == "__main__":
    main()
