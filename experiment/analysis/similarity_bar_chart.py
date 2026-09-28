#!/usr/bin/env python3
"""Supplementary visualization: mean cosine similarity score per
condition (Baseline, Raw-cloaked, each restoration technique), grouped
by verifier and dataset. The primary results are in results_table.py
(EER / TAR@FAR) -- this is a quick visual sanity check alongside it.

Run: python analysis/similarity_bar_chart.py
"""
import os
import sys

import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from analysis.common import load_all_csvs


def main():
    os.makedirs(config.PLOTS_DIR, exist_ok=True)
    df = load_all_csvs(config.CSV_DIR)

    conditions = [config.BASELINE_LABEL, config.RAW_LABEL] + config.TECHNIQUES
    combos = [(m, d) for m in config.VERIFIER_MODELS for d in config.DATASETS]

    x = np.arange(len(conditions))
    width = 0.8 / len(combos)

    plt.figure(figsize=(16, 7))
    for i, (model, dataset) in enumerate(combos):
        means = []
        for condition in conditions:
            if condition == config.BASELINE_LABEL:
                subset = df[(df.model == model) & (df.dataset == config.BASELINE_LABEL)]
            else:
                subset = df[(df.model == model) & (df.dataset == dataset) & (df.technique == condition)]
            means.append(subset.score.mean() if len(subset) else np.nan)
        plt.bar(x + i * width, means, width, label=f"{model} - {dataset}")

    plt.xticks(x + width * (len(combos) - 1) / 2, conditions, rotation=45, ha="right")
    plt.ylabel("Mean cosine similarity score")
    plt.title("Similarity Scores: Baseline vs. Cloaked vs. Restored")
    plt.legend(fontsize=8, ncol=2)
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()

    out_path = os.path.join(config.PLOTS_DIR, "similarity_bar_chart.png")
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
