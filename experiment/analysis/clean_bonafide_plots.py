#!/usr/bin/env python3
"""ROC curves and score-distribution plots for the clean_bonafide
verifier-calibration metrics (verify/clean_bonafide_metrics.py's CSVs).
Separate from roc_curves.py/score_distributions.py, which are built
around the main experiment's Baseline/Cloaked/Restored structure --
this data is shaped differently (per-corpus, per-descent-gender-group).

Produces:
  - clean_bonafide_roc_corpora.png       ROC + bootstrap 95% confidence bands, LibriSpeech/ASVspoof2021/FakeAVCeleb(overall)
  - clean_bonafide_det_corpora.png       DET curve (FRR vs FAR, normal-deviate axes), same 3 corpora
  - clean_bonafide_dist_corpora.png      score distributions, same 3 corpora
  - clean_bonafide_fakeavceleb_eer_by_group.png   EER bar chart, 10 descent x gender groups

Run: python analysis/clean_bonafide_plots.py
"""
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.metrics import roc_curve

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from analysis.common import load_all_csvs
from analysis.metrics import bootstrap_roc_band

CORPORA = ["LibriSpeech", "ASVspoof2021", "FakeAVCeleb"]
DET_TICK_PERCENTS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 40, 60, 80, 90, 95]
FAKEAVCELEB_GROUPS = [
    "FakeAVCeleb-African-men", "FakeAVCeleb-African-women",
    "FakeAVCeleb-Asian(East)-men", "FakeAVCeleb-Asian(East)-women",
    "FakeAVCeleb-Asian(South)-men", "FakeAVCeleb-Asian(South)-women",
    "FakeAVCeleb-Caucasian(American)-men", "FakeAVCeleb-Caucasian(American)-women",
    "FakeAVCeleb-Caucasian(European)-men", "FakeAVCeleb-Caucasian(European)-women",
]


def load_clean_bonafide():
    df = load_all_csvs(config.CSV_DIR)
    return df[df.dataset == "CleanBonafide"]


def plot_roc_corpora(df, out_path, n_boot=200):
    plt.figure(figsize=(8, 6))
    color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    far_grid = np.logspace(-4, 0, 200)

    for i, model in enumerate(config.VERIFIER_MODELS):
        for j, corpus in enumerate(CORPORA):
            subset = df[(df.model == model) & (df.technique == corpus)]
            if subset.empty:
                continue
            color = color_cycle[i % len(color_cycle)]
            style = ["-", "--", ":"][j]

            median_tar, lo, hi = bootstrap_roc_band(subset.label, subset.score, far_grid, n_boot=n_boot)
            plt.fill_between(far_grid, lo, hi, color=color, alpha=0.12, linewidth=0)
            plt.plot(far_grid, median_tar, style, color=color, label=f"{model} ({corpus})")

    plt.xscale("log")
    plt.xlabel("FAR (log scale)")
    plt.ylabel("TAR")
    plt.ylim(0, 1.02)
    plt.title("Clean-dataset ROC with bootstrap 95% CI bands")
    plt.legend(fontsize=7, ncol=2)
    plt.grid(True, which="both", alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"Wrote {out_path}")


def plot_det_corpora(df, out_path):
    """DET curve: FRR vs FAR on normal-deviate (probit) axes, the
    standard NIST/speaker-verification convention -- makes error
    trade-offs easier to compare than ROC when systems perform
    similarly, since it roughly straightens out ROC's typical curvature.
    """
    plt.figure(figsize=(8, 7))
    color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    tick_vals = [v / 100 for v in DET_TICK_PERCENTS]
    tick_pos = norm.ppf(tick_vals)
    tick_labels = [f"{v:g}" for v in DET_TICK_PERCENTS]

    max_x, max_y = 0.0, 0.0
    for i, model in enumerate(config.VERIFIER_MODELS):
        for j, corpus in enumerate(CORPORA):
            subset = df[(df.model == model) & (df.technique == corpus)]
            if subset.empty:
                continue
            far, tar, _ = roc_curve(subset.label, subset.score)
            frr = 1 - tar
            far_c = np.clip(far, 1e-4, 1 - 1e-4)
            frr_c = np.clip(frr, 1e-4, 1 - 1e-4)
            style = ["-", "--", ":"][j]
            x, y = norm.ppf(far_c), norm.ppf(frr_c)
            plt.plot(x, y, style, color=color_cycle[i % len(color_cycle)], label=f"{model} ({corpus})")
            max_x, max_y = max(max_x, np.nanmax(x)), max(max_y, np.nanmax(y))

    # size the axes to whatever error range the data actually reaches
    # (plus a little padding), instead of a fixed cutoff that clips
    # curves for harder conditions like FakeAVCeleb's near-chance EER
    upper = norm.ppf(min(0.99, norm.cdf(max(max_x, max_y)) + 0.05))
    tick_pos = [t for t in tick_pos if t <= upper]
    tick_labels = tick_labels[: len(tick_pos)]

    plt.xticks(tick_pos, tick_labels)
    plt.yticks(tick_pos, tick_labels)
    plt.xlim(norm.ppf(0.0008), upper)
    plt.ylim(norm.ppf(0.0008), upper)
    plt.xlabel("FAR (%)")
    plt.ylabel("FRR (%)")
    plt.title("Clean-dataset DET curve: LibriSpeech vs ASVspoof2021 vs FakeAVCeleb")
    plt.legend(fontsize=7, ncol=2)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"Wrote {out_path}")


def plot_score_distributions(df, out_path):
    plt.figure(figsize=(10, 7))
    for model in config.VERIFIER_MODELS:
        for corpus in CORPORA:
            subset = df[(df.model == model) & (df.technique == corpus)]
            for label, name in [(1, "genuine"), (0, "impostor")]:
                scores = subset[subset.label == label].score
                if scores.empty:
                    continue
                plt.hist(
                    scores, bins=30, histtype="step", density=True, linewidth=1.3,
                    label=f"{model} {name} ({corpus})",
                )

    plt.xlabel("Cosine similarity score")
    plt.ylabel("Density")
    plt.title("Clean-dataset score distributions: genuine vs impostor")
    plt.legend(fontsize=6, ncol=2)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"Wrote {out_path}")


def plot_fakeavceleb_eer_by_group(df, out_path):
    from analysis.results_table import compute_eer

    rows = []
    for model in config.VERIFIER_MODELS:
        for group in FAKEAVCELEB_GROUPS:
            subset = df[(df.model == model) & (df.technique == group)]
            if subset.empty:
                continue
            far, tar, _ = roc_curve(subset.label, subset.score)
            eer = compute_eer(far, tar)
            label = group.replace("FakeAVCeleb-", "")
            rows.append({"group": label, "model": model, "eer": eer})

    plot_df = pd.DataFrame(rows)
    groups = sorted(plot_df.group.unique())
    x = np.arange(len(groups))
    width = 0.8 / len(config.VERIFIER_MODELS)

    plt.figure(figsize=(12, 6))
    for i, model in enumerate(config.VERIFIER_MODELS):
        vals = [plot_df[(plot_df.group == g) & (plot_df.model == model)].eer.values[0] for g in groups]
        plt.bar(x + i * width, vals, width, label=model)

    plt.xticks(x + width, groups, rotation=45, ha="right")
    plt.ylabel("EER")
    plt.title("FakeAVCeleb: EER by descent x gender group")
    plt.legend()
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"Wrote {out_path}")


def main():
    os.makedirs(config.PLOTS_DIR, exist_ok=True)
    df = load_clean_bonafide()

    plot_roc_corpora(df, os.path.join(config.PLOTS_DIR, "clean_bonafide_roc_corpora.png"))
    plot_det_corpora(df, os.path.join(config.PLOTS_DIR, "clean_bonafide_det_corpora.png"))
    plot_score_distributions(df, os.path.join(config.PLOTS_DIR, "clean_bonafide_dist_corpora.png"))
    plot_fakeavceleb_eer_by_group(df, os.path.join(config.PLOTS_DIR, "clean_bonafide_fakeavceleb_eer_by_group.png"))


if __name__ == "__main__":
    main()
