#!/usr/bin/env python3
"""Sanity-checks the delay estimator on real clips.

For a few clips per condition, shifts the processed signal by a scan of
lags around the estimate and prints STOI / SI-SDR at each, so it is
visible whether the estimated lag really is the best alignment (and
whether STOI, which compares envelopes, agrees with SI-SDR, which
compares waveforms). Also lists clips whose estimated delay sits at the
edge of the search window, with their correlation peak and how much
better that lag is than lag 0 -- the signature of a false peak.

Run:
    conda run -n antifake2026 python analysis/alignment_diagnose.py
"""
import glob
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from analysis import metrics as M
from analysis import clean_bonafide_vs_synth as base
from analysis.alignment_check import CONDITIONS, SR

import librosa

by_stem, _ = base.load_manifest_by_stem()
rng = random.Random(3)


def load_pair(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    ref, _ = librosa.load(by_stem[stem]["file"], sr=SR, mono=True)
    deg, _ = librosa.load(path, sr=SR, mono=True)
    return stem, ref, deg


def ratio_to_lag0(ref, deg, delay):
    nfft = 1 << int(np.ceil(np.log2(len(ref) + len(deg))))
    cc = np.fft.irfft(np.conj(np.fft.rfft(ref, nfft)) * np.fft.rfft(deg, nfft), nfft)
    return abs(cc[int(round(delay)) % nfft]) / (abs(cc[0]) + 1e-12)


def scan(name, path):
    stem, ref, deg = load_pair(path)
    delay, peak = M.estimate_delay(ref, deg)
    print(f"\n{name}  {stem}: estimated delay {delay:.2f} samples, peak {peak:.3f}, "
          f"|cc(lag)|/|cc(0)| = {ratio_to_lag0(ref, deg, delay):.2f}")
    for lag in (0, delay - 20, delay - 5, delay - 1, delay, delay + 1, delay + 5, delay + 20):
        d2 = M._advance(deg, lag)
        trim = int(np.ceil(abs(lag))) + 1
        n = min(len(ref), len(d2))
        r, d = ref[trim:n - trim], d2[trim:n - trim]
        M.ALIGN_MODE = "truncate"
        print(f"   applied lag {lag:9.2f}   STOI {M.stoi_score(r, d, SR):.3f}   SI-SDR {M.si_sdr(r, d):7.2f} dB")
    M.ALIGN_MODE = "delay"


for name in ("ProtectYourAudio (cloak)", "attack-vc (cloak)", "POP + mel inversion"):
    files = sorted(glob.glob(os.path.join(CONDITIONS[name], "*.wav")))
    scan(name, rng.choice(files))

print("\n\nAntiFake: clips whose estimated delay is large")
files = sorted(glob.glob(os.path.join(CONDITIONS["AntiFake (cloak)"], "*.wav")))
shown = 0
delays = []
for f in rng.sample(files, 150):
    stem, ref, deg = load_pair(f)
    delay, peak = M.estimate_delay(ref, deg)
    delays.append(delay)
    if abs(delay) > 1000 and shown < 6:
        print(f"   {stem}: delay {delay:8.1f}  peak {peak:.3f}  |cc(lag)|/|cc(0)| {ratio_to_lag0(ref, deg, delay):.2f}")
        shown += 1
d = np.abs(np.array(delays))
print(f"   |delay| percentiles 50/75/90/95/99: {np.percentile(d, [50, 75, 90, 95, 99]).round(1)}; "
      f"share above 1000: {(d > 1000).mean():.2f}")
