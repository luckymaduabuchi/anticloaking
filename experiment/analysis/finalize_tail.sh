#!/usr/bin/env bash
# Re-runs just the back half of finalize_all.sh, now that the SV2TTS
# ceiling is the true full 4,867 clips (not the earlier incomplete 3,852).
set -uo pipefail
cd "$(dirname "$0")/.."

LOG=/tmp/finalize_tail.log
: > "$LOG"
CEIL_OUT=/home/vm-user/Desktop/Antifake2026/results/groundtruthcomparison/cleanbonafidevscleansynth/SV2TTS
run() { conda run -n antifake2026 --no-capture-output python -u "$@" >> "$LOG" 2>&1; }

echo "$(date): scoring full (4867-clip) clean SV2TTS ceiling" | tee -a "$LOG"
run analysis/clean_bonafide_vs_synth.py --system sv2tts --out-dir "$CEIL_OUT"
echo "$(date): rebuilding tables written by older code" | tee -a "$LOG"
run analysis/rebuild_tables.py
echo "$(date): coverage report" | tee -a "$LOG"
run analysis/verify_coverage.py
echo "$(date): paired comparisons on all clips" | tee -a "$LOG"
run analysis/paired_all.py --workers 6
echo "$(date): finalize_tail complete -> results/paired_stats/" | tee -a "$LOG"
