#!/usr/bin/env python3
"""Runs every paired cluster-bootstrap comparison the paper's protection
and restoration claims rest on, using whatever score files exist:
score CSVs that already carry stem IDs are used as-is; older ones get
their stems recovered with robust_stats.backfill_stems (which validates
the alignment and refuses rather than guesses -- refused conditions are
listed in the output, never silently dropped).

  Part 1  cloaked_vs_ceiling   A = cloaked-source clone, B = clean-audio
          ceiling, same synthesizer. Matched on the clips both cover, so
          the SV2TTS ceiling (originally 1,500 clips) is compared on
          exactly those 1,500 stems.
  Part 2  restoration_vs_baseline   A = restored-then-cloned, B = the
          cloak's no-restoration baseline, same synthesizer. A negative
          EER difference whose whole CI is below zero on all three
          verifiers is the paired 'reversal' criterion.

Outputs (results/paired_stats/): paired_cloaked_vs_ceiling.csv,
paired_restoration_vs_baseline.csv, paired_verdicts.csv,
paired_unmapped.csv.

Run:
    conda run -n antifake2026 python analysis/paired_all.py [--workers 5]
"""
import argparse
import glob
import os
import re
import sys
from multiprocessing import Pool

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis import robust_stats as rs
from analysis import clean_bonafide_vs_synth as base

ROOT = "/home/vm-user/Desktop/Antifake2026"
RESULTS = f"{ROOT}/results"
GT = f"{RESULTS}/groundtruthvscloaking"
CEIL = f"{RESULTS}/groundtruthcomparison/cleanbonafidevscleansynth"
OUT = f"{RESULTS}/paired_stats"
CLOAKED_SYNTH = f"{ROOT}/Dataset/cloaked_synthesize"
CLEAN_SYNTH = f"{ROOT}/Dataset/clean_synthesize"
RESTORED_SYNTH = f"{ROOT}/Dataset/restored_synthesize"
VERIFIERS = list(base.VERIFIERS)
SYNTHS = ("sv2tts", "seedvc", "f5tts")

# method -> (results tree, no-restoration baseline csvs dir per synth, system label per synth,
#            cloaked_synthesize dir per synth)
METHODS = {
    "POP": dict(
        tree="groundtruthvsPOP",
        csvs=lambda s: f"{GT}/groundtruthvsPOP/groundtruthvscloakedsynthesis/{s}/csvs",
        system=lambda s: f"pop_{s}", synth_dir=lambda s: f"{CLOAKED_SYNTH}/POP/{s}"),
    "attackvc": dict(
        tree="groundtruthvsattackvc",
        csvs=lambda s: f"{GT}/groundtruthvsattackvc/groundtruthvscloakedsynthesis/{s}/csvs",
        system=lambda s: f"attackvc_{s}", synth_dir=lambda s: f"{CLOAKED_SYNTH}/attack-vc/{s}"),
    "Antifake": dict(
        tree="groundtruthvsAntifake",
        csvs=lambda s: f"{RESULTS}/cleanbonafidevscleansynth/ANTIFAKE_{ {'sv2tts': 'SV2TTS', 'seedvc': 'SEEDVC', 'f5tts': 'F5TTS'}[s] }/csvs",
        system=lambda s: f"antifake_{s}",
        synth_dir=lambda s: f"{CLOAKED_SYNTH}/Antifake/{'f5tt5' if s == 'f5tts' else s}"),
    "protectyouraudio": dict(
        tree="groundtruthvsprotectyouraudio",
        csvs=lambda s: f"{GT}/groundtruthvsprotectyouraudio/groundtruthvscloakedsynthesis/{s}/csvs",
        system=lambda s: f"protectyouraudio_{s}", synth_dir=lambda s: f"{CLOAKED_SYNTH}/ProtectYourAudio/{s}"),
}
CEILING = {
    "sv2tts": dict(csvs=f"{CEIL}/SV2TTS/csvs", system="sv2tts", synth_dir=f"{CLEAN_SYNTH}/sv2tts"),
    "seedvc": dict(csvs=f"{CEIL}/SEEDVC/csvs", system="seedvc", synth_dir=f"{CLEAN_SYNTH}/seedvc"),
    "f5tts": dict(csvs=f"{CEIL}/F5TTS/csvs", system="f5tts", synth_dir=f"{CLEAN_SYNTH}/f5tts"),
}

_MANIFEST = None


def manifest():
    global _MANIFEST
    if _MANIFEST is None:
        _MANIFEST = base.load_manifest_by_stem()[0]
    return _MANIFEST


def _ceiling_stems_sv2tts_original():
    """The stems the original 1,500-clip clean SV2TTS ceiling was scored
    on (deterministic; same selector the synthesis script used)."""
    from synth.clean_bonafide_selection import select_sv2tts_subset
    return [os.path.splitext(os.path.basename(e["file"]))[0] for e in select_sv2tts_subset()]


def get_trials(csv_path, synth_dir, explicit_stems=None):
    df = pd.read_csv(csv_path)
    if "stem" not in df.columns:
        df = rs.backfill_stems(df, synth_dir, manifest(), stems=explicit_stems)
    return rs.trials_from_df(df, "stem")


def compare(job):
    """job: dict(kind, label, a=dict(csvs, system, synth_dir, [stems]), b=..., n_boot, meta)."""
    rows, eer = [], {}
    try:
        for v in VERIFIERS:
            ta = get_trials(os.path.join(job["a"]["csvs"], f"{job['a']['system']}__{job['a']['system']}__{v}.csv"),
                            job["a"]["synth_dir"], job["a"].get("stems"))
            tb = get_trials(os.path.join(job["b"]["csvs"], f"{job['b']['system']}__{job['b']['system']}__{v}.csv"),
                            job["b"]["synth_dir"], job["b"].get("stems"))
            res = rs.paired_cluster_bootstrap_diff(ta, tb, n_boot=job["n_boot"])
            for metric, r in res.items():
                rows.append({**job["meta"], "verifier": base.MODEL_DISPLAY_NAMES[v], "metric": metric,
                             "n_A": len(ta), "n_B": len(tb), "n_matched": r["n_matched"],
                             "A": round(r["a"], 4), "B": round(r["b"], 4), "A_minus_B": round(r["diff"], 4),
                             "CI95_lo": round(r["lo"], 4), "CI95_hi": round(r["hi"], 4), "p": round(r["p"], 4)})
            eer[v] = res["EER"]
    except (FileNotFoundError, ValueError, KeyError) as e:
        return {"job": job["label"], "meta": job["meta"], "error": f"{type(e).__name__}: {e}"[:300]}
    verdict = rs.protection_verdict(eer) if job["kind"] == "cloaked_vs_ceiling" else rs.reversal_verdict(eer)
    return {"job": job["label"], "meta": job["meta"], "rows": rows, "verdict": verdict}


# ---------------------------------------------------------------------------
# Restoration: map each results folder to the folder of clones it scored
# ---------------------------------------------------------------------------
def _norm(part):
    return re.sub(r"[^a-z0-9.]", "", part.lower())


TECH_TOKENS = {
    "adaptive_filter_centroid": {"adaptivefiltercentroid"},
    "downsampling": {"downsampling", "downsample"},
    "upsampling": {"upsampling", "upsample"},
    "ensemble_averaging_perturbed": {"ensembleaveragingperturbed"},
    "mel_spectrogram_inversion": {"melspectrogram", "melspectrograminversion"},
    "quantization": {"quantization"},
    "re_recording": {"simulatedrerecord", "rerecording"},
    "spectral_subtraction": {"spectralsubtraction"},
    "highpass": {"highpass"},
    "second_cloak_noise": {"secondcloaknoise"},
    "lowpass_gain": {"lowpass"},
}
METHOD_TOKENS = {"POP": {"pop"}, "attackvc": {"attackvc"}, "Antifake": {"antifake"},
                 "protectyouraudio": {"protectyouraudio"}}


def index_restored_synth():
    idx = []
    for dirpath, _dirs, files in os.walk(RESTORED_SYNTH):
        if any(f.endswith(".wav") for f in files):
            rel = os.path.relpath(dirpath, RESTORED_SYNTH).split(os.sep)
            idx.append((dirpath, {_norm(p) for p in rel}))
    return idx


def restoration_jobs(n_boot):
    idx = index_restored_synth()
    jobs, unmapped = [], []
    for method, m in METHODS.items():
        rest_root = f"{GT}/{m['tree']}/groundtruthvsrestoredsynthesis"
        for csv_dir in sorted(glob.glob(f"{rest_root}/**/csvs", recursive=True)):
            parts = os.path.relpath(os.path.dirname(csv_dir), rest_root).split(os.sep)
            technique = parts[0]
            gain = parts[1] if technique == "lowpass_gain" and len(parts) == 3 else None
            synth = parts[-1]
            files = glob.glob(f"{csv_dir}/*__*__SpeechBrain.csv")
            if technique not in TECH_TOKENS or synth not in SYNTHS or not files:
                continue
            label = os.path.basename(files[0]).split("__")[0]
            need = {_norm(synth)} | METHOD_TOKENS[method]
            tech_tok = TECH_TOKENS[technique]
            if gain:
                need.add(_norm(gain))
            cands = [d for d, toks in idx if need <= toks and (toks & tech_tok)]
            meta = {"kind": "restoration_vs_baseline", "method": method, "technique": technique,
                    "gain": gain or "", "synth": synth, "label": label}
            base_cfg = dict(csvs=m["csvs"](synth), system=m["system"](synth), synth_dir=m["synth_dir"](synth))
            if not cands:
                unmapped.append({**meta, "reason": "no matching restored_synthesize folder"})
                continue
            # get_trials() only needs synth_dir as a fallback for CSVs that
            # predate per-row stem IDs (see its "stem" not in df.columns
            # check); a current CSV already carries its own clip identity,
            # so don't gate it behind backfill_stems() validating against a
            # directory listing -- that check requires the block count to
            # exactly equal the folder's file count, which a handful of
            # individually-failed clips (already recorded in this csv's own
            # failures/ log) legitimately breaks even though the CSV itself
            # is perfectly usable.
            score_df = pd.read_csv(files[0])
            if "stem" in score_df.columns:
                chosen = cands[0]  # unused by get_trials when stem is present; any candidate is fine
            else:
                chosen = None
                for cand in cands:
                    try:
                        rs.backfill_stems(score_df, cand, manifest())
                        chosen = cand
                        break
                    except ValueError:
                        continue
                if chosen is None:
                    unmapped.append({**meta, "reason": f"backfill refused for all {len(cands)} candidate folder(s)"})
                    continue
            jobs.append(dict(kind="restoration_vs_baseline", label=label, n_boot=n_boot, meta=meta,
                             a=dict(csvs=csv_dir, system=label, synth_dir=chosen), b=base_cfg))
    return jobs, unmapped


def ceiling_jobs(n_boot):
    jobs = []
    for method, m in METHODS.items():
        for synth in SYNTHS:
            c = dict(CEILING[synth])
            if synth == "sv2tts":  # the original ceiling was scored on a fixed 1,500-clip subset
                c["stems"] = _ceiling_stems_sv2tts_original()
            jobs.append(dict(kind="cloaked_vs_ceiling", label=f"{method}_{synth}", n_boot=n_boot,
                             meta={"kind": "cloaked_vs_ceiling", "method": method, "synth": synth},
                             a=dict(csvs=m["csvs"](synth), system=m["system"](synth), synth_dir=m["synth_dir"](synth)),
                             b=c))
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--n-boot-ceiling", type=int, default=1000)
    ap.add_argument("--n-boot-restoration", type=int, default=300)
    ap.add_argument("--skip-restoration", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    jobs = ceiling_jobs(args.n_boot_ceiling)
    unmapped = []
    if not args.skip_restoration:
        rjobs, unmapped = restoration_jobs(args.n_boot_restoration)
        print(f"{len(rjobs)} restoration conditions mapped, {len(unmapped)} unmapped", flush=True)
        jobs += rjobs

    ceiling_rows, restoration_rows, verdicts, errors = [], [], [], []
    with Pool(args.workers) as pool:
        for i, res in enumerate(pool.imap_unordered(compare, jobs), 1):
            if "error" in res:
                errors.append({**res["meta"], "reason": res["error"]})
                print(f"[{i}/{len(jobs)}] ERROR {res['job']}: {res['error']}", flush=True)
                continue
            (ceiling_rows if res["meta"]["kind"] == "cloaked_vs_ceiling" else restoration_rows).extend(res["rows"])
            verdicts.append({**res["meta"], "paired_EER_verdict": res["verdict"]})
            print(f"[{i}/{len(jobs)}] {res['job']}: {res['verdict']}", flush=True)

    pd.DataFrame(ceiling_rows).to_csv(f"{OUT}/paired_cloaked_vs_ceiling.csv", index=False)
    pd.DataFrame(restoration_rows).to_csv(f"{OUT}/paired_restoration_vs_baseline.csv", index=False)
    pd.DataFrame(verdicts).to_csv(f"{OUT}/paired_verdicts.csv", index=False)
    pd.DataFrame(unmapped + errors).to_csv(f"{OUT}/paired_unmapped.csv", index=False)
    print(f"\nWrote results to {OUT}  ({len(verdicts)} ok, {len(unmapped)} unmapped, {len(errors)} errors)")


if __name__ == "__main__":
    main()
