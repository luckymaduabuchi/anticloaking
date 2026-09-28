#!/usr/bin/env python3
"""Recomputes STOI / PESQ / SI-SDR with delay-corrected alignment
(metrics.align_signals) for every restoration condition and, optionally,
the cloak-level imperceptibility tables, and updates the quality columns
in the existing results_table.csv files in place.

Quality depends only on (original, restored/cloaked audio), not on the
downstream synthesizer, so it is computed once per (cloak method,
technique[, gain]) and written into that condition's three synthesizer
tables. The previous (truncation-only) values are kept in
results/quality_alignment_comparison.csv, and each updated table gets a
quality_alignment column so the two conventions can't be mixed up.

Run:
    conda run -n antifake2026 python analysis/recompute_quality_aligned.py [--workers 4] [--include-cloak]
"""
import argparse
import os
import sys
from multiprocessing import Pool

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis import clean_bonafide_vs_synth as base
from analysis import restoration_protective_efficacy as r

RESULTS = "/home/vm-user/Desktop/Antifake2026/results"
GT = f"{RESULTS}/groundtruthvscloaking"
DATASET = "/home/vm-user/Desktop/Antifake2026/Dataset"
QCOLS = ["STOI_mean", "STOI_median", "PESQ_mean", "PESQ_median",
         "SI_SDR_mean_dB", "SI_SDR_median_dB", "SI_SDR_valid_share", "quality_N"]
TREES = {"POP": "groundtruthvsPOP", "attackvc": "groundtruthvsattackvc", "Antifake": "groundtruthvsAntifake"}
TECHNIQUES = ["adaptive_filter_centroid", "downsampling", "upsampling", "ensemble_averaging_perturbed",
              "mel_spectrogram_inversion", "quantization", "re_recording", "spectral_subtraction",
              "highpass", "second_cloak_noise"]
GAINS = ["1.0", "1.2", "1.4", "1.6", "1.8", "2.0"]
SYNTHS = ["sv2tts", "seedvc", "f5tts"]
CLOAK_TABLES = {  # cloak-level imperceptibility tables (audio = cloaked_bonafide dir)
    "POP": (f"{DATASET}/cloaked_bonafide/POP", f"{GT}/groundtruthvsPOP/gorundtruthvscloaked"),
    "attackvc": (f"{DATASET}/cloaked_bonafide/attackvc", f"{GT}/groundtruthvsattackvc/groundtruthvscloaked"),
    "protectyouraudio": (f"{DATASET}/cloaked_bonafide/ProtectYourAudio",
                         f"{GT}/groundtruthvsprotectyouraudio/groundtruthvscloaked"),
    "antifake": (f"{DATASET}/cloaked_bonafide/Antifake", f"{RESULTS}/cleanbonafidevscleansynth/ANTIFAKE"),
}


def build_jobs(include_cloak):
    jobs = []  # (key, audio_dir, [table dirs])
    for method, tree in TREES.items():
        root = f"{GT}/{tree}/groundtruthvsrestoredsynthesis"
        for tech in TECHNIQUES:
            jobs.append((f"{method}/{tech}", r.restoration_root_dir(tech, method),
                         [f"{root}/{tech}/{s}" for s in SYNTHS]))
        for g in GAINS:
            jobs.append((f"{method}/lowpass_gain_{g}", r.restoration_root_dir("lowpass_gain", method, g),
                         [f"{root}/lowpass_gain/gain_{g}/{s}" for s in SYNTHS]))
    if include_cloak:
        for name, (audio, table_dir) in CLOAK_TABLES.items():
            jobs.append((f"cloak/{name}", audio, [table_dir]))
    return jobs


def compute(job):
    key, audio_dir, _tables = job
    if not os.path.isdir(audio_dir):
        return key, None, f"missing audio dir {audio_dir}"
    q = base.compute_quality_metrics_ungated(audio_dir)
    return key, q, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only-cloak", action="store_true",
                    help="only the 4 cloak-level tables (implies --include-cloak)")
    ap.add_argument("--include-cloak", action="store_true",
                    help="also update the 4 cloak-level imperceptibility tables (run only after "
                         "rescore_with_ids.sh has finished, since that rewrites those tables)")
    args = ap.parse_args()

    jobs = build_jobs(args.include_cloak or args.only_cloak)
    if args.only_cloak:
        jobs = [j for j in jobs if j[0].startswith("cloak/")]
    by_key = {j[0]: j for j in jobs}
    comparison = []
    with Pool(args.workers) as pool:
        for i, (key, q, err) in enumerate(pool.imap_unordered(compute, jobs), 1):
            if q is None:
                print(f"[{i}/{len(jobs)}] SKIP {key}: {err or 'no quality computed'}", flush=True)
                continue
            for tdir in by_key[key][2]:
                path = os.path.join(tdir, "results_table.csv")
                if not os.path.isfile(path):
                    continue
                df = pd.read_csv(path)
                old = df.iloc[0][[c for c in QCOLS if c in df.columns]].to_dict()
                comparison.append({"condition": key, "table": tdir.replace(RESULTS + "/", ""),
                                   **{f"old_{k}": v for k, v in old.items()},
                                   **{f"new_{k}": v for k, v in q.items()}})
                for k, v in q.items():
                    df[k] = v
                df["quality_alignment"] = "delay-corrected"
                df.to_csv(path, index=False)
            print(f"[{i}/{len(jobs)}] {key}: STOI {q['STOI_mean']}  PESQ {q['PESQ_mean']}  "
                  f"SI-SDR {q['SI_SDR_mean_dB']} dB  (n={q['quality_N']})", flush=True)

    pd.DataFrame(comparison).to_csv(f"{RESULTS}/quality_alignment_comparison.csv", index=False)
    print(f"\nWrote {RESULTS}/quality_alignment_comparison.csv ({len(comparison)} tables updated)")


if __name__ == "__main__":
    main()
