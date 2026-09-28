#!/usr/bin/env python3
"""Apply all 10 restoration/inversion techniques to every cloaked
utterance in both datasets, plus pass through an unpurified "Raw"
baseline so the synthesis/verification stages can compare cloaked-only
vs. cloaked-then-restored.

Run (inside antifake2026 env):
    conda run -n antifake2026 python purify/run_all.py
"""
import glob
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from purify import (
    lowpass, highpass, downsample, upsample, quantization, adaptive_filter,
    spectral_subtraction, ensemble_averaging, mel_inversion, sim_rerecord,
)
from purify.common import load_wav, save_wav

TECHNIQUE_MODULES = {
    "LowPassFiltering": lowpass,
    "HighPassFiltering": highpass,
    "Downsampling": downsample,
    "Upsampling": upsample,
    "QuantizationFiltering": quantization,
    "AdaptiveFiltering": adaptive_filter,
    "SpectralSubtraction": spectral_subtraction,
    "EnsembleAveraging": ensemble_averaging,
    "MelSpectrogram": mel_inversion,
    "SimulatedReRecord": sim_rerecord,
}

DATASET_DIRS = {
    "AntiFake": config.CLOAK_ANTIFAKE_DIR,
    "ProtectYourAudio": config.CLOAK_PROTECT_DIR,
}


def main():
    assert set(TECHNIQUE_MODULES) == set(config.TECHNIQUES), "technique list in config.py is out of sync"

    for dataset, cloak_dir in DATASET_DIRS.items():
        cloaked_files = sorted(glob.glob(os.path.join(cloak_dir, "*.wav")))
        if not cloaked_files:
            print(f"[warn] no cloaked files found for {dataset} in {cloak_dir}; run cloak/generate_*.py first")
            continue

        for cloaked_path in cloaked_files:
            utt_id = os.path.splitext(os.path.basename(cloaked_path))[0]
            wav = load_wav(cloaked_path, config.SAMPLE_RATE)

            raw_dir = os.path.join(config.PURIFY_DIR, config.RAW_LABEL, dataset)
            os.makedirs(raw_dir, exist_ok=True)
            raw_out = os.path.join(raw_dir, f"{utt_id}.wav")
            if not os.path.exists(raw_out):
                save_wav(raw_out, wav, config.SAMPLE_RATE)

            for technique, module in TECHNIQUE_MODULES.items():
                out_dir = os.path.join(config.PURIFY_DIR, technique, dataset)
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, f"{utt_id}.wav")
                if os.path.exists(out_path):
                    continue

                print(f"[run ] {dataset}/{technique}/{utt_id}")
                try:
                    purified = module.apply(wav, config.SAMPLE_RATE)
                    save_wav(out_path, purified, config.SAMPLE_RATE)
                except Exception:
                    print(f"[fail] {dataset}/{technique}/{utt_id}")
                    traceback.print_exc()


if __name__ == "__main__":
    main()
