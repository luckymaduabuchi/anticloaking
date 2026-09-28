#!/usr/bin/env python3
"""Audio-quality comparison between Dataset/clean_bonafide/ (ground
truth) and one of its cloaked versions in Dataset/cloaked_bonafide/
-- i.e. "how much does this cloaking method degrade the audio itself."
Parametrized by method name (POP/protectyouraudio/attackvc/antifake),
mirroring analysis/clean_bonafide_vs_synth.py's --system design.

Unlike clean_bonafide_vs_synth.py (speaker-verification leakage against
TTS-*resynthesized* speech, which has different linguistic content than
the source), every cloaking method here perturbs the *same* recording
rather than resynthesizing it, so it's the same situation as
analysis/audio_quality.py's victim-vs-cloak_output comparison: content
and duration are preserved, so sample-aligned signal-quality metrics
(STOI, PESQ, SI-SDR -- same three functions from analysis/metrics.py,
reused unchanged) are well-defined here, unlike for TTS clones.

Handles the sample-rate mismatch some cloaking methods introduce (POP's
output is 24kHz to match its VITS surrogate; clean_bonafide is 16kHz
throughout) by resampling both sides to 16kHz before scoring -- PESQ in
particular only supports exactly 8kHz or 16kHz, so this isn't optional.

Skips any clean_bonafide entry with no corresponding cloaked output
(still in progress, or permanently excluded, e.g. POP's 3 Whisper-
hallucinated-transcript exclusions) rather than erroring, so this can
be run against a still-running cloak batch and rerun later once more
completes.

Output, under the given --out-dir:
  results_table.csv           overall + per-source STOI/PESQ/SI-SDR
  results_table_by_group.csv  per-descent-x-gender breakdown (FakeAVCeleb subset only)
  plots/quality_bars.png

Run:
    conda run -n antifake2026 python analysis/clean_bonafide_vs_cloak_quality.py \\
        --method POP --out-dir /home/vm-user/Desktop/Antifake2026/results/groundtruthvscloaking/groundtruthvsPOP/gorundtruthvscloaked
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from synth.clean_bonafide_selection import select_all_entries
from analysis.metrics import stoi_score, pesq_score, si_sdr

import librosa
import numpy as np
import pandas as pd

SCORE_SR = 16000  # clean_bonafide's native rate; PESQ only supports 8k/16k

CLOAK_DIRS = {
    "POP": os.path.join(config.RAW_DIR, "cloaked_bonafide", "POP"),
    "protectyouraudio": os.path.join(config.RAW_DIR, "cloaked_bonafide", "ProtectYourAudio"),
    "attackvc": os.path.join(config.RAW_DIR, "cloaked_bonafide", "attackvc"),
    "antifake": os.path.join(config.RAW_DIR, "cloaked_bonafide", "Antifake"),
}

FAKEAVCELEB_GROUPS = [
    "African-men", "African-women",
    "Asian(East)-men", "Asian(East)-women",
    "Asian(South)-men", "Asian(South)-women",
    "Caucasian(American)-men", "Caucasian(American)-women",
    "Caucasian(European)-men", "Caucasian(European)-women",
]


def stem_of(entry):
    return os.path.splitext(os.path.basename(entry["file"]))[0]


def score_all(cloak_dir):
    entries = select_all_entries()
    print(f"{len(entries)} clean_bonafide entries total", flush=True)

    rows = []
    n_missing = 0
    for i, entry in enumerate(entries):
        stem = stem_of(entry)
        cloaked_path = os.path.join(cloak_dir, f"{stem}.wav")
        if not os.path.exists(cloaked_path):
            n_missing += 1
            continue

        clean_wav, _ = librosa.load(entry["file"], sr=SCORE_SR, mono=True)
        cloaked_wav, _ = librosa.load(cloaked_path, sr=SCORE_SR, mono=True)

        row = {
            "stem": stem,
            "source": entry["source"],
            "group": f"{entry['descent']}-{entry['gender']}" if "descent" in entry else "",
        }
        try:
            row["stoi"] = stoi_score(clean_wav, cloaked_wav, SCORE_SR)
        except Exception as e:
            print(f"[warn] STOI failed for {stem}: {e}", flush=True)
            row["stoi"] = np.nan
        try:
            row["pesq"] = pesq_score(clean_wav, cloaked_wav, SCORE_SR)
        except Exception as e:
            print(f"[warn] PESQ failed for {stem}: {e}", flush=True)
            row["pesq"] = np.nan
        try:
            row["sisdr"] = si_sdr(clean_wav, cloaked_wav)
        except Exception as e:
            print(f"[warn] SI-SDR failed for {stem}: {e}", flush=True)
            row["sisdr"] = np.nan
        rows.append(row)

        if (i + 1) % 500 == 0:
            print(f"  scored {i + 1}/{len(entries)}", flush=True)

    print(f"scored {len(rows)}, skipped {n_missing} with no cloaked output", flush=True)
    return pd.DataFrame(rows)


def summarize(df, key_col, key_val, out_rows):
    subset = df if key_col is None else df[df[key_col] == key_val]
    if subset.empty:
        return
    out_rows.append({
        "Data": key_val if key_col else "Overall",
        "STOI_mean": round(float(subset.stoi.mean()), 4),
        "STOI_median": round(float(subset.stoi.median()), 4),
        "PESQ_mean": round(float(subset.pesq.mean()), 4),
        "PESQ_median": round(float(subset.pesq.median()), 4),
        "SI_SDR_mean_dB": round(float(subset.sisdr.mean()), 4),
        "SI_SDR_median_dB": round(float(subset.sisdr.median()), 4),
        "N": len(subset),
    })


def build_tables(df, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    overall_rows = []
    summarize(df, None, None, overall_rows)
    for source in sorted(df.source.unique()):
        summarize(df, "source", source, overall_rows)
    overall_df = pd.DataFrame(overall_rows)
    overall_path = os.path.join(out_dir, "results_table.csv")
    overall_df.to_csv(overall_path, index=False)
    print(f"\nWrote {overall_path}\n")
    print(overall_df.to_string(index=False))

    group_rows = []
    for group in FAKEAVCELEB_GROUPS:
        summarize(df, "group", group, group_rows)
    group_df = pd.DataFrame(group_rows)
    group_path = os.path.join(out_dir, "results_table_by_group.csv")
    group_df.to_csv(group_path, index=False)
    print(f"\nWrote {group_path}\n")
    print(group_df.to_string(index=False))

    return overall_df, group_df


def plot_bars(overall_df, out_path):
    import matplotlib.pyplot as plt

    if overall_df.empty:
        print("No data to plot -- skipping.")
        return

    metrics = [("STOI_mean", "STOI"), ("PESQ_mean", "PESQ"), ("SI_SDR_mean_dB", "SI-SDR (dB)")]
    fig, axes = plt.subplots(1, 3, figsize=(14, 6))
    x = np.arange(len(overall_df))
    for ax, (col, title) in zip(axes, metrics):
        ax.bar(x, overall_df[col])
        ax.set_xticks(x)
        ax.set_xticklabels(overall_df["Data"], rotation=45, ha="right", fontsize=8)
        ax.set_title(title)
        ax.grid(True, axis="y", alpha=0.3)
    fig.suptitle("clean_bonafide vs. cloaked audio quality")
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    print(f"Wrote {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", required=True, choices=list(CLOAK_DIRS.keys()))
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    df = score_all(CLOAK_DIRS[args.method])
    overall_df, group_df = build_tables(df, args.out_dir)
    plot_bars(overall_df, os.path.join(args.out_dir, "plots", "quality_bars.png"))
    print(f"\nAll outputs written under {args.out_dir}")


if __name__ == "__main__":
    main()
