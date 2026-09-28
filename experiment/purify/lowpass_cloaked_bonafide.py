#!/usr/bin/env python3
"""Adaptive-attacker test: apply LowPassFiltering (purify/lowpass.py --
attenuates high-frequency content, where adversarial perturbations tend
to concentrate) to POP's and attack-vc's cloaked clean_bonafide output,
*before* any downstream cloning. If a cloak's protective effect
(established in the paper's protective-efficacy sections) depends on
perturbation energy this filter removes, cloning the *restored* audio
should behave more like the clean-audio ceiling than like the
cloaked-source protective-efficacy result -- i.e. the filter would have
reversed the protection. If restored-then-cloned results stay close to
the cloaked-source numbers, LowPassFiltering did not undo the cloak's
effect.

Purely a signal-processing pass (no GPU, no model loading) -- cheap and
fast relative to everything else in this project. Downstream synthesis
of the restored audio is a separate step (synth/synthesize_*.py already
support pointing --source-dir at an arbitrary directory).

Run (inside antifake2026 env):
    conda run -n antifake2026 python purify/lowpass_cloaked_bonafide.py
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from purify import lowpass
from purify.common import load_wav, save_wav

SOURCE_DIRS = {
    "POP": os.path.join(config.RAW_DIR, "cloaked_bonafide", "POP"),
    "attackvc": os.path.join(config.RAW_DIR, "cloaked_bonafide", "attackvc"),
    "Antifake": os.path.join(config.RAW_DIR, "cloaked_bonafide", "Antifake"),
    "ProtectYourAudio": os.path.join(config.RAW_DIR, "cloaked_bonafide", "ProtectYourAudio"),
}
OUT_DIRS = {
    "POP": config.CLOAKED_BONAFIDE_LOWPASS_POP_DIR,
    "attackvc": config.CLOAKED_BONAFIDE_LOWPASS_ATTACKVC_DIR,
    "Antifake": os.path.join(config.CLOAKED_BONAFIDE_LOWPASS_DIR, "Antifake"),
    "ProtectYourAudio": config.CLOAKED_BONAFIDE_LOWPASS_PROTECTYOURAUDIO_DIR,
}


def main():
    for method, source_dir in SOURCE_DIRS.items():
        out_dir = OUT_DIRS[method]
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
                filtered = lowpass.apply(wav, config.SAMPLE_RATE)
                save_wav(out_path, filtered, config.SAMPLE_RATE)
                n_done += 1
            except Exception as e:
                print(f"[fail] {method}/{stem}: {e}", flush=True)
                n_fail += 1

            if (i + 1) % 500 == 0:
                print(f"  {method}: {i + 1}/{len(source_files)}", flush=True)

        print(f"{method}: done ({n_done} written/skipped, {n_fail} failed)", flush=True)


if __name__ == "__main__":
    main()
