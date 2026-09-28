#!/usr/bin/env python3
"""Generate the corrected second-cloak-application restoration
candidates (purify/second_cloak_noise.py: cloak-agnostic additive
Gaussian noise, 30dB SNR, single pass) for POP's, attack-vc's, and
AntiFake's cloaked clean_bonafide output. Replaces the earlier,
incorrect implementation (cloak/pop_vendored/protect_already_cloaked.py,
which re-ran a specific cloak's own attack a second time -- something a
real restoration-side attacker without knowledge of the cloak used
could not do); that script and its output are left untouched.

Pure signal processing (no GPU) -- fast relative to the downstream
cloning/verification stages that follow.

Run (inside antifake2026 env):
    conda run -n antifake2026 python purify/second_cloak_noise_cloaked_bonafide.py
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from purify import second_cloak_noise
from purify.common import load_wav, save_wav

SOURCE_DIRS = {
    "POP": os.path.join(config.RAW_DIR, "cloaked_bonafide", "POP"),
    "attackvc": os.path.join(config.RAW_DIR, "cloaked_bonafide", "attackvc"),
    "Antifake": os.path.join(config.RAW_DIR, "cloaked_bonafide", "Antifake"),
    "ProtectYourAudio": os.path.join(config.RAW_DIR, "cloaked_bonafide", "ProtectYourAudio"),
}


def main():
    for method, source_dir in SOURCE_DIRS.items():
        out_dir = config.CLOAKED_BONAFIDE_SECOND_CLOAK_NOISE_DIRS[method]
        os.makedirs(out_dir, exist_ok=True)

        source_files = sorted(glob.glob(os.path.join(source_dir, "*.wav")))
        print(f"{method}: {len(source_files)} cloaked clips found", flush=True)

        n_done, n_fail = 0, 0
        for i, path in enumerate(source_files):
            stem = os.path.splitext(os.path.basename(path))[0]
            out_path = os.path.join(out_dir, f"{stem}.wav")
            if os.path.exists(out_path):
                n_done += 1
                continue

            try:
                wav = load_wav(path, config.SAMPLE_RATE)
                restored = second_cloak_noise.apply(wav, config.SAMPLE_RATE)
                save_wav(out_path, restored, config.SAMPLE_RATE)
                n_done += 1
            except Exception as e:
                print(f"[fail] {method}/{stem}: {e}", flush=True)
                n_fail += 1

            if (i + 1) % 1000 == 0:
                print(f"  {method}: {i + 1}/{len(source_files)}", flush=True)

        print(f"{method}: done ({n_done} written/skipped, {n_fail} failed)", flush=True)


if __name__ == "__main__":
    main()
