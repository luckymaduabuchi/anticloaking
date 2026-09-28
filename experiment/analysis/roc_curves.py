#!/usr/bin/env python3
"""Full threshold-sweep ROC curves (TAR vs FAR, log-scale FAR axis),
per verifier, comparing all three measurement stages: unprotected
Baseline, cloaked-only (Raw, no restoration attempted), and
cloaked-then-restored (all 10 restoration techniques pooled). No such
threshold-sweep generator existed anywhere in the prior pipeline --
only fixed single-threshold metrics did -- so this is new.

Run: python analysis/roc_curves.py
"""
import os
import sys

import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from analysis.common import load_all_csvs

STAGE_STYLES = {"baseline": "-", "cloaked": ":", "restored": "--"}


def main():
    os.makedirs(config.PLOTS_DIR, exist_ok=True)
    df = load_all_csvs(config.CSV_DIR)

    plt.figure(figsize=(8, 6))
    color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    for i, model in enumerate(config.VERIFIER_MODELS):
        model_df = df[df.model == model]

        baseline = model_df[model_df.dataset == config.BASELINE_LABEL]
        cloaked = model_df[(model_df.dataset != config.BASELINE_LABEL) & (model_df.technique == config.RAW_LABEL)]
        restored = model_df[
            (model_df.dataset != config.BASELINE_LABEL)
            & (model_df.technique != config.RAW_LABEL)
            & (model_df.technique != config.BASELINE_LABEL)
        ]

        for group_df, tag in [(baseline, "baseline"), (cloaked, "cloaked"), (restored, "restored")]:
            if group_df.empty:
                continue
            far, tar, _ = roc_curve(group_df.label, group_df.score)
            far = far.clip(min=1e-4)  # keep log-scale x-axis finite
            plt.plot(
                far, tar, STAGE_STYLES[tag], color=color_cycle[i % len(color_cycle)],
                label=f"{model} ({tag})",
            )

    plt.xscale("log")
    plt.xlabel("FAR (log scale)")
    plt.ylabel("TAR")
    plt.ylim(0, 1.02)
    plt.title("ROC: unprotected vs. cloaked vs. cloaked+restored audio")
    plt.legend(fontsize=8)
    plt.grid(True, which="both", alpha=0.3)
    plt.tight_layout()

    out_path = os.path.join(config.PLOTS_DIR, "roc_curves.png")
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
