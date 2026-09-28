#!/usr/bin/env python3
"""Score every synthesized clone (Baseline, Raw-cloaked, and each
restoration technique) against the real victim (target trial, label=1)
and the *entire* real impostor pool (impostor trials, label=0 -- scored
many-to-one so low-FAR operating points are statistically meaningful
without extra expensive synthesis runs), with all three verifiers.
Writes real, measured score,label CSVs to verify/csvs/.

Run (inside antifake2026 env):
    conda run -n antifake2026 python verify/run_all.py
"""
import csv
import glob
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from verify import verify_speechbrain, verify_resemblyzer, verify_wavlm

VERIFIERS = {
    "SpeechBrain": verify_speechbrain.similarity,
    "Resemblyzer": verify_resemblyzer.similarity,
    "WavLM": verify_wavlm.similarity,
}


def load_manifest():
    with open(config.MANIFEST_PATH) as f:
        manifest = json.load(f)
    lookup = {e["utt_id"]: e["wav"] for e in manifest["victims"]}
    return lookup, manifest["impostor_pool"]


def append_row(csv_path, score, label):
    is_new = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["score", "label"])
        writer.writerow([f"{score:.6f}", label])


def expected_row_count(n_utterances, n_impostors):
    return n_utterances * (1 + n_impostors)


def already_scored(csv_path, n_expected_rows):
    if not os.path.exists(csv_path):
        return False
    with open(csv_path) as f:
        return sum(1 for _ in f) - 1 >= n_expected_rows  # minus header


def score_condition(csv_path, synth_files, victim_lookup, impostor_pool, similarity_fn):
    if already_scored(csv_path, expected_row_count(len(synth_files), len(impostor_pool))):
        print(f"[skip] {csv_path}: already fully scored")
        return

    for synth_wav in synth_files:
        utt_id = os.path.splitext(os.path.basename(synth_wav))[0]
        victim_wav = victim_lookup.get(utt_id)
        if victim_wav is None:
            print(f"[warn] {utt_id} not in manifest, skipping")
            continue

        print(f"[run ] {os.path.basename(csv_path)} / {utt_id}")
        try:
            genuine_score = similarity_fn(synth_wav, victim_wav)
            append_row(csv_path, genuine_score, 1)

            for impostor_wav in impostor_pool:
                impostor_score = similarity_fn(synth_wav, impostor_wav)
                append_row(csv_path, impostor_score, 0)
        except Exception:
            print(f"[fail] {os.path.basename(csv_path)} / {utt_id}")
            traceback.print_exc()


def main():
    os.makedirs(config.CSV_DIR, exist_ok=True)
    victim_lookup, impostor_pool = load_manifest()

    for model_name, similarity_fn in VERIFIERS.items():
        # Baseline: original unprotected audio -> synth -> verify
        baseline_files = sorted(glob.glob(os.path.join(config.SYNTH_DIR, config.BASELINE_LABEL, "*.wav")))
        if baseline_files:
            csv_path = os.path.join(config.CSV_DIR, f"{config.BASELINE_LABEL}__{config.BASELINE_LABEL}__{model_name}.csv")
            score_condition(csv_path, baseline_files, victim_lookup, impostor_pool, similarity_fn)

        # Raw-cloaked and each restoration technique, per dataset
        for label in [config.RAW_LABEL] + config.TECHNIQUES:
            for dataset in config.DATASETS:
                synth_files = sorted(glob.glob(os.path.join(config.SYNTH_DIR, dataset, label, "*.wav")))
                if not synth_files:
                    continue
                csv_path = os.path.join(config.CSV_DIR, f"{dataset}__{label}__{model_name}.csv")
                score_condition(csv_path, synth_files, victim_lookup, impostor_pool, similarity_fn)


if __name__ == "__main__":
    main()
