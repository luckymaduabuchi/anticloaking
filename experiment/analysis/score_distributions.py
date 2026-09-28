#!/usr/bin/env python3
"""Score-distribution histograms: target (genuine) vs impostor
cosine-similarity scores, for unprotected/cloaked/restored audio, per
verifier. Mirrors the paper's example_score_distributions_all_models
figure, but built from measured scores instead of drawn to match
target statistics.

Run: python analysis/score_distributions.py
"""
import os
import sys

import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from analysis.common import load_all_csvs

LABEL_NAMES = {1: "target", 0: "impostor"}


def stage_subset(model_df, tag):
    if tag == "baseline":
        return model_df[model_df.dataset == config.BASELINE_LABEL]
    if tag == "cloaked":
        return model_df[(model_df.dataset != config.BASELINE_LABEL) & (model_df.technique == config.RAW_LABEL)]
    return model_df[
        (model_df.dataset != config.BASELINE_LABEL)
        & (model_df.technique != config.RAW_LABEL)
        & (model_df.technique != config.BASELINE_LABEL)
    ]


def main():
    os.makedirs(config.PLOTS_DIR, exist_ok=True)
    df = load_all_csvs(config.CSV_DIR)

    plt.figure(figsize=(10, 7))

    for model in config.VERIFIER_MODELS:
        model_df = df[df.model == model]
        for tag in ["baseline", "cloaked", "restored"]:
            group_df = stage_subset(model_df, tag)
            for label, label_name in LABEL_NAMES.items():
                scores = group_df[group_df.label == label].score
                if scores.empty:
                    continue
                plt.hist(
                    scores, bins=30, histtype="step", density=True, linewidth=1.5,
                    label=f"{model} {label_name} ({tag})",
                )

    plt.xlabel("Cosine similarity score")
    plt.ylabel("Density")
    plt.title("Score distributions: target vs. impostor, per measurement stage")
    plt.legend(fontsize=6, ncol=2)
    plt.tight_layout()

    out_path = os.path.join(config.PLOTS_DIR, "score_distributions.png")
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
