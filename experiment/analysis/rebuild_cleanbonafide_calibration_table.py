#!/usr/bin/env python3
"""Insert the previously-missing CleanBonafide/LibriSpeech, SB-ECAPA row
into results/groundtruthcomparison/cleanbonafide/analysis/results_table.csv,
computed from the newly-scored
CleanBonafide__LibriSpeech__SpeechBrain.csv (see
verify/compute_librispeech_speechbrain_calibration.py) using the exact
same EER/TAR/minDCF/d-prime/etc. formulas as analysis/results_table.py.

Does NOT regenerate the whole table via results_table.py's own CSV-
directory scan: two rows in the existing table (CleanSynthesize/f5tts
and CleanSynthesize/sv2tts, both N=8) have no source CSV anywhere under
this project's results/ tree, so they must have been merged in from a
separate small calibration run elsewhere -- a directory-scan rebuild
would silently drop them. Confirmed via `find results -iname
'*CleanSynthesize*'` returning nothing. Instead, this only computes and
splices in the one missing row, leaving all 44 existing rows untouched
(verified below).

Run:
    LD_LIBRARY_PATH=/home/vm-user/anaconda3/envs/antifake2026/lib:$LD_LIBRARY_PATH \
    conda run -n antifake2026 python analysis/rebuild_cleanbonafide_calibration_table.py
"""
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from analysis.metrics import min_dcf, d_prime, overlap_coefficient, partial_auc, full_roc_auc, bootstrap_ci
from analysis.results_table import compute_eer, tar_at_far, _eer_metric_fn, _tar_at_1pct_metric_fn

CLEANBONAFIDE_ROOT = "/home/vm-user/Desktop/Antifake2026/results/groundtruthcomparison/cleanbonafide"
NEW_CSV = os.path.join(CLEANBONAFIDE_ROOT, "verify", "csvs", "CleanBonafide__LibriSpeech__SpeechBrain.csv")
REAL_TABLE = os.path.join(CLEANBONAFIDE_ROOT, "analysis", "results_table.csv")

NEW_DATA, NEW_SV = "CleanBonafide/LibriSpeech", "SB-ECAPA"
# splice right before this row -- alphabetically, within the SB-ECAPA
# block, "CleanBonafide/LibriSpeech" sorts here (matches how every other
# row in this table was ordered: groupby(["dataset","technique","model"]))
INSERT_BEFORE = ("CleanSynthesize/f5tts", "SB-ECAPA")


def compute_row():
    df = pd.read_csv(NEW_CSV)
    labels = df.label.to_numpy()
    scores = df.score.to_numpy()
    n_target, n_impostor = int((labels == 1).sum()), int((labels == 0).sum())

    far, tar, _ = roc_curve(labels, scores)
    eer = compute_eer(far, tar)
    tar_far = {fp: tar_at_far(far, tar, fp) for fp in config.FAR_OPERATING_POINTS}
    eer_lo, eer_hi = bootstrap_ci(labels, scores, _eer_metric_fn)
    tar1_lo, tar1_hi = bootstrap_ci(labels, scores, _tar_at_1pct_metric_fn)
    target_scores, impostor_scores = scores[labels == 1], scores[labels == 0]

    return {
        "Data": NEW_DATA,
        "SV": NEW_SV,
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
        "pAUC@0.1%FAR": round(partial_auc(labels, scores, far_max=0.001), 4),
        "target_mean": round(float(target_scores.mean()), 4),
        "target_median": round(float(np.median(target_scores)), 4),
        "impostor_mean": round(float(impostor_scores.mean()), 4),
        "impostor_median": round(float(np.median(impostor_scores)), 4),
        "#T/#I": f"{n_target}/{n_impostor}",
    }


def main():
    new_row = compute_row()
    print("Computed row:")
    print(pd.Series(new_row))

    old_df = pd.read_csv(REAL_TABLE)
    if ((old_df.Data == NEW_DATA) & (old_df.SV == NEW_SV)).any():
        print(f"\n{NEW_DATA}/{NEW_SV} already present -- aborting, nothing to insert.")
        return

    insert_pos = old_df.index[(old_df.Data == INSERT_BEFORE[0]) & (old_df.SV == INSERT_BEFORE[1])]
    if len(insert_pos) != 1:
        print(f"\nCouldn't find unique insertion anchor {INSERT_BEFORE} -- aborting.")
        return
    pos = insert_pos[0]

    new_df = pd.concat([
        old_df.iloc[:pos],
        pd.DataFrame([new_row]),
        old_df.iloc[pos:],
    ], ignore_index=True)

    # Verify every pre-existing row is untouched.
    old_indexed = old_df.set_index(["Data", "SV"])
    new_indexed = new_df.set_index(["Data", "SV"])
    mismatches = [idx for idx in old_indexed.index if not old_indexed.loc[idx].equals(new_indexed.loc[idx])]
    if mismatches:
        print("\nUNEXPECTED: existing rows changed:", mismatches, "-- not writing.")
        return

    new_df.to_csv(REAL_TABLE, index=False)
    print(f"\nWrote {REAL_TABLE} ({len(new_df)} rows, was {len(old_df)})")


if __name__ == "__main__":
    main()
