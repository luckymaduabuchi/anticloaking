#!/usr/bin/env python3
"""Primary results table: EER, TAR@fixed-FAR, minDCF, and score-separation
metrics per (Data, SV) condition.

  Data  SV  EER  EER_CI95  TAR@1%  TAR@1%_CI95  TAR@0.1%  TAR@0.01%
       minDCF  d_prime  overlap_coef  ROC_AUC  pAUC@1%FAR  pAUC@0.1%FAR
       target_mean  target_median  impostor_mean  impostor_median  #T/#I

Data is one of: Baseline, <Dataset>/Raw, <Dataset>/<Technique>.
SV is one of: SB-ECAPA, Resemblyzer, WavLM.
EER and TAR@FAR are computed from the full ROC curve (sklearn roc_curve)
over that condition's pooled real (measured, not simulated) target and
impostor scores. minDCF cost parameters (P_target/C_miss/C_fa) and the
partial-AUC FAR ranges are defined in analysis/metrics.py.

ROC_AUC (full) is supplementary only -- it weights the high-FAR region
heavily and can look excellent even when the security-relevant FAR<1%
region is weak, so it should not be read as the main evidence of
identity leakage on its own. pAUC@1%FAR / pAUC@0.1%FAR are the more
meaningful summaries for that reason; pAUC@0.1%FAR is noisier wherever
#I is small (see the pAUC@0.1%FAR column's inline note).

Not included here (need a reference-vs-processed audio pair or a
baseline-to-compare-against structure that doesn't exist yet for the
clean-dataset calibration -- see README.md): STOI/PESQ/MOS/SI-SDR,
ΔTAR@1%FAR, ΔEER. C_llr (calibration) is skipped -- this project
evaluates discrimination/leakage, not calibrated decision probabilities.

Run: python analysis/results_table.py
"""
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from analysis.common import load_all_csvs
from analysis.metrics import min_dcf, d_prime, overlap_coefficient, partial_auc, full_roc_auc, bootstrap_ci

MODEL_DISPLAY_NAMES = {
    "SpeechBrain": "SB-ECAPA",
    "Resemblyzer": "Resemblyzer",
    "WavLM": "WavLM",
}


def condition_name(dataset, technique):
    if dataset == config.BASELINE_LABEL and technique == config.BASELINE_LABEL:
        return config.BASELINE_LABEL
    return f"{dataset}/{technique}"


def compute_eer(far, tar):
    fnr = 1 - tar
    # nearest crossover of FAR and FNR curves as the EER estimate
    idx = np.nanargmin(np.abs(fnr - far))
    return float((far[idx] + fnr[idx]) / 2)


def tar_at_far(far, tar, target_far):
    order = np.argsort(far)
    return float(np.interp(target_far, far[order], tar[order]))


def _eer_metric_fn(labels, scores):
    far, tar, _ = roc_curve(labels, scores)
    return compute_eer(far, tar)


def _tar_at_1pct_metric_fn(labels, scores):
    far, tar, _ = roc_curve(labels, scores)
    return tar_at_far(far, tar, 0.01)


def main():
    os.makedirs(config.ANALYSIS_DIR, exist_ok=True)
    df = load_all_csvs(config.CSV_DIR)

    rows = []
    for (dataset, technique, model), subset in df.groupby(["dataset", "technique", "model"]):
        labels = subset.label.to_numpy()
        scores = subset.score.to_numpy()
        n_target = int(np.sum(labels == 1))
        n_impostor = int(np.sum(labels == 0))

        if n_target == 0 or n_impostor == 0:
            continue

        far, tar, _ = roc_curve(labels, scores)
        eer = compute_eer(far, tar)
        tar_far = {fp: tar_at_far(far, tar, fp) for fp in config.FAR_OPERATING_POINTS}

        eer_lo, eer_hi = bootstrap_ci(labels, scores, _eer_metric_fn)
        tar1_lo, tar1_hi = bootstrap_ci(labels, scores, _tar_at_1pct_metric_fn)

        target_scores = scores[labels == 1]
        impostor_scores = scores[labels == 0]

        rows.append({
            "Data": condition_name(dataset, technique),
            "SV": MODEL_DISPLAY_NAMES.get(model, model),
            "EER": round(eer, 4),
            "EER_CI95": f"[{eer_lo:.4f}, {eer_hi:.4f}]",
            "TAR@1%": round(tar_far[0.01], 4),
            "TAR@1%_CI95": f"[{tar1_lo:.4f}, {tar1_hi:.4f}]",
            "TAR@0.1%": round(tar_far[0.001], 4),
            "TAR@0.01%": round(tar_far[0.0001], 4),
            "minDCF": round(min_dcf(labels, scores), 4),
            "d_prime": round(d_prime(labels, scores), 4),
            "overlap_coef": round(overlap_coefficient(labels, scores), 4),
            "ROC_AUC": round(full_roc_auc(labels, scores), 4),
            "pAUC@1%FAR": round(partial_auc(labels, scores, far_max=0.01), 4),
            # noisier at low #I (e.g. 400 for a single FakeAVCeleb group ->
            # only ~0.4 expected false accepts at FAR=0.1%); read alongside #T/#I
            "pAUC@0.1%FAR": round(partial_auc(labels, scores, far_max=0.001), 4),
            "target_mean": round(float(target_scores.mean()), 4),
            "target_median": round(float(np.median(target_scores)), 4),
            "impostor_mean": round(float(impostor_scores.mean()), 4),
            "impostor_median": round(float(np.median(impostor_scores)), 4),
            "#T/#I": f"{n_target}/{n_impostor}",
        })

    result_df = pd.DataFrame(rows)
    dataset_order = [config.BASELINE_LABEL] + [
        condition_name(d, t) for d in config.DATASETS for t in [config.RAW_LABEL] + config.TECHNIQUES
    ]
    result_df["_order"] = result_df["Data"].apply(lambda d: dataset_order.index(d) if d in dataset_order else 999)
    result_df = result_df.sort_values(["_order", "SV"]).drop(columns="_order")

    out_csv = os.path.join(config.ANALYSIS_DIR, "results_table.csv")
    result_df.to_csv(out_csv, index=False)
    print(f"Wrote {out_csv}\n")
    print(result_df.to_string(index=False))


if __name__ == "__main__":
    main()
