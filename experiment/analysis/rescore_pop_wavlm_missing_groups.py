#!/usr/bin/env python3
"""Patch script: rescore WavLM for the 3 clean_bonafide-vs-POP descent x
gender groups that were dropped entirely or partially by CUDA OOM during
the original clean_bonafide_vs_synth.py --system POP run (the GPU was
shared concurrently with the attack-vc/ProtectYourAudio cloaking batches
at the time).

Confirmed from /tmp/clean_bonafide_vs_pop.log: WavLM has ZERO scored rows
for African-men and African-women (100% OOM on every clip in those two
groups), and only ~55% coverage for Asian(East)-men (2123/3872 pairs,
vs. SpeechBrain's full count for the same group). Every other group only
lost isolated single clips, which barely dents a 300-400 pair group.
SB-ECAPA and Resemblyzer are unaffected -- this script only touches the
WavLM CSV/table rows for these 3 groups.

Does NOT rescore the whole corpus. Only the FakeAVCeleb entries whose
descent x gender falls in BROKEN_GROUPS below are rescored, then those
rows are patched into the existing POP__POP__WavLM.csv (the original is
backed up to *.csv.bak first), and results_table.csv /
results_table_by_group.csv / plots are regenerated from the patched CSVs
via clean_bonafide_vs_synth.py's own table/plot builders, so the
methodology stays identical to the original run.

Run:
    LD_LIBRARY_PATH=/home/vm-user/anaconda3/envs/antifake2026/lib:$LD_LIBRARY_PATH \
    conda run -n antifake2026 python analysis/rescore_pop_wavlm_missing_groups.py
"""
import glob
import os
import random
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from verify import verify_wavlm
from analysis.clean_bonafide_vs_synth import (
    SYSTEM_DIRS, SEED, IMPOSTORS_PER_CLIP,
    load_manifest_by_stem, EmbeddingCache,
    build_results_table, build_group_breakdown, plot_all, plot_group_breakdown,
)

SYSTEM_NAME = "POP"
OUT_DIR = "/home/vm-user/Desktop/Antifake2026/results/groundtruthvscloaking/groundtruthvsPOP/gorundtruthvscloaked"
CSV_DIR = os.path.join(OUT_DIR, "csvs")
PLOTS_DIR = os.path.join(OUT_DIR, "plots")
WAVLM_CSV = os.path.join(CSV_DIR, f"{SYSTEM_NAME}__{SYSTEM_NAME}__WavLM.csv")

BROKEN_GROUPS = {"African-men", "African-women", "Asian(East)-men"}


def rescore_broken_groups():
    by_stem, by_speaker = load_manifest_by_stem()
    speakers = list(by_speaker.keys())
    synth_dir = SYSTEM_DIRS[SYSTEM_NAME]
    synth_files = sorted(glob.glob(os.path.join(synth_dir, "*.wav")))

    targets = []
    for synth_wav in synth_files:
        stem = os.path.splitext(os.path.basename(synth_wav))[0]
        entry = by_stem.get(stem)
        if entry is None or "descent" not in entry:
            continue
        group = f"{entry['descent']}-{entry['gender']}"
        if group in BROKEN_GROUPS:
            targets.append((synth_wav, stem, entry, group))

    print(f"{len(targets)} clips belong to the broken groups {BROKEN_GROUPS}", flush=True)

    # Same seed/sampling scheme as clean_bonafide_vs_synth.py's score_all(),
    # just restricted to this subset -- these clips never successfully
    # drew WavLM impostor pairs before (genuine failed => impostor block
    # never ran), so there is no prior draw to stay consistent with.
    rng = random.Random(SEED)
    cache = EmbeddingCache(verify_wavlm)
    rows = []
    n_fail = 0
    for j, (synth_wav, stem, entry, group) in enumerate(targets):
        try:
            genuine_score = cache.similarity(synth_wav, entry["file"])
        except Exception as e:
            print(f"  [warn] WavLM: still failing on {stem} ({e}); skipping", flush=True)
            n_fail += 1
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass
            continue
        rows.append((f"{genuine_score:.6f}", 1, group))

        other_speakers = [s for s in speakers if s != entry["speaker_id"]]
        impostor_speakers = rng.sample(other_speakers, min(IMPOSTORS_PER_CLIP, len(other_speakers)))
        for spk in impostor_speakers:
            impostor_file = rng.choice(by_speaker[spk])
            try:
                impostor_score = cache.similarity(synth_wav, impostor_file)
            except Exception as e:
                print(f"  [warn] WavLM: still failing on {stem} vs impostor ({e}); skipping trial", flush=True)
                try:
                    import torch
                    torch.cuda.empty_cache()
                except Exception:
                    pass
                continue
            rows.append((f"{impostor_score:.6f}", 0, group))

        if (j + 1) % 100 == 0:
            print(f"  rescored {j + 1}/{len(targets)}", flush=True)

    print(f"Rescored {len(targets) - n_fail}/{len(targets)} clips ({n_fail} still failing)", flush=True)
    return rows


def patch_csv(new_rows):
    df = pd.read_csv(WAVLM_CSV)
    backup_path = WAVLM_CSV + ".bak"
    if not os.path.exists(backup_path):
        df.to_csv(backup_path, index=False)
        print(f"Backed up original to {backup_path}", flush=True)

    before = len(df)
    df = df[~df.group.isin(BROKEN_GROUPS)]
    print(f"Dropped {before - len(df)} incomplete/biased rows for {BROKEN_GROUPS}", flush=True)

    new_df = pd.DataFrame(new_rows, columns=["score", "label", "group"])
    df = pd.concat([df, new_df], ignore_index=True)
    df.to_csv(WAVLM_CSV, index=False)
    print(f"Wrote {WAVLM_CSV} ({len(df)} total rows)", flush=True)


def main():
    new_rows = rescore_broken_groups()
    if not new_rows:
        print("No rows rescored -- aborting patch.", flush=True)
        return
    patch_csv(new_rows)

    # STOI/PESQ/SI-SDR don't depend on the verifier, and this patch only
    # touches WavLM's speaker-verification scores -- reuse the existing
    # quality numbers rather than recomputing them.
    existing_table = pd.read_csv(os.path.join(OUT_DIR, "results_table.csv"))
    q_cols = ["STOI_mean", "STOI_median", "PESQ_mean", "PESQ_median",
              "SI_SDR_mean_dB", "SI_SDR_median_dB", "quality_N"]
    quality = existing_table.iloc[0][q_cols].to_dict()

    build_results_table(SYSTEM_NAME, CSV_DIR, OUT_DIR, quality=quality)
    build_group_breakdown(SYSTEM_NAME, CSV_DIR, OUT_DIR)

    import matplotlib.pyplot as plt
    import analysis.clean_bonafide_vs_synth as cbvs
    cbvs.plt = plt
    plot_all(SYSTEM_NAME, CSV_DIR, PLOTS_DIR)
    plot_group_breakdown(SYSTEM_NAME, CSV_DIR, PLOTS_DIR)
    print(f"\nAll patched outputs written under {OUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
