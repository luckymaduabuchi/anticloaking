#!/usr/bin/env python3
"""Fill in the missing SB-ECAPA/LibriSpeech row of the clean_bonafide-vs-itself
calibration table (results/groundtruthcomparison/cleanbonafide/).

CleanBonafide__LibriSpeech__SpeechBrain.csv never existed -- Resemblyzer and
WavLM were both scored against LibriSpeech during the original calibration
pass, but SpeechBrain was not. This reconstructs the exact same genuine/
impostor pairs (same seed, same call order) via clean_bonafide_metrics'
own pairing functions, then scores them with verify_speechbrain and writes
the CSV in the same format/location the original pass would have used.

Reproducibility check: rerunning build_genuine_pairs/build_impostor_pairs
with seed=123 reproduces the exact LibriSpeech pair counts (434 genuine /
1500 impostor) already reported in the existing results_table.csv. A
Resemblyzer re-score of these reconstructed pairs was compared against the
existing CleanBonafide__LibriSpeech__Resemblyzer.csv: pair-for-pair identical
labels/ordering, scores differing only in the 4th-5th decimal (e.g.
0.922259 vs 0.922219), consistent with CPU-vs-GPU floating-point
nondeterminism rather than a pairing/methodology error.

Run (CPU-only, to match the environment this was validated under):
    CUDA_VISIBLE_DEVICES="" LD_LIBRARY_PATH=/home/vm-user/anaconda3/envs/antifake2026/lib:$LD_LIBRARY_PATH \
    conda run -n antifake2026 python verify/compute_librispeech_speechbrain_calibration.py
"""
import csv
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from verify.clean_bonafide_metrics import (
    load_entries,
    build_genuine_pairs,
    build_impostor_pairs,
    EmbeddingCache,
)
from verify import verify_speechbrain

OUT_PATH = os.path.join(
    "/home/vm-user/Desktop/Antifake2026/results/groundtruthcomparison/cleanbonafide",
    "verify", "csvs", "CleanBonafide__LibriSpeech__SpeechBrain.csv",
)


def main():
    rng = random.Random(123)
    entries = load_entries()
    genuine = build_genuine_pairs(entries, rng)
    impostor = build_impostor_pairs(entries, rng)
    print("LibriSpeech genuine pairs:", len(genuine["LibriSpeech"]), flush=True)
    print("LibriSpeech impostor pairs:", len(impostor["LibriSpeech"]), flush=True)

    cache = EmbeddingCache(verify_speechbrain)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["score", "label"])

        n = 0
        for a, b in genuine["LibriSpeech"]:
            w.writerow([f"{cache.similarity(a, b):.6f}", 1])
            n += 1
            if n % 100 == 0:
                print(f"  genuine {n}/{len(genuine['LibriSpeech'])}", flush=True)
        print("genuine scored", flush=True)

        n = 0
        for a, b in impostor["LibriSpeech"]:
            w.writerow([f"{cache.similarity(a, b):.6f}", 0])
            n += 1
            if n % 200 == 0:
                print(f"  impostor {n}/{len(impostor['LibriSpeech'])}", flush=True)
        print("impostor scored", flush=True)

    print("Wrote", OUT_PATH, flush=True)


if __name__ == "__main__":
    main()
