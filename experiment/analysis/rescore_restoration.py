#!/usr/bin/env python3
"""Re-scores every restoration-study condition (restored-then-cloned audio
vs. the clean original) so its score CSVs carry stem / trial / ref_stem
columns and a failures/ log, and its results tables use attainable
low-FAR TAR + cluster-bootstrap CIs (see clean_bonafide_vs_synth.py and
robust_stats.py).

Each results folder is mapped to the folder of clones it scored by
matching folder-name tokens (technique, cloak method, synthesizer, gain)
under Dataset/restored_synthesize. Ambiguous or missing mappings are
logged and skipped, never guessed silently. The conditions that the paired
analysis could not match (paired_unmapped.csv: F5-TTS, plus a few SV2TTS)
are scored first.

The quality columns (STOI/PESQ/SI-SDR) of each existing results_table.csv
are carried over untouched (recompute_quality_aligned.py owns those).
Resumable: a condition whose three CSVs already have IDs and whose table
already has CI_method is skipped. Several shards can run side by side.

Run:
    conda run -n antifake2026 python analysis/rescore_restoration.py --shard 0/2
    conda run -n antifake2026 python analysis/rescore_restoration.py --shard 1/2
"""
import argparse
import glob
import os
import sys
import time
import traceback

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis import clean_bonafide_vs_synth as base
from analysis import paired_all as pa

QCOLS = ["STOI_mean", "STOI_median", "PESQ_mean", "PESQ_median", "SI_SDR_mean_dB",
         "SI_SDR_median_dB", "SI_SDR_valid_share", "quality_N", "quality_alignment"]


def wav_count(d):
    return sum(1 for f in os.listdir(d) if f.endswith(".wav"))


def discover():
    idx = pa.index_restored_synth()
    conds, unmapped = [], []
    for method, m in pa.METHODS.items():
        rest_root = f"{pa.GT}/{m['tree']}/groundtruthvsrestoredsynthesis"
        for csv_dir in sorted(glob.glob(f"{rest_root}/**/csvs", recursive=True)):
            parts = os.path.relpath(os.path.dirname(csv_dir), rest_root).split(os.sep)
            technique = parts[0]
            gain = parts[1] if technique == "lowpass_gain" and len(parts) == 3 else None
            synth = parts[-1]
            files = glob.glob(f"{csv_dir}/*__*__SpeechBrain.csv")
            if technique not in pa.TECH_TOKENS or synth not in pa.SYNTHS or not files:
                continue
            label = os.path.basename(files[0]).split("__")[0]
            need = {pa._norm(synth)} | pa.METHOD_TOKENS[method]
            if gain:
                need.add(pa._norm(gain))
            cands = [d for d, toks in idx if need <= toks and (toks & pa.TECH_TOKENS[technique])]
            meta = dict(label=label, method=method, technique=technique, gain=gain or "", synth=synth,
                        csv_dir=csv_dir, out_dir=os.path.dirname(csv_dir))
            if not cands:
                unmapped.append({**meta, "reason": "no matching restored_synthesize folder"})
                continue
            if len(cands) > 1:
                # prefer the fullest folder; record that we had to choose
                cands.sort(key=lambda d: -wav_count(d))
                meta["note"] = f"{len(cands)} candidates, chose {cands[0]}"
            conds.append({**meta, "synth_dir": cands[0]})
    return conds, unmapped


def priority_labels():
    p = f"{pa.OUT}/paired_unmapped.csv"
    if not os.path.isfile(p):
        return set()
    u = pd.read_csv(p)
    return set(u["label"].dropna())


def is_done(c):
    files = glob.glob(f"{c['csv_dir']}/*__*__*.csv")
    if len(files) != 3 or not all(base.csv_current(f) for f in files):
        return False
    t = os.path.join(c["out_dir"], "results_table.csv")
    return os.path.isfile(t) and "CI_method" in pd.read_csv(t, nrows=1).columns


def run_one(c):
    label, csv_dir, out_dir = c["label"], c["csv_dir"], c["out_dir"]
    table = os.path.join(out_dir, "results_table.csv")
    old = pd.read_csv(table) if os.path.isfile(table) else None
    quality = None
    if old is not None and "STOI_mean" in old.columns:
        quality = {k: old.iloc[0][k] for k in QCOLS if k in old.columns}
    base.DATA_LABEL_PREFIXES[label] = "CleanBonafideVsRestoredCloakedSynth"
    base.score_all(label, c["synth_dir"], csv_dir)
    # re-read quality right before writing the table: recompute_quality_aligned.py
    # may have updated it while this condition was being scored
    if os.path.isfile(table):
        cur = pd.read_csv(table)
        if "STOI_mean" in cur.columns:
            quality = {k: cur.iloc[0][k] for k in QCOLS if k in cur.columns}
    base.build_results_table(label, csv_dir, out_dir, quality=quality)
    base.build_group_breakdown(label, csv_dir, out_dir)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", default="0/1", help="k/n: process every n-th condition starting at k")
    args = ap.parse_args()
    k, n = map(int, args.shard.split("/"))

    conds, unmapped = discover()
    first = priority_labels()
    conds.sort(key=lambda c: (c["label"] not in first, c["method"], c["technique"], c["gain"], c["synth"]))
    if k == 0:
        pd.DataFrame(unmapped).to_csv(f"{pa.OUT}/rescore_restoration_unmapped.csv", index=False)
    mine = conds[k::n]
    print(f"shard {k}/{n}: {len(mine)} of {len(conds)} conditions ({len(unmapped)} unmapped overall)", flush=True)

    ok, failed = 0, []
    for i, c in enumerate(mine, 1):
        if is_done(c):
            print(f"[{i}/{len(mine)}] already done: {c['label']}", flush=True)
            continue
        t0 = time.time()
        print(f"[{i}/{len(mine)}] {c['label']}  <- {c['synth_dir']}" + (f"   NOTE {c['note']}" if "note" in c else ""),
              flush=True)
        try:
            run_one(c)
            ok += 1
            print(f"[{i}/{len(mine)}] done in {(time.time() - t0) / 60:.1f} min", flush=True)
        except Exception as e:
            failed.append((c["label"], repr(e)))
            print(f"[{i}/{len(mine)}] FAILED {c['label']}: {e}", flush=True)
            traceback.print_exc()
    open(f"/tmp/rescore_restoration_shard_{k}.done", "w").write(f"{ok} ok, {len(failed)} failed\n")
    print(f"\nshard {k}/{n} finished: {ok} rescored, {len(failed)} failed", flush=True)
    for label, err in failed:
        print(f"  FAILED {label}: {err}")


if __name__ == "__main__":
    main()
