#!/usr/bin/env python3
"""Does descent or gender predict how well attack-vc's protective effect
holds up once the cloaked audio is cloned by a downstream system?

Same analysis as descent_gender_effect_pop_synth.py, but for attack-vc's
three completed protective-efficacy runs (attackvc_sv2tts, attackvc_seedvc,
attackvc_f5tts -- see
results/groundtruthvscloaking/groundtruthvsattackvc/groundtruthvscloakedsynthesis/),
compared against the same clean-audio ceiling breakdowns. Averages EER
and TAR@1%FAR across verifiers within each descent and within each
gender, and reports both breakdowns side by side with the ceiling so
any gender/descent effect -- and whether it's consistent across all
three synthesizers -- can be read off directly.

Run:
    conda run -n antifake2026 python analysis/descent_gender_effect_attackvc_synth.py
"""
import os
import sys

import pandas as pd

RESULTS_ROOT = "/home/vm-user/Desktop/Antifake2026/results/groundtruthvscloaking/groundtruthvsattackvc/groundtruthvscloakedsynthesis"
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
    g = df.groupby(key)[["EER", "TAR@1%"]].mean().round(4)
    g["N_groups_averaged"] = df.groupby(key).size()
    return g


def main():
    for system in SYSTEMS:
        df = load(system)
        ceiling_df = load_ceiling(system)
        print(f"\n=== {system}: attack-vc-cloaked source ===")
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
