"""Shared CSV-loading helpers for the analysis scripts. Reads only the
real score,label CSVs produced by verify/run_all.py -- nothing here
generates or simulates data.
"""
import glob
import os

import pandas as pd


def load_all_csvs(csv_dir):
    """Returns a single long dataframe with columns:
    dataset, technique, model, score, label
    """
    rows = []
    for path in sorted(glob.glob(os.path.join(csv_dir, "*.csv"))):
        base = os.path.basename(path)[: -len(".csv")]
        dataset, technique, model = base.split("__")
        df = pd.read_csv(path)
        df["dataset"] = dataset
        df["technique"] = technique
        df["model"] = model
        rows.append(df)

    if not rows:
        raise FileNotFoundError(f"No CSVs found in {csv_dir}. Run verify/run_all.py first.")
    return pd.concat(rows, ignore_index=True)
