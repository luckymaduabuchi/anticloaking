#!/usr/bin/env python3
"""Verifier calibration metrics on real, uncloaked, unsynthesized speech
(Dataset/clean_bonafide/): how well do SpeechBrain ECAPA, Resemblyzer,
and WavLM separate genuine (same-speaker) from impostor (different-
speaker) pairs on plain bonafide audio, before any cloaking/restoration/
synthesis is involved. This is the sanity-check baseline the rest of
the experiment's numbers should be read against.

Trial construction:
  - Genuine (label=1): same-speaker pairs within LibriSpeech, within
    ASVspoof2021, and within FakeAVCeleb (overall, and broken down per
    descent x gender group -- 10 groups). Capped per speaker to avoid a
    handful of prolific speakers dominating.
  - Impostor (label=0): different-speaker pairs within LibriSpeech,
    within ASVspoof2021, within FakeAVCeleb (overall, and per group --
    same descent+gender, different speaker), and cross-corpus pairs
    (LibriSpeech x ASVspoof2021 x FakeAVCeleb).

Each unique file's embedding is computed once per model and cached,
since files are reused across many trial pairs.

Run (inside antifake2026 env):
    conda run -n antifake2026 python verify/clean_bonafide_metrics.py
"""
import csv
import itertools
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from verify import verify_speechbrain, verify_resemblyzer, verify_wavlm

MANIFEST_PATH = os.path.join(config.RAW_DIR, "clean_bonafide", "manifest.json")

VERIFIERS = {
    "SpeechBrain": verify_speechbrain,
    "Resemblyzer": verify_resemblyzer,
    "WavLM": verify_wavlm,
}

SEED = 123
MAX_GENUINE_PAIRS_PER_SPEAKER = 6
MAX_WITHIN_CORPUS_IMPOSTOR_PAIRS = 1500   # per source (LibriSpeech, ASVspoof2021)
MAX_CROSS_CORPUS_IMPOSTOR_PAIRS = 1500    # per source-pair
MAX_FAKEAVCELEB_GROUP_IMPOSTOR_PAIRS = 400   # per descent x gender group (only 50 speakers each)
MAX_FAKEAVCELEB_OVERALL_IMPOSTOR_PAIRS = 3000


def load_entries():
    with open(MANIFEST_PATH) as f:
        return json.load(f)["entries"]


def _genuine_pairs_from_groups(by_speaker, rng):
    out = []
    for files in by_speaker.values():
        if len(files) < 2:
            continue
        combos = list(itertools.combinations(sorted(files), 2))
        rng.shuffle(combos)
        out.extend(combos[:MAX_GENUINE_PAIRS_PER_SPEAKER])
    return out


def build_genuine_pairs(entries, rng):
    """(file_a, file_b) genuine pairs, grouped by source (LibriSpeech,
    ASVspoof2021, FakeAVCeleb overall, and FakeAVCeleb-<descent>-<gender>
    per group)."""
    pairs = {}
    for source in ["LibriSpeech", "ASVspoof2021"]:
        by_speaker = {}
        for e in entries:
            if e["source"] == source and e["speaker_id"]:
                by_speaker.setdefault(e["speaker_id"], []).append(e["file"])
        pairs[source] = _genuine_pairs_from_groups(by_speaker, rng)

    fac_by_speaker = {}
    fac_by_group_speaker = {}
    for e in entries:
        if e["source"] != "FakeAVCeleb":
            continue
        fac_by_speaker.setdefault(e["speaker_id"], []).append(e["file"])
        group = (e["descent"], e["gender"])
        fac_by_group_speaker.setdefault(group, {}).setdefault(e["speaker_id"], []).append(e["file"])

    pairs["FakeAVCeleb"] = _genuine_pairs_from_groups(fac_by_speaker, rng)
    for group, by_speaker in fac_by_group_speaker.items():
        label = f"FakeAVCeleb-{group[0].replace(' ', '')}-{group[1]}"
        pairs[label] = _genuine_pairs_from_groups(by_speaker, rng)

    return pairs


def _sample_impostor_pairs(by_speaker, rng, target):
    speakers = list(by_speaker.keys())
    if len(speakers) < 2:
        return []
    out = set()
    attempts = 0
    while len(out) < target and attempts < target * 20:
        attempts += 1
        s1, s2 = rng.sample(speakers, 2)
        f1, f2 = rng.choice(by_speaker[s1]), rng.choice(by_speaker[s2])
        out.add(tuple(sorted((f1, f2))))
    return list(out)


def build_impostor_pairs(entries, rng):
    """(file_a, file_b) impostor pairs: within-corpus (different speaker
    id, incl. FakeAVCeleb overall and per descent x gender group) and
    cross-corpus (different source)."""
    pairs = {}

    for source in ["LibriSpeech", "ASVspoof2021"]:
        by_speaker = {}
        for e in entries:
            if e["source"] == source and e["speaker_id"]:
                by_speaker.setdefault(e["speaker_id"], []).append(e["file"])
        pairs[source] = _sample_impostor_pairs(by_speaker, rng, MAX_WITHIN_CORPUS_IMPOSTOR_PAIRS)

    fac_by_speaker = {}
    fac_by_group_speaker = {}
    for e in entries:
        if e["source"] != "FakeAVCeleb":
            continue
        fac_by_speaker.setdefault(e["speaker_id"], []).append(e["file"])
        group = (e["descent"], e["gender"])
        fac_by_group_speaker.setdefault(group, {}).setdefault(e["speaker_id"], []).append(e["file"])

    pairs["FakeAVCeleb"] = _sample_impostor_pairs(fac_by_speaker, rng, MAX_FAKEAVCELEB_OVERALL_IMPOSTOR_PAIRS)
    for group, by_speaker in fac_by_group_speaker.items():
        label = f"FakeAVCeleb-{group[0].replace(' ', '')}-{group[1]}"
        pairs[label] = _sample_impostor_pairs(by_speaker, rng, MAX_FAKEAVCELEB_GROUP_IMPOSTOR_PAIRS)

    files_by_source = {}
    for e in entries:
        files_by_source.setdefault(e["source"], []).append(e["file"])

    for src_a, src_b in itertools.combinations(sorted(files_by_source), 2):
        label = f"{src_a}Vs{src_b}"
        cross_pairs = set()
        attempts = 0
        target = MAX_CROSS_CORPUS_IMPOSTOR_PAIRS
        while len(cross_pairs) < target and attempts < target * 20:
            attempts += 1
            f1 = rng.choice(files_by_source[src_a])
            f2 = rng.choice(files_by_source[src_b])
            cross_pairs.add((f1, f2))
        pairs[label] = list(cross_pairs)

    return pairs


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


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["score", "label"])
        writer.writerows(rows)


def main():
    rng = random.Random(SEED)
    entries = load_entries()

    genuine = build_genuine_pairs(entries, rng)
    impostor = build_impostor_pairs(entries, rng)

    print("Genuine pairs:", {k: len(v) for k, v in genuine.items()})
    print("Impostor pairs:", {k: len(v) for k, v in impostor.items()})

    for model_name, module in VERIFIERS.items():
        print(f"\n=== {model_name} ===")
        cache = EmbeddingCache(module)

        for source, pairs in genuine.items():
            csv_path = os.path.join(config.CSV_DIR, f"CleanBonafide__{source}__{model_name}.csv")
            rows = [(f"{cache.similarity(a, b):.6f}", 1) for a, b in pairs]
            # impostor rows for the same "technique" bucket (within-corpus) appended to the same file
            rows += [(f"{cache.similarity(a, b):.6f}", 0) for a, b in impostor.get(source, [])]
            write_csv(csv_path, rows)
            print(f"  wrote {csv_path} ({len(rows)} rows)")

        for label, pairs in impostor.items():
            if label in genuine:
                continue  # already folded into the within-corpus file above
            csv_path = os.path.join(config.CSV_DIR, f"CleanBonafide__{label}__{model_name}.csv")
            rows = [(f"{cache.similarity(a, b):.6f}", 0) for a, b in pairs]
            write_csv(csv_path, rows)
            print(f"  wrote {csv_path} ({len(rows)} rows, impostor-only)")


if __name__ == "__main__":
    main()
