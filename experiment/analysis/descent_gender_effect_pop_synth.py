#!/usr/bin/env python3
"""Does descent or gender predict how well POP's protective effect
holds up once the cloaked audio is cloned by a downstream system?

Reads the per-group (descent x gender) breakdowns already computed by
clean_bonafide_vs_synth.py for the two completed protective-efficacy
runs (pop_sv2tts, pop_seedvc -- see
results/groundtruthvscloaking/groundtruthvsPOP/groundtruthvscloakedsynthesis/),
averages EER and TAR@1%FAR across verifiers within each descent and
within each gender, and reports both breakdowns side by side for the
two systems so any gender/descent effect (and whether it's consistent
between the two synthesizers) can be read off directly.

Run:
    conda run -n antifake2026 python analysis/descent_gender_effect_pop_synth.py
"""
import os
import sys

import pandas as pd

RESULTS_ROOT = "/home/vm-user/Desktop/Antifake2026/results/groundtruthvscloaking/groundtruthvsPOP/groundtruthvscloakedsynthesis"
CEILING_ROOT = "/home/vm-user/Desktop/Antifake2026/results/groundtruthcomparison/cleanbonafidevscleansynth"
SYSTEMS = ["sv2tts", "seedvc", "f5tts"]
CEILING_DIRS = {"sv2tts": "SV2TTS", "seedvc": "SEEDVC", "f5tts": "F5TTS"}


def load(system):
    path = os.path.join(RESULTS_ROOT, system, "results_table_by_group.csv")
    df = pd.read_csv(path)
    df["descent"] = df["Group"].str.rsplit("-", n=1).str[0]
    df["gender"] = df["Group"].str.rsplit("-", n=1).str[1]
    return df


def load_ceiling(system):
    path = os.path.join(CEILING_ROOT, CEILING_DIRS[system], "results_table_by_group.csv")
    df = pd.read_csv(path)
    df["descent"] = df["Group"].str.rsplit("-", n=1).str[0]
    df["gender"] = df["Group"].str.rsplit("-", n=1).str[1]
    return df


def summarize(df, key):
    # Average EER/TAR@1% across the 3 verifiers within each descent/gender
    # value -- a verifier-agnostic view of whether that demographic
    # attribute predicts an easier/harder-to-protect group.
    g = df.groupby(key)[["EER", "TAR@1%"]].mean().round(4)
    g["N_groups_averaged"] = df.groupby(key).size()
    return g


def main():
    for system in SYSTEMS:
        df = load(system)
        ceiling_df = load_ceiling(system)
        print(f"\n=== {system}: POP-cloaked source ===")
        print("\nBy gender (averaged across 5 descents x 3 verifiers):")
        print(summarize(df, "gender").to_string())
        print("\nBy descent (averaged across 2 genders x 3 verifiers):")
        print(summarize(df, "descent").to_string())

        print(f"\n=== {system}: clean-audio ceiling (no cloaking) -- for comparison ===")
        print("\nBy gender:")
        print(summarize(ceiling_df, "gender").to_string())
        print("\nBy descent:")
        print(summarize(ceiling_df, "descent").to_string())


if __name__ == "__main__":
    main()
