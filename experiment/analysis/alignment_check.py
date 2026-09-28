#!/usr/bin/env python3
"""How much does delay alignment change the quality metrics?

1. Synthetic check: shift a real clip by a known fractional delay and make
   sure metrics.estimate_delay recovers it and SI-SDR recovers after
   correction.
2. Real audio: for a random sample of clips from each cloaking method and
   from several restoration techniques, report the estimated delay (how
   often and by how much the cloaked/restored clip is offset from its
   original) and STOI / PESQ / SI-SDR under the old truncation-only
   alignment vs. delay-corrected alignment.

Run:
    conda run -n antifake2026 python analysis/alignment_check.py [--num-clips 100]
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
from analysis import metrics as M
from analysis import clean_bonafide_vs_synth as base

SR = base.QUALITY_SCORE_SR
DATASET = os.path.join(config.RAW_DIR)
CONDITIONS = {
    "POP (cloak)": f"{DATASET}/cloaked_bonafide/POP",
    "attack-vc (cloak)": f"{DATASET}/cloaked_bonafide/attackvc",
    "AntiFake (cloak)": f"{DATASET}/cloaked_bonafide/Antifake",
    "ProtectYourAudio (cloak)": f"{DATASET}/cloaked_bonafide/ProtectYourAudio",
    "POP + downsampling": f"{DATASET}/restoration techniques/resampling/POP/downsample",
    "POP + re-recording": f"{DATASET}/restoration techniques/re_recording/POP",
    "POP + mel inversion": f"{DATASET}/restoration techniques/mel_spectrogram_inversion/POP",
    "attack-vc + re-recording": f"{DATASET}/restoration techniques/re_recording/attackvc",
}


def synthetic_check():
    import librosa
    x, _ = librosa.load(glob.glob(f"{DATASET}/clean_bonafide/librispeech/*.flac")[0], sr=SR, mono=True)
    for true_delay in (0.0, 5.0, 37.3, -12.6, 250.0):
        y = M._advance(x, -true_delay)  # y lags x by true_delay samples
        est, peak = M.estimate_delay(x, y)
        M.ALIGN_MODE = "truncate"
        sd_old = M.si_sdr(x, y)
        M.ALIGN_MODE = "delay"
        sd_new = M.si_sdr(x, y)
        print(f"  true delay {true_delay:7.1f}  estimated {est:8.2f}  peak {peak:.3f}   "
              f"SI-SDR truncate {sd_old:7.2f} dB -> aligned {sd_new:7.2f} dB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--num-clips", type=int, default=100)
    args = ap.parse_args()

    print("Synthetic check (known delays):")
    synthetic_check()

    import librosa
    by_stem, _ = base.load_manifest_by_stem()
    rng = random.Random(0)
    rows = []
    for name, d in CONDITIONS.items():
        files = sorted(glob.glob(os.path.join(d, "*.wav")))
        if not files:
            print(f"[skip] {name}: no files in {d}")
            continue
        sample = rng.sample(files, min(args.num_clips, len(files)))
        delays, peaks, old, new, applied, edge = [], [], [], [], [], []
        for f in sample:
            stem = os.path.splitext(os.path.basename(f))[0]
            if stem not in by_stem:
                continue
            try:
                ref, _ = librosa.load(by_stem[stem]["file"], sr=SR, mono=True)
                deg, _ = librosa.load(f, sr=SR, mono=True)
                _, _, info = M.align_signals(ref, deg)
                delays.append(info["delay"]); peaks.append(info["peak"])
                applied.append(info["applied"]); edge.append(info["time_varying"])
                vals = {}
                for mode in ("truncate", "delay"):
                    M.ALIGN_MODE = mode
                    vals[mode] = (M.stoi_score(ref, deg, SR), M.pesq_score(ref, deg, SR), M.si_sdr(ref, deg))
                old.append(vals["truncate"]); new.append(vals["delay"])
            except Exception as e:
                print(f"  [warn] {name} {stem}: {e}")
        M.ALIGN_MODE = "delay"
        if not old:
            continue
        d, o, n = np.array(delays), np.array(old), np.array(new)
        rows.append({
            "condition": name, "n": len(o),
            "median_|delay|_samples": round(float(np.median(np.abs(d))), 2),
            "share_|delay|>1_sample": round(float((np.abs(d) > 1).mean()), 2),
            "max_|delay|": round(float(np.abs(d).max()), 1),
            "share_shifted": round(float(np.mean(applied)), 2),
            "share_time_varying": round(float(np.mean(edge)), 2),
            "STOI_trunc": round(o[:, 0].mean(), 3), "STOI_aligned": round(n[:, 0].mean(), 3),
            "PESQ_trunc": round(o[:, 1].mean(), 3), "PESQ_aligned": round(n[:, 1].mean(), 3),
            "SISDR_trunc": round(o[:, 2].mean(), 2), "SISDR_aligned(valid clips)": round(float(np.nanmean(n[:, 2])), 2),
        })
        print(f"  done {name}", flush=True)
    print()
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
