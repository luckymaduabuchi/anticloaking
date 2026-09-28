#!/usr/bin/env python3
"""Scores ProtectYourAudio's restoration study for the 4 techniques whose
restored+recloned audio is already complete on disk (all 3 synthesizers)
but was never scored -- ProtectYourAudio's restoration study was never
run at all (no run_protectyouraudio_all_synths.py existed, unlike POP/
attack-vc/AntiFake). Mirrors run_pop_all_synths.py's pattern exactly.

Scope: adaptive_filter_centroid, ensemble_averaging_perturbed,
mel_spectrogram_inversion, quantization only. lowpass_gain is excluded
here -- its SV2TTS re-cloning is still being completed separately
(run_pya_lowpass_sv2tts.sh); the other 5 techniques (highpass,
re_recording, resampling, second_cloak_noise, spectral_subtraction)
have no restored_synthesize audio at all yet and are out of scope for
this pass.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import restoration_protective_efficacy as r
from analysis import clean_bonafide_vs_synth as base

RESTORED = "/home/vm-user/Desktop/Antifake2026/Dataset/restored_synthesize"
TOTAL = 4850  # ProtectYourAudio's own cloaked-source clip count (not 4864/4867)

# (technique result-folder name, on-disk restored_synthesize dirname, on-disk method-dir casing)
TECHNIQUES = [
    ("adaptive_filter_centroid", "Adaptive_filter_centroid", "ProtectYourAudio"),
    ("ensemble_averaging_perturbed", "ensemble_averaging_perturbed", "protectyouraudio"),
    ("mel_spectrogram_inversion", "Mel_spectrogram", "ProtectYourAudio"),
    ("quantization", "quantization", "ProtectYourAudio"),
]

# Confirmed via on-disk audit (wav count below TOTAL): permanent per-clip
# failure, same pattern as everywhere else in this project.
CEILING_OVERRIDES = {
    "adaptive_filter_centroid_protectyouraudio_f5tts": 4831,
}


def wav_count(d):
    return len([f for f in os.listdir(d) if f.endswith(".wav")]) if os.path.isdir(d) else 0


jobs = []
skipped = []
for technique, dirname, method_dir in TECHNIQUES:
    base_dir = os.path.join(RESTORED, dirname, method_dir)
    restored_dir = r.restoration_root_dir(technique, "ProtectYourAudio")
    for synth in ("sv2tts", "seedvc", "f5tts"):
        synth_dir = os.path.join(base_dir, synth)
        label = f"{technique}_protectyouraudio_{synth}"
        expected = CEILING_OVERRIDES.get(label, TOTAL)
        n = wav_count(synth_dir)
        out_dir = os.path.join(
            r.RESULTS_ROOT, "groundtruthvsprotectyouraudio", "groundtruthvsrestoredsynthesis",
            technique, synth,
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

print(f"Running {len(jobs)} ProtectYourAudio restoration job(s):")
for label, synth_dir, out_dir, restored_dir in jobs:
    print(f"  {label}")

for label, synth_dir, out_dir, restored_dir in jobs:
    print(f"\n{'=' * 70}\n{label}  ({synth_dir})\n{'=' * 70}", flush=True)
    csv_dir = os.path.join(out_dir, "csvs")
    os.makedirs(csv_dir, exist_ok=True)

    base.DATA_LABEL_PREFIXES[label] = "CleanBonafideVsRestoredCloakedSynth"
    base.score_all(label, synth_dir, csv_dir)
    quality = base.compute_quality_metrics_ungated(restored_dir) if restored_dir else None
    base.build_results_table(label, csv_dir, out_dir, quality=quality)
    base.build_group_breakdown(label, csv_dir, out_dir)

print(f"\nAll {len(jobs)} ProtectYourAudio restoration jobs complete.")
