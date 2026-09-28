#!/usr/bin/env python3
"""Generate the low-pass + gain-multiplier restoration candidates
(purify/lowpass_gain.py) for POP's and attack-vc's cloaked
clean_bonafide output, one directory per (cloak method, gain value)
combination, using the Butterworth design (the paper's own main-results
configuration). The actual "search" for which gain best reverses the
cloak happens downstream: each candidate here gets cloned with SV2TTS
and scored against the genuine clean_bonafide original
(analysis/clean_bonafide_vs_synth.py), and whichever gain's clones come
closest to the clean-audio ceiling is the one that "worked."

Pure signal processing (no GPU) -- fast relative to the downstream
cloning/verification stages that follow.

Run (inside antifake2026 env):
    conda run -n antifake2026 python purify/lowpass_gain_search_cloaked_bonafide.py
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from purify import lowpass_gain
from purify.common import load_wav, save_wav

SOURCE_DIRS = {
    "POP": os.path.join(config.RAW_DIR, "cloaked_bonafide", "POP"),
    "attackvc": os.path.join(config.RAW_DIR, "cloaked_bonafide", "attackvc"),
    "Antifake": os.path.join(config.RAW_DIR, "cloaked_bonafide", "Antifake"),
    "ProtectYourAudio": os.path.join(config.RAW_DIR, "cloaked_bonafide", "ProtectYourAudio"),
}
OUT_ROOT = os.path.join(config.RESTORATION_TECHNIQUES_DIR, "low_pass_gain")
FILTER_TYPE = "butterworth"


def main():
    for method, source_dir in SOURCE_DIRS.items():
        source_files = sorted(glob.glob(os.path.join(source_dir, "*.wav")))
        print(f"{method}: {len(source_files)} cloaked clips found", flush=True)

        for gain in lowpass_gain.GAIN_VALUES:
            out_dir = os.path.join(OUT_ROOT, method, f"gain_{gain}")
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
                    restored = lowpass_gain.apply(wav, config.SAMPLE_RATE, gain=gain, filter_type=FILTER_TYPE)
                    save_wav(out_path, restored, config.SAMPLE_RATE)
                    n_done += 1
                except Exception as e:
                    print(f"[fail] {method}/gain_{gain}/{stem}: {e}", flush=True)
                    n_fail += 1

                if (i + 1) % 1000 == 0:
                    print(f"  {method}/gain_{gain}: {i + 1}/{len(source_files)}", flush=True)

            print(f"{method}/gain_{gain}: done ({n_done} written/skipped, {n_fail} failed)", flush=True)


if __name__ == "__main__":
    main()
