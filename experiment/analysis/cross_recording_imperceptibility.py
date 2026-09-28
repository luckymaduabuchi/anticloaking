#!/usr/bin/env python3
"""Imperceptibility, tested the way a verifier is really used.

The original imperceptibility test compares each cloaked clip to the
recording it was made from (same words, room, microphone), which nearly any
verifier passes. Here the genuine trial is instead a DIFFERENT recording of
the same speaker; the 10 impostor trials are unchanged (per-clip seeded,
identical to the main test's impostors). The identical trials are also run
with the UNCLOAKED clip as the query, giving the baseline that any
cross-recording test needs:

    query  = cloaked clip i    vs  other recording of speaker i   (genuine)
                                vs  10 other speakers' recordings  (impostor)
    baseline: same trials with the clean original of clip i as the query.

A cloak is imperceptible to a verifier if its cross-recording scores are no
worse than the baseline on the same clips: --analyze reports the paired
cluster-bootstrap difference in EER / TAR@1% (cloaked minus clean; a
positive EER difference means the cloak made the speaker harder to verify).

Only speakers with at least two recordings can be tested. Results are
reported per source corpus because FakeAVCeleb's cross-recording baseline is
already near chance (it cannot show much), while LibriSpeech and ASVspoof
can.

Score files: results/crossrecording/<set>/csvs/<set>__<set>__<Verifier>.csv
(same columns as every other score file: stem/trial/ref_stem IDs, per-clip
impostor sampling), where <set> is clean, POP, attackvc, Antifake or
protectyouraudio.

Run:
    conda run -n antifake2026 python analysis/cross_recording_imperceptibility.py --score
    conda run -n antifake2026 python analysis/cross_recording_imperceptibility.py --analyze
"""
import argparse
import glob
import os
import random
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from analysis import clean_bonafide_vs_synth as base
from analysis import robust_stats as rs

OUT = "/home/vm-user/Desktop/Antifake2026/results/crossrecording"
SETS = {
    "clean": None,  # the clean originals themselves
    "POP": base.SYSTEM_DIRS["POP"],
    "attackvc": base.SYSTEM_DIRS["attackvc"],
    "Antifake": base.SYSTEM_DIRS["antifake"],
    "protectyouraudio": base.SYSTEM_DIRS["protectyouraudio"],
}
SOURCES = {"librispeech": "LibriSpeech", "asvspoof": "ASVspoof2021", "fakeavceleb": "FakeAVCeleb"}


def trial_plan(by_stem, by_speaker):
    """Per stem: (other recording of the same speaker, [10 impostor files]).
    Impostors come from the same per-clip generator as the main test, so a
    clip has the same impostors here as in every other condition."""
    speakers = list(by_speaker.keys())
    plan = {}
    for stem, e in by_stem.items():
        others = sorted(f for f in by_speaker[e["speaker_id"]] if f != e["file"])
        if not others:
            continue  # single-recording speaker: no cross-recording genuine trial
        genuine_ref = random.Random(f"{base.SEED}:cross:{stem}").choice(others)
        rng = random.Random(f"{base.SEED}:{stem}")
        other_spk = [s for s in speakers if s != e["speaker_id"]]
        imps = [rng.choice(by_speaker[s]) for s in rng.sample(other_spk, min(base.IMPOSTORS_PER_CLIP, len(other_spk)))]
        plan[stem] = (genuine_ref, imps)
    return plan


def score_set(name, src_dir, by_stem, plan):
    csv_dir = f"{OUT}/{name}/csvs"
    stems = sorted(plan)
    if src_dir is not None:
        stems = [s for s in stems if os.path.exists(f"{src_dir}/{s}.wav")]
    print(f"{name}: {len(stems)} clips with a cross-recording genuine trial", flush=True)
    for model_name, module in base.VERIFIERS.items():
        path = f"{csv_dir}/{name}__{name}__{model_name}.csv"
        if os.path.exists(path) and base.csv_current(path):
            print(f"  [skip] {model_name}: already scored", flush=True)
            continue
        cache = base.EmbeddingCache(module)
        rows, failures = [], []
        for j, stem in enumerate(stems):
            e = by_stem[stem]
            query = e["file"] if src_dir is None else f"{src_dir}/{stem}.wav"
            group = f"{e['descent']}-{e['gender']}" if "descent" in e else ""
            genuine_ref, imps = plan[stem]
            trials = [("genuine", genuine_ref, 1)] + [(f"impostor_{k}", f, 0) for k, f in enumerate(imps, 1)]
            for trial, ref, label in trials:
                try:
                    score = cache.similarity(query, ref)
                except Exception as ex:
                    failures.append((stem, trial, base._stem(ref), str(ex)[:200]))
                    continue
                rows.append((f"{score:.6f}", label, group, stem, trial, base._stem(ref), base.SAMPLING_TAG))
            if (j + 1) % 500 == 0:
                print(f"  {model_name}: {j + 1}/{len(stems)}", flush=True)
                try:
                    import torch
                    torch.cuda.empty_cache()
                except Exception:
                    pass
        base.write_csv(path, rows)
        base.write_failures(path, failures)
        print(f"  wrote {path} ({len(rows)} rows, {len(failures)} failures)", flush=True)


def analyze(n_boot):
    base_trials = {v: rs.load_trials(f"{OUT}/clean/csvs/clean__clean__{v}.csv") for v in base.VERIFIERS}
    out_rows = []
    for name in ("POP", "attackvc", "Antifake", "protectyouraudio"):
        for src_prefix, src_name in SOURCES.items():
            for v in base.VERIFIERS:
                try:
                    a = rs.load_trials(f"{OUT}/{name}/csvs/{name}__{name}__{v}.csv")
                except FileNotFoundError:
                    continue
                b = base_trials[v]
                keep = lambda t: t.restrict([i for i in t.ids if str(i).startswith(src_prefix + "_")])
                a_s, b_s = keep(a), keep(b)
                if len(a_s) == 0 or len(b_s) == 0:
                    continue
                for metric, r in rs.paired_cluster_bootstrap_diff(a_s, b_s, n_boot=n_boot).items():
                    out_rows.append({"cloak": name, "source": src_name, "verifier": base.MODEL_DISPLAY_NAMES[v],
                                     "metric": metric, "n_clips": r["n_matched"],
                                     "cloaked": round(r["a"], 4), "clean_baseline": round(r["b"], 4),
                                     "cloaked_minus_clean": round(r["diff"], 4),
                                     "CI95_lo": round(r["lo"], 4), "CI95_hi": round(r["hi"], 4), "p": round(r["p"], 4)})
    df = pd.DataFrame(out_rows)
    os.makedirs(OUT, exist_ok=True)
    df.to_csv(f"{OUT}/summary.csv", index=False)
    pd.set_option("display.width", 220, "display.max_rows", 400)
    print(df[df.metric == "EER"].to_string(index=False))
    print(f"\nWrote {OUT}/summary.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--only", nargs="*", help="sets to score (default: all)")
    ap.add_argument("--n-boot", type=int, default=1000)
    args = ap.parse_args()
    if not (args.score or args.analyze):
        ap.error("give --score and/or --analyze")

    if args.score:
        by_stem, by_speaker = base.load_manifest_by_stem()
        plan = trial_plan(by_stem, by_speaker)
        print(f"{len(plan)} of {len(by_stem)} clips have a same-speaker recording to compare against", flush=True)
        for name, src in SETS.items():
            if args.only and name not in args.only:
                continue
            score_set(name, src, by_stem, plan)
    if args.analyze:
        analyze(args.n_boot)


if __name__ == "__main__":
    main()
