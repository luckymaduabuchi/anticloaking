#!/usr/bin/env bash
# Re-scores every primary (non-restoration) condition through
# clean_bonafide_vs_synth.py so the score CSVs gain the stem/trial/ref_stem
# columns and a failures/ log (see CSV_COLUMNS there). Same seed and
# sampling as before, so numbers reproduce unless a clip's failure status
# changed (any such change is visible afterwards in failures/ and by
# diffing results_table.csv against the backup).
#
# Backs up the old CSVs + tables first (plots and the restoration trees
# are excluded; disk is nearly full). The clean SV2TTS ceiling is NOT in
# this list -- it must wait for run_clean_sv2tts_full.sh to finish
# (see the CLEAN_SV2TTS line at the bottom, run afterwards).
set -uo pipefail
cd "$(dirname "$0")/.."

RESULTS=/home/vm-user/Desktop/Antifake2026/results
BACKUP=/home/vm-user/Desktop/Antifake2026/results_backup_pre_ids.tar.gz
LOG=/tmp/rescore_with_ids.log
: > "$LOG"

if [ ! -f "$BACKUP" ]; then
  echo "$(date): backing up old score CSVs + tables -> $BACKUP" | tee -a "$LOG"
  (cd "$RESULTS" && find groundtruthvscloaking cleanbonafidevscleansynth groundtruthcomparison \
      \( -path '*groundtruthvsrestoredsynthesis*' -o -path '*/plots/*' \) -prune -o \
      -type f \( -name '*.csv' -o -name '*.csv.bak' \) -print \
    | tar czf "$BACKUP" -T -)
  echo "$(date): backup done ($(du -h "$BACKUP" | cut -f1))" | tee -a "$LOG"
fi

GT="$RESULTS/groundtruthvscloaking"
PAIRS=(
  "POP|$GT/groundtruthvsPOP/gorundtruthvscloaked"
  "attackvc|$GT/groundtruthvsattackvc/groundtruthvscloaked"
  "protectyouraudio|$GT/groundtruthvsprotectyouraudio/groundtruthvscloaked"
  "antifake|$RESULTS/cleanbonafidevscleansynth/ANTIFAKE"
  "f5tts|$RESULTS/groundtruthcomparison/cleanbonafidevscleansynth/F5TTS"
  "seedvc|$RESULTS/groundtruthcomparison/cleanbonafidevscleansynth/SEEDVC"
  "pop_sv2tts|$GT/groundtruthvsPOP/groundtruthvscloakedsynthesis/sv2tts"
  "pop_seedvc|$GT/groundtruthvsPOP/groundtruthvscloakedsynthesis/seedvc"
  "pop_f5tts|$GT/groundtruthvsPOP/groundtruthvscloakedsynthesis/f5tts"
  "attackvc_sv2tts|$GT/groundtruthvsattackvc/groundtruthvscloakedsynthesis/sv2tts"
  "attackvc_seedvc|$GT/groundtruthvsattackvc/groundtruthvscloakedsynthesis/seedvc"
  "attackvc_f5tts|$GT/groundtruthvsattackvc/groundtruthvscloakedsynthesis/f5tts"
  "antifake_sv2tts|$RESULTS/cleanbonafidevscleansynth/ANTIFAKE_SV2TTS"
  "antifake_seedvc|$RESULTS/cleanbonafidevscleansynth/ANTIFAKE_SEEDVC"
  "antifake_f5tts|$RESULTS/cleanbonafidevscleansynth/ANTIFAKE_F5TTS"
  "protectyouraudio_sv2tts|$GT/groundtruthvsprotectyouraudio/groundtruthvscloakedsynthesis/sv2tts"
  "protectyouraudio_seedvc|$GT/groundtruthvsprotectyouraudio/groundtruthvscloakedsynthesis/seedvc"
  "protectyouraudio_f5tts|$GT/groundtruthvsprotectyouraudio/groundtruthvscloakedsynthesis/f5tts"
)

# Optional extra pair(s) passed as args, e.g. the clean SV2TTS ceiling once
# its full-corpus synthesis is done:
#   rescore_with_ids.sh "sv2tts|$RESULTS/groundtruthcomparison/cleanbonafidevscleansynth/SV2TTS"
for extra in "$@"; do PAIRS+=("$extra"); done

for pair in "${PAIRS[@]}"; do
  SYSTEM="${pair%%|*}"
  OUT="${pair##*|}"
  echo "$(date): scoring $SYSTEM -> $OUT" | tee -a "$LOG"
  conda run -n antifake2026 --no-capture-output python -u analysis/clean_bonafide_vs_synth.py \
    --system "$SYSTEM" --out-dir "$OUT" >> "$LOG" 2>&1
  echo "$(date): finished $SYSTEM (exit $?)" | tee -a "$LOG"
done
echo "$(date): all rescoring finished" | tee -a "$LOG"
