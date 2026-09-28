#!/usr/bin/env bash
# Waits for every long-running job, then finishes the migration:
#   1. full-corpus clean SV2TTS ceiling synthesis (run_clean_sv2tts_full.sh)
#   2. primary-condition rescore (rescore_with_ids.sh)
#   3. restoration-study rescore, both shards (rescore_restoration.py)
# Then: score the full clean SV2TTS ceiling with IDs, rebuild any table
# written by older code, update cloak-level quality with delay alignment,
# report coverage, and re-run every paired comparison on all clips.
set -uo pipefail
cd "$(dirname "$0")/.."

LOG=/tmp/finalize_all.log
: > "$LOG"
CEIL_OUT=/home/vm-user/Desktop/Antifake2026/results/groundtruthcomparison/cleanbonafidevscleansynth/SV2TTS
run() { conda run -n antifake2026 --no-capture-output python -u "$@" >> "$LOG" 2>&1; }

echo "$(date): waiting for clean SV2TTS synthesis, primary rescore, and restoration shards" | tee -a "$LOG"
until grep -q "finished pass" /tmp/clean_sv2tts_full.log 2>/dev/null \
   && grep -q "all rescoring finished" /tmp/rescore_with_ids.log 2>/dev/null \
   && [ -f /tmp/rescore_restoration_shard_0.done ] && [ -f /tmp/rescore_restoration_shard_1.done ]; do
  sleep 300
done
echo "$(date): all prerequisites done" | tee -a "$LOG"

echo "$(date): scoring full clean SV2TTS ceiling" | tee -a "$LOG"
run analysis/clean_bonafide_vs_synth.py --system sv2tts --out-dir "$CEIL_OUT"
echo "$(date): rebuilding tables written by older code" | tee -a "$LOG"
run analysis/rebuild_tables.py
echo "$(date): cloak-level quality with delay alignment" | tee -a "$LOG"
run analysis/recompute_quality_aligned.py --only-cloak
echo "$(date): coverage report" | tee -a "$LOG"
run analysis/verify_coverage.py
echo "$(date): paired comparisons on all clips" | tee -a "$LOG"
run analysis/paired_all.py --workers 6
echo "$(date): finalize complete -> results/paired_stats/  (coverage report above in this log)" | tee -a "$LOG"
