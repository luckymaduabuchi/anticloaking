#!/usr/bin/env bash
# Runs once the full-corpus clean SV2TTS ceiling (run_clean_sv2tts_full.sh,
# 4,867 clips) has been synthesized:
#   1. re-scores the clean SV2TTS ceiling on ALL clips, with trial IDs
#   2. re-runs every paired comparison, so the SV2TTS comparisons use the
#      full ~4,864 clips per condition instead of the original 1,500-clip
#      overlap.
# Waits for the synthesis wrapper's "finished pass" line and for the
# rescore_with_ids.sh run to be done, so nothing competes for the GPU.
set -uo pipefail
cd "$(dirname "$0")/.."

LOG=/tmp/after_full_ceiling.log
: > "$LOG"
CEIL_OUT=/home/vm-user/Desktop/Antifake2026/results/groundtruthcomparison/cleanbonafidevscleansynth/SV2TTS

echo "$(date): waiting for full clean SV2TTS synthesis" | tee -a "$LOG"
until grep -q "finished pass" /tmp/clean_sv2tts_full.log 2>/dev/null; do sleep 120; done
echo "$(date): synthesis done ($(ls /home/vm-user/Desktop/Antifake2026/Dataset/clean_synthesize/sv2tts | grep -c '\.wav$') clips); waiting for main rescore" | tee -a "$LOG"
until grep -q "all rescoring finished" /tmp/rescore_with_ids.log 2>/dev/null; do sleep 120; done

echo "$(date): scoring full clean SV2TTS ceiling" | tee -a "$LOG"
conda run -n antifake2026 --no-capture-output python -u analysis/clean_bonafide_vs_synth.py \
  --system sv2tts --out-dir "$CEIL_OUT" >> "$LOG" 2>&1
echo "$(date): rebuilding tables + running all paired comparisons" | tee -a "$LOG"
conda run -n antifake2026 --no-capture-output python -u analysis/rebuild_tables.py >> "$LOG" 2>&1
conda run -n antifake2026 --no-capture-output python -u analysis/paired_all.py --workers 6 >> "$LOG" 2>&1
echo "$(date): all done -> results/paired_stats/" | tee -a "$LOG"
