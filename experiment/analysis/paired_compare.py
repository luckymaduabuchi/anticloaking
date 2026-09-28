#!/usr/bin/env python3
"""Paired cluster-bootstrap comparison of two conditions scored on the
same clips (see robust_stats.py for the method and why).

For each verifier: keeps only clips (stems) with a genuine trial in BOTH
conditions, resamples those clips with all their trials (the same
resample for both conditions), and reports metric(A) - metric(B) with a
95% CI and bootstrap p-value. Also prints the matched-clip count so
unequal clip sets are visible instead of silently ignored.

Two ways to run it:

1. Preset -- every cloaked-source cloning condition vs. its clean-audio
   ceiling (A = cloaked, B = ceiling, so a positive EER difference means
   the cloak raised EER, i.e. protection):
       python analysis/paired_compare.py --preset cloaked_vs_ceiling

2. Any two conditions (e.g. restored vs. no-restoration baseline, A =
   restored, B = baseline; a negative EER difference whose whole CI is
   below zero on every verifier is the paired 'reversal' test):
       python analysis/paired_compare.py \\
           --a-csvs <dir> --a-system <name> --b-csvs <dir> --b-system <name>
   Score files from before the ID columns existed can be used by adding
   --a-synth-dir / --b-synth-dir (the directory that was scored); stems
   are then recovered by robust_stats.backfill_stems, which refuses when
   it cannot validate the alignment.
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis import robust_stats as rs
from analysis import clean_bonafide_vs_synth as base

RESULTS = "/home/vm-user/Desktop/Antifake2026/results"
GT = os.path.join(RESULTS, "groundtruthvscloaking")
CEIL = os.path.join(RESULTS, "groundtruthcomparison", "cleanbonafidevscleansynth")
VERIFIER_NAMES = list(base.VERIFIERS)  # SpeechBrain, Resemblyzer, WavLM

# (label, system, csvs dir) for each cloaked-source condition, and the
# clean ceiling (system, csvs dir) it is compared against.
CEILING = {
    "sv2tts": ("sv2tts", os.path.join(CEIL, "SV2TTS", "csvs")),
    "seedvc": ("seedvc", os.path.join(CEIL, "SEEDVC", "csvs")),
    "f5tts": ("f5tts", os.path.join(CEIL, "F5TTS", "csvs")),
}


def _cloaked_conditions():
    out = []
    for method, tree in (("pop", "groundtruthvsPOP"), ("attackvc", "groundtruthvsattackvc"),
                         ("protectyouraudio", "groundtruthvsprotectyouraudio")):
        for synth in ("sv2tts", "seedvc", "f5tts"):
            out.append((f"{method}_{synth}", f"{method}_{synth}", synth,
                        os.path.join(GT, tree, "groundtruthvscloakedsynthesis", synth, "csvs")))
    for synth, up in (("sv2tts", "SV2TTS"), ("seedvc", "SEEDVC"), ("f5tts", "F5TTS")):
        out.append((f"antifake_{synth}", f"antifake_{synth}", synth,
                    os.path.join(RESULTS, "cleanbonafidevscleansynth", f"ANTIFAKE_{up}", "csvs")))
    return out


def load_condition(csvs_dir, system, verifier, cluster_by, synth_dir=None, manifest=None, speaker_of=None):
    path = os.path.join(csvs_dir, f"{system}__{system}__{verifier}.csv")
    if synth_dir is not None:
        df = rs.backfill_stems(path, synth_dir, manifest)
        tmp = path + ".backfilled.tmp.csv"
        df.to_csv(tmp, index=False)
        try:
            return rs.load_trials(tmp, cluster_by, speaker_of)
        finally:
            os.remove(tmp)
    return rs.load_trials(path, cluster_by, speaker_of)


def compare(label, a, b, cluster_by, n_boot, speaker_of=None, manifest=None):
    """a, b: dicts with csvs_dir, system, optional synth_dir."""
    rows = []
    per_verifier_eer = {}
    for v in VERIFIER_NAMES:
        ta = load_condition(a["csvs_dir"], a["system"], v, cluster_by, a.get("synth_dir"), manifest, speaker_of)
        tb = load_condition(b["csvs_dir"], b["system"], v, cluster_by, b.get("synth_dir"), manifest, speaker_of)
        res = rs.paired_cluster_bootstrap_diff(ta, tb, n_boot=n_boot)
        for metric, r in res.items():
            rows.append({
                "comparison": label, "verifier": base.MODEL_DISPLAY_NAMES[v], "metric": metric,
                "n_clusters_A": len(ta), "n_clusters_B": len(tb), "n_matched": r["n_matched"],
                "A": round(r["a"], 4), "B": round(r["b"], 4), "A_minus_B": round(r["diff"], 4),
                "CI95_lo": round(r["lo"], 4), "CI95_hi": round(r["hi"], 4), "p": round(r["p"], 4),
                "cluster_by": cluster_by,
            })
        per_verifier_eer[v] = res["EER"]
    return rows, rs.reversal_verdict(per_verifier_eer)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", choices=["cloaked_vs_ceiling"])
    ap.add_argument("--a-csvs"); ap.add_argument("--a-system"); ap.add_argument("--a-synth-dir")
    ap.add_argument("--b-csvs"); ap.add_argument("--b-system"); ap.add_argument("--b-synth-dir")
    ap.add_argument("--label", default="A vs B")
    ap.add_argument("--cluster-by", choices=["stem", "speaker"], default="stem")
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--out", help="write the result table to this CSV")
    args = ap.parse_args()

    by_stem, _ = base.load_manifest_by_stem()
    speaker_of = {s: e["speaker_id"] for s, e in by_stem.items()} if args.cluster_by == "speaker" else None

    jobs = []
    if args.preset == "cloaked_vs_ceiling":
        for label, system, synth, csvs in _cloaked_conditions():
            csys, cdir = CEILING[synth]
            jobs.append((f"{label} vs clean {synth} ceiling",
                         {"csvs_dir": csvs, "system": system}, {"csvs_dir": cdir, "system": csys}))
    else:
        if not (args.a_csvs and args.a_system and args.b_csvs and args.b_system):
            ap.error("give --preset, or all of --a-csvs/--a-system/--b-csvs/--b-system")
        jobs.append((args.label,
                     {"csvs_dir": args.a_csvs, "system": args.a_system, "synth_dir": args.a_synth_dir},
                     {"csvs_dir": args.b_csvs, "system": args.b_system, "synth_dir": args.b_synth_dir}))

    all_rows = []
    for label, a, b in jobs:
        try:
            rows, verdict = compare(label, a, b, args.cluster_by, args.n_boot, speaker_of, by_stem)
        except (FileNotFoundError, ValueError) as e:
            print(f"[skip] {label}: {e}")
            continue
        all_rows.extend(rows)
        print(f"\n== {label}   (paired EER verdict A<B: {verdict})")
        print(pd.DataFrame(rows).drop(columns=["comparison", "cluster_by"]).to_string(index=False))

    if args.out and all_rows:
        pd.DataFrame(all_rows).to_csv(args.out, index=False)
        print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
