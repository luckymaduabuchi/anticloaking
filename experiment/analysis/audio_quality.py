#!/usr/bin/env python3
"""Audio-quality metrics (STOI, PESQ, SI-SDR) for the cloak/restore
pipeline: how much does cloaking, and then restoration, degrade the
audio relative to the original victim recording?

Unlike results_table.py/clean_bonafide_vs_synth.py (speaker-verification
leakage: does the clone still sound like the victim to a verifier),
this measures signal-level quality/intelligibility loss, and therefore
only applies where content is preserved between reference and degraded
signal:
  Data = <Dataset>/Raw            victim vs. cloaked-only, no restoration
  Data = <Dataset>/<Technique>    victim vs. cloaked-then-restored

It deliberately does NOT cover TTS-cloned speech (Baseline or any
synthesized clip) -- those use different linguistic content than the
victim's own recording, so STOI/PESQ/SI-SDR (which require sample-level
alignment of the *same* utterance) are undefined there. See
analysis/metrics.py's module docstring and README.md's Metrics section.

Requires purify/run_all.py to have been run first (purify_output/ is
where the <Dataset>/<Raw|Technique>/<utt_id>.wav files this script
reads come from).

Run:
    conda run -n antifake2026 python analysis/audio_quality.py
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from purify.common import load_wav
from analysis.metrics import stoi_score, pesq_score, si_sdr

CONDITIONS = [config.RAW_LABEL] + config.TECHNIQUES


def load_victims():
    """utt_id -> waveform, for every real victim recording."""
    victims = {}
    for path in sorted(glob.glob(os.path.join(config.VICTIM_DIR, "*.wav"))):
        utt_id = os.path.splitext(os.path.basename(path))[0]
        victims[utt_id] = load_wav(path, config.SAMPLE_RATE)
    return victims


def score_condition(dataset, label, victims):
    cond_dir = os.path.join(config.PURIFY_DIR, label, dataset)
    files = sorted(glob.glob(os.path.join(cond_dir, "*.wav")))

    stois, pesqs, sisdrs = [], [], []
    for path in files:
        utt_id = os.path.splitext(os.path.basename(path))[0]
        reference = victims.get(utt_id)
        if reference is None:
            continue
        degraded = load_wav(path, config.SAMPLE_RATE)

        try:
            stois.append(stoi_score(reference, degraded, config.SAMPLE_RATE))
        except Exception as e:
            print(f"[warn] STOI failed for {dataset}/{label}/{utt_id}: {e}")
        try:
            pesqs.append(pesq_score(reference, degraded, config.SAMPLE_RATE))
        except Exception as e:
            print(f"[warn] PESQ failed for {dataset}/{label}/{utt_id}: {e}")
        try:
            sisdrs.append(si_sdr(reference, degraded))
        except Exception as e:
            print(f"[warn] SI-SDR failed for {dataset}/{label}/{utt_id}: {e}")

    return stois, pesqs, sisdrs


def build_table():
    victims = load_victims()
    if not victims:
        print(f"[warn] no victim recordings found in {config.VICTIM_DIR} -- nothing to score")
        return pd.DataFrame()

    rows = []
    for dataset in config.DATASETS:
        for label in CONDITIONS:
            stois, pesqs, sisdrs = score_condition(dataset, label, victims)
            if not stois and not pesqs and not sisdrs:
                continue
            rows.append({
                "Data": f"{dataset}/{label}",
                "STOI_mean": round(float(np.mean(stois)), 4) if stois else float("nan"),
                "STOI_median": round(float(np.median(stois)), 4) if stois else float("nan"),
                "PESQ_mean": round(float(np.mean(pesqs)), 4) if pesqs else float("nan"),
                "PESQ_median": round(float(np.median(pesqs)), 4) if pesqs else float("nan"),
                "SI_SDR_mean_dB": round(float(np.mean(sisdrs)), 4) if sisdrs else float("nan"),
                "SI_SDR_median_dB": round(float(np.median(sisdrs)), 4) if sisdrs else float("nan"),
                "N": len(stois),
            })

    result_df = pd.DataFrame(rows)
    os.makedirs(config.ANALYSIS_DIR, exist_ok=True)
    out_csv = os.path.join(config.ANALYSIS_DIR, "audio_quality_table.csv")
    result_df.to_csv(out_csv, index=False)
    print(f"\nWrote {out_csv}\n")
    print(result_df.to_string(index=False))
    return result_df


def plot_quality_bars(result_df, out_path):
    import matplotlib.pyplot as plt

    if result_df.empty:
        print("No audio-quality data to plot -- skipping.")
        return

    metrics = [("STOI_mean", "STOI"), ("PESQ_mean", "PESQ"), ("SI_SDR_mean_dB", "SI-SDR (dB)")]
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    x = np.arange(len(result_df))
    for ax, (col, title) in zip(axes, metrics):
        ax.bar(x, result_df[col])
        ax.set_xticks(x)
        ax.set_xticklabels(result_df["Data"], rotation=75, ha="right", fontsize=7)
        ax.set_title(title)
        ax.grid(True, axis="y", alpha=0.3)
    fig.suptitle("Audio quality vs. victim original: cloaked-only and cloaked+restored")
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    print(f"Wrote {out_path}")


def main():
    result_df = build_table()
    plot_quality_bars(result_df, os.path.join(config.PLOTS_DIR, "audio_quality.png"))


if __name__ == "__main__":
    main()
