#!/usr/bin/env python3
"""Does voice cloning preserve identity? For every Dataset/clean_bonafide/
clip that's been cloned so far (synth/synthesize_sv2tts.py,
synth/synthesize_f5tts.py -- both long-running, so this only scores
whatever's finished at the time it's run, and can be safely rerun later
as more clones complete), score the synthesized clip against:
  - its own real source clip (genuine, label=1)
  - a sample of other real clean_bonafide clips from a DIFFERENT speaker
    (impostor, label=0), capped per clip to keep scoring tractable at
    this scale

with all 3 judges. Embeddings are cached per file since real clips get
reused as impostor references across many trials.

Run (inside antifake2026 env):
    conda run -n antifake2026 python verify/clean_synthesize_metrics.py
"""
import csv
import glob
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from verify import verify_speechbrain, verify_resemblyzer, verify_wavlm

VERIFIERS = {
    "SpeechBrain": verify_speechbrain,
    "Resemblyzer": verify_resemblyzer,
    "WavLM": verify_wavlm,
}

SYSTEMS = {
    "sv2tts": config.CLEAN_SYNTHESIZE_SV2TTS_DIR,
    "f5tts": config.CLEAN_SYNTHESIZE_F5TTS_DIR,
}

MANIFEST_PATH = os.path.join(config.RAW_DIR, "clean_bonafide", "manifest.json")
IMPOSTORS_PER_CLIP = 10
SEED = 11


class EmbeddingCache:
    def __init__(self, verifier_module):
        self.module = verifier_module
        self.cache = {}

    def get(self, path):
        if path not in self.cache:
            self.cache[path] = self.module.embed(path)
        return self.cache[path]

    def similarity(self, path_a, path_b):
        import numpy as np
        a, b = self.get(path_a), self.get(path_b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def load_manifest_by_stem():
    with open(MANIFEST_PATH) as f:
        entries = json.load(f)["entries"]
    by_stem = {}
    by_speaker = {}
    for e in entries:
        stem = os.path.splitext(os.path.basename(e["file"]))[0]
        by_stem[stem] = e
        by_speaker.setdefault(e["speaker_id"], []).append(e["file"])
    return by_stem, by_speaker


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["score", "label"])
        writer.writerows(rows)


def main():
    os.makedirs(config.CSV_DIR, exist_ok=True)
    by_stem, by_speaker = load_manifest_by_stem()
    speakers = list(by_speaker.keys())
    rng = random.Random(SEED)

    for model_name, module in VERIFIERS.items():
        print(f"\n=== {model_name} ===")
        cache = EmbeddingCache(module)

        for system, synth_dir in SYSTEMS.items():
            synth_files = sorted(glob.glob(os.path.join(synth_dir, "*.wav")))
            if not synth_files:
                print(f"  [skip] no synthesized files for {system} yet")
                continue

            rows = []
            for j, synth_wav in enumerate(synth_files):
                stem = os.path.splitext(os.path.basename(synth_wav))[0]
                entry = by_stem.get(stem)
                if entry is None:
                    continue

                genuine_score = cache.similarity(synth_wav, entry["file"])
                rows.append((f"{genuine_score:.6f}", 1))

                other_speakers = [s for s in speakers if s != entry["speaker_id"]]
                impostor_speakers = rng.sample(other_speakers, min(IMPOSTORS_PER_CLIP, len(other_speakers)))
                for spk in impostor_speakers:
                    impostor_file = rng.choice(by_speaker[spk])
                    impostor_score = cache.similarity(synth_wav, impostor_file)
                    rows.append((f"{impostor_score:.6f}", 0))

                if (j + 1) % 200 == 0:
                    print(f"  {system}: scored {j + 1}/{len(synth_files)}")

            csv_path = os.path.join(config.CSV_DIR, f"CleanSynthesize__{system}__{model_name}.csv")
            write_csv(csv_path, rows)
            n_genuine = sum(1 for _, l in rows if l == 1)
            n_impostor = sum(1 for _, l in rows if l == 0)
            print(f"  wrote {csv_path} ({len(rows)} rows: {n_genuine} genuine, {n_impostor} impostor)")


if __name__ == "__main__":
    main()
