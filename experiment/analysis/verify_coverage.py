#!/usr/bin/env python3
"""Reports which conditions are fully migrated to the ID-bearing,
robust-statistics format, and which are not.

For every primary condition and every restoration condition: do all three
score CSVs carry stem/trial/ref_stem, does the results table carry the
cluster-CI / false-accept-count columns (CI_method), and (restoration and
cloak-level tables) has the quality been recomputed with delay alignment.
Prints a summary and lists every condition that is not fully done.

Run:
    conda run -n antifake2026 python analysis/verify_coverage.py
"""
import glob
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis import clean_bonafide_vs_synth as base

RESULTS = "/home/vm-user/Desktop/Antifake2026/results"


def check(csv_dir, need_quality):
    problems = []
    files = glob.glob(f"{csv_dir}/*__*__*.csv")
    if len(files) != 3:
        problems.append(f"{len(files)} score CSVs")
    elif not all(base.csv_current(f) for f in files):
        problems.append("score CSVs lack IDs")
    table = os.path.join(os.path.dirname(csv_dir), "results_table.csv")
    if not os.path.isfile(table):
        problems.append("no results_table.csv")
    else:
        cols = pd.read_csv(table, nrows=1).columns
        if "CI_method" not in cols:
            problems.append("table not rebuilt (no CI_method)")
        if need_quality and "quality_alignment" not in cols:
            problems.append("quality not delay-aligned")
    return problems


def main():
    rows = []
    for d in sorted(glob.glob(f"{RESULTS}/**/csvs", recursive=True)):
        if "/failures" in d:
            continue
        files = glob.glob(f"{d}/*__*__SpeechBrain.csv")
        if not files:
            continue
        system = os.path.basename(files[0]).split("__")[0]
        restoration = "groundtruthvsrestoredsynthesis" in d
        cloak_level = system in base.CONTENT_PRESERVING_SYSTEMS
        if not restoration and system not in base.DATA_LABEL_PREFIXES:
            continue  # e.g. the clean-vs-clean calibration set, out of scope
        problems = check(d, need_quality=restoration or cloak_level)
        rows.append({"kind": "restoration" if restoration else "primary", "system": system,
                     "dir": d.replace(RESULTS + "/", ""), "problems": "; ".join(problems)})
    df = pd.DataFrame(rows)
    done = (df.problems == "").sum()
    print(f"{done} of {len(df)} conditions fully migrated "
          f"(primary {((df.kind == 'primary') & (df.problems == '')).sum()}/{(df.kind == 'primary').sum()}, "
          f"restoration {((df.kind == 'restoration') & (df.problems == '')).sum()}/{(df.kind == 'restoration').sum()})")
    todo = df[df.problems != ""]
    if len(todo):
        print("\nNOT fully done:")
        print(todo[["kind", "system", "problems"]].to_string(index=False))


if __name__ == "__main__":
    main()
