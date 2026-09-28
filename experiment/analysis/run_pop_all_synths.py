#!/usr/bin/env python3
"""Runs every POP restoration job (SV2TTS + Seed-VC + F5-TTS, all 16
technique-variants x 3 synthesizers = 48 combinations) in one process.
Mirrors run_attackvc_all_synths.py. POP's SV2TTS restoration results
were accidentally deleted alongside attack-vc's (see conversation
history) and were never scored for Seed-VC/F5-TTS at all, so every one
of these 48 is being scored fresh. Unlike attack-vc's Low_pass tree,
POP's on-disk directory layout is clean (no reorganization) --
confirmed via on-disk audit before writing this script.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import restoration_protective_efficacy as r
from analysis import clean_bonafide_vs_synth as base

RESTORED = "/home/vm-user/Desktop/Antifake2026/Dataset/restored_synthesize"
TOTAL = 4864

# (technique result-folder name, on-disk restored_synthesize dirname) --
# same mapping restoration_protective_efficacy.py's OTHER_TECHNIQUES
# already uses, reused here for consistency.
TECHNIQUES = [
    ("adaptive_filter_centroid", "Adaptive_filter_centroid"),
    ("downsampling", "Downsampling"),
    ("upsampling", "Upsampling"),
    ("ensemble_averaging_perturbed", "ensemble_averaging_perturbed"),
    ("mel_spectrogram_inversion", "Mel_spectrogram"),
    ("quantization", "quantization"),
    ("re_recording", "SimulatedReRecord"),
    ("spectral_subtraction", "SpectralSubtraction"),
    ("highpass", "Highpass"),
    ("second_cloak_noise", "Second_cloak_noise"),
]

# Confirmed via on-disk audit: a handful of combinations stabilized a
# few clips short of 4864 after retries -- same permanent-failure
# pattern as everywhere else in this project.
CEILING_OVERRIDES = {
    "adaptive_filter_centroid_pop_f5tts": 4852,
    "downsampling_pop_f5tts": 4862,
    "upsampling_pop_sv2tts": 4838,
    "re_recording_pop_f5tts": 4863,
    "highpass_pop_f5tts": 4863,
    "second_cloak_noise_pop_sv2tts": 4777,
    "lowpass_pop_gain1.6_f5tts": 4863,
    "lowpass_pop_gain1.8_f5tts": 4863,
    "lowpass_pop_gain1.8_sv2tts": 4862,
    "lowpass_pop_gain2.0_f5tts": 4863,
    "lowpass_pop_gain2.0_sv2tts": 4849,
}


def wav_count(d):
    return len([f for f in os.listdir(d) if f.endswith(".wav")]) if os.path.isdir(d) else 0


jobs = []
skipped = []
for technique, dirname in TECHNIQUES:
    base_dir = os.path.join(RESTORED, dirname, "POP")
    restored_dir = r.restoration_root_dir(technique, "POP")
    for synth in ("sv2tts", "seedvc", "f5tts"):
        synth_dir = os.path.join(base_dir, synth)
        label = f"{technique}_pop_{synth}"
        expected = CEILING_OVERRIDES.get(label, TOTAL)
        n = wav_count(synth_dir)
        out_dir = os.path.join(
            r.RESULTS_ROOT, "groundtruthvsPOP", "groundtruthvsrestoredsynthesis",
            technique, synth,
        )
        if n < expected:
            skipped.append((label, synth_dir, n, expected))
            continue
        if r.already_scored(out_dir):
            continue
        jobs.append((label, synth_dir, out_dir, restored_dir))

for gain in ("1.0", "1.2", "1.4", "1.6", "1.8", "2.0"):
    restored_dir = r.restoration_root_dir("low_pass", "POP", gain)
    for synth in ("sv2tts", "seedvc", "f5tts"):
        synth_dir = os.path.join(RESTORED, "Low_pass", "POP", f"gain_{gain}", synth)
        label = f"lowpass_pop_gain{gain}_{synth}"
        expected = CEILING_OVERRIDES.get(label, TOTAL)
        n = wav_count(synth_dir)
        out_dir = os.path.join(
            r.RESULTS_ROOT, "groundtruthvsPOP", "groundtruthvsrestoredsynthesis",
            "lowpass_gain", f"gain_{gain}", synth,
        )
        if n < expected:
            skipped.append((label, synth_dir, n, expected))
            continue
        if r.already_scored(out_dir):
            continue
        jobs.append((label, synth_dir, out_dir, restored_dir))

if skipped:
    print(f"Skipping {len(skipped)} combination(s) below their expected ceiling:")
    for label, synth_dir, n, expected in skipped:
        print(f"  [skip] {label}: {n}/{expected}  ({synth_dir})")
    print()

print(f"Running {len(jobs)} POP job(s) (all synthesizers):")
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

print(f"\nAll {len(jobs)} POP restoration jobs complete.")
