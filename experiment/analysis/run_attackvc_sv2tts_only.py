#!/usr/bin/env python3
"""Runs only the attack-vc SV2TTS restoration jobs from
restoration_protective_efficacy.py's JOBS list, deliberately skipping
POP/AntiFake (their SV2TTS restoration results were accidentally
deleted alongside attack-vc's and are being redone separately, later,
not in this pass -- see conversation history)."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import restoration_protective_efficacy as r
from analysis import clean_bonafide_vs_synth as base

jobs = [j for j in r.JOBS if "attackvc" in j[0] and j[0].endswith("_sv2tts")]
print(f"Running {len(jobs)} attack-vc SV2TTS job(s):")
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

print(f"\nAll {len(jobs)} attack-vc SV2TTS restoration jobs complete.")
