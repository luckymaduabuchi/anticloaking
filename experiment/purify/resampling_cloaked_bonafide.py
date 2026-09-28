#!/usr/bin/env python3
"""Generate the resampling restoration candidates -- downsampling
(purify/downsample.py) and upsampling (purify/upsample.py), already
faithful to the paper's decimation / zero-insertion+interpolation
description -- for POP's and attack-vc's cloaked clean_bonafide output.
Two variants per cloak method, like low-pass+gain's gain values. As
with the other restoration techniques, the actual test of whether this
reverses a cloak's protective effect happens downstream: each candidate
gets cloned and scored against the genuine clean_bonafide original.

Pure signal processing (no GPU) -- fast relative to the downstream
cloning/verification stages that follow.

Run (inside antifake2026 env):
    conda run -n antifake2026 python purify/resampling_cloaked_bonafide.py
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from purify import downsample, upsample
from purify.common import load_wav, save_wav

SOURCE_DIRS = {
    "POP": os.path.join(config.RAW_DIR, "cloaked_bonafide", "POP"),
    "attackvc": os.path.join(config.RAW_DIR, "cloaked_bonafide", "attackvc"),
    "Antifake": os.path.join(config.RAW_DIR, "cloaked_bonafide", "Antifake"),
    "ProtectYourAudio": os.path.join(config.RAW_DIR, "cloaked_bonafide", "ProtectYourAudio"),
}

VARIANT_MODULES = {
    "downsample": downsample,
    "upsample": upsample,
}


def main():
    for method, source_dir in SOURCE_DIRS.items():
        source_files = sorted(glob.glob(os.path.join(source_dir, "*.wav")))
        print(f"{method}: {len(source_files)} cloaked clips found", flush=True)

        for variant, module in VARIANT_MODULES.items():
            out_dir = config.CLOAKED_BONAFIDE_RESAMPLING_DIRS[(method, variant)]
            os.makedirs(out_dir, exist_ok=True)

            n_done, n_fail = 0, 0
            for i, path in enumerate(source_files):
                stem = os.path.splitext(os.path.basename(path))[0]
                out_path = os.path.join(out_dir, f"{stem}.wav")
                if os.path.exists(out_path):
                    n_done += 1
                    continue

                try:
                    wav = load_wav(path, config.SAMPLE_RATE)
                    restored = module.apply(wav, config.SAMPLE_RATE)
                    save_wav(out_path, restored, config.SAMPLE_RATE)
                    n_done += 1
                except Exception as e:
                    print(f"[fail] {method}/{variant}/{stem}: {e}", flush=True)
                    n_fail += 1

                if (i + 1) % 1000 == 0:
                    print(f"  {method}/{variant}: {i + 1}/{len(source_files)}", flush=True)

            print(f"{method}/{variant}: done ({n_done} written/skipped, {n_fail} failed)", flush=True)


if __name__ == "__main__":
    main()
