#!/usr/bin/env python3
"""Runs every attack-vc restoration job (SV2TTS + Seed-VC + F5-TTS,
all 16 technique-variants x 3 synthesizers = up to 48 combinations) in
one process. Deliberately excludes POP/AntiFake (their SV2TTS
restoration results were accidentally deleted alongside attack-vc's
and are being redone separately, later, not in this pass).

Also explicitly adds the 6 low-pass+gain attack-vc SV2TTS jobs, which
restoration_protective_efficacy.py's JOBS list silently drops: that
loop only walks LOWPASS_ATTACKVC_ROOT's *top-level* "gain X.X"
directories, but an external reorganization nested the real SV2TTS
data one level deeper (Low_pass/attackvc/sv2tts/gain X.X/sv2tts/),
so the loop's own directory listing no longer finds them at all --
neither scored nor reported as skipped, just silently absent.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import restoration_protective_efficacy as r
from analysis import clean_bonafide_vs_synth as base

jobs = [j for j in r.JOBS if "attackvc" in j[0]]

LOWPASS_ATTACKVC_ROOT = r.LOWPASS_ATTACKVC_ROOT
for gain in ("1.0", "1.2", "1.4", "1.6", "1.8", "2.0"):
    label = f"lowpass_attackvc_gain{gain}_sv2tts"
    if any(j[0] == label for j in jobs):
        continue
    synth_dir = os.path.join(LOWPASS_ATTACKVC_ROOT, "sv2tts", f"gain {gain}", "sv2tts")
    out_dir = os.path.join(
        r.RESULTS_ROOT, "groundtruthvsattackvc", "groundtruthvsrestoredsynthesis",
        "lowpass_gain", f"gain_{gain}", "sv2tts",
    )
    if not os.path.isdir(synth_dir):
        print(f"[skip] {label}: no dir at {synth_dir}")
        continue
    if r.already_scored(out_dir):
        print(f"[skip] {label}: already scored")
        continue
    restored_dir = r.restoration_root_dir("low_pass", "attackvc", gain)
    jobs.append((label, synth_dir, out_dir, restored_dir))

print(f"Running {len(jobs)} attack-vc job(s) (all synthesizers):")
for label, synth_dir, out_dir, restored_dir in jobs:
    print(f"  {label}")

for label, synth_dir, out_dir, restored_dir in jobs:
    print(f"\n{'=' * 70}\n{label}  ({synth_dir})\n{'=' * 70}")
    csv_dir = os.path.join(out_dir, "csvs")
    os.makedirs(csv_dir, exist_ok=True)

    base.DATA_LABEL_PREFIXES[label] = "CleanBonafideVsRestoredCloakedSynth"
    base.score_all(label, synth_dir, csv_dir)
    quality = base.compute_quality_metrics_ungated(restored_dir) if restored_dir else None
    base.build_results_table(label, csv_dir, out_dir, quality=quality)
    base.build_group_breakdown(label, csv_dir, out_dir)

print(f"\nAll {len(jobs)} attack-vc restoration jobs complete.")
