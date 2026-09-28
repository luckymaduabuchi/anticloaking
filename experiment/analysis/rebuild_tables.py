#!/usr/bin/env python3
"""Rebuilds results_table.csv / results_table_by_group.csv (attainable
low-FAR TAR + false-accept counts, cluster-bootstrap CIs) for every
primary condition whose score CSVs already carry the trial-ID columns but
whose table was written by the older code (no CI_method column).

Needed because rescoring runs as one Python process per condition, and
the conditions scored before the new table code went in wrote old-style
tables. The STOI/PESQ/SI-SDR columns are carried over from the existing
table unchanged (they don't depend on the score CSVs).

Skips conditions whose CSVs still lack IDs (e.g. the restoration study,
which was scored before IDs existed -- those keep the legacy score-level
CIs and interpolated low-FAR values until they are rescored).

Run:
    conda run -n antifake2026 python analysis/rebuild_tables.py
"""
import glob
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis import clean_bonafide_vs_synth as base

RESULTS = "/home/vm-user/Desktop/Antifake2026/results"
QUALITY_COLS = ["STOI_mean", "STOI_median", "PESQ_mean", "PESQ_median",
                "SI_SDR_mean_dB", "SI_SDR_median_dB", "quality_N"]


def main():
    csv_dirs = sorted(d for d in glob.glob(os.path.join(RESULTS, "**", "csvs"), recursive=True)
                      if "groundtruthvsrestoredsynthesis" not in d)
    for csv_dir in csv_dirs:
        out_dir = os.path.dirname(csv_dir)
        files = sorted(glob.glob(os.path.join(csv_dir, "*__*__*.csv")))
        systems = {os.path.basename(f).split("__")[0] for f in files}
        if len(systems) != 1 or list(systems)[0] not in base.DATA_LABEL_PREFIXES:
            continue  # not a primary-condition dir (e.g. clean-vs-clean calibration)
        system = list(systems)[0]
        if len(files) != 3 or not all(base.csv_current(f) for f in files):
            print(f"[skip] {csv_dir}: score CSVs lack trial IDs")
            continue
        table = os.path.join(out_dir, "results_table.csv")
        old = pd.read_csv(table) if os.path.exists(table) else None
        if old is not None and "CI_method" in old.columns:
            print(f"[ok]   {csv_dir}: table already up to date")
            continue
        quality = None
        if old is not None and all(c in old.columns for c in QUALITY_COLS):
            quality = old.iloc[0][QUALITY_COLS].to_dict()
        print(f"[rebuild] {system}: {out_dir}")
        base.build_results_table(system, csv_dir, out_dir, quality=quality)
        base.build_group_breakdown(system, csv_dir, out_dir)


if __name__ == "__main__":
    main()
