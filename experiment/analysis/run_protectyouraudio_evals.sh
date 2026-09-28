#!/usr/bin/env bash
# Chains the ProtectYourAudio evaluation sequence: waits for the
# already-running groundtruthvscloaked (imperceptibility) job (pid
# passed as $1) to finish, then runs the three protective-efficacy
# evaluations (cloaked_synthesize vs clean_bonafide, one per
# downstream synthesizer) one at a time. All via clean_bonafide_vs_synth.py,
# whose SYSTEM_DIRS now includes protectyouraudio/protectyouraudio_sv2tts/
# protectyouraudio_seedvc/protectyouraudio_f5tts (added 2026-09-17,
# mirroring POP/attack-vc/AntiFake's existing entries). conda run now
# auto-sets LD_PRELOAD via the antifake2026 env's activate.d hook (fixes
# the pandas-vs-soxr libstdc++ symbol-version bug found the same day),
# so no manual env var needed here.
set -uo pipefail
cd "$(dirname "$0")/.."

WAIT_PID="$1"
OUT_ROOT=/home/vm-user/Desktop/Antifake2026/results/groundtruthvscloaking/groundtruthvsprotectyouraudio/groundtruthvscloakedsynthesis
LOG=/tmp/pya_evals_chain.log
: > "$LOG"

echo "$(date): waiting for groundtruthvscloaked job (pid $WAIT_PID) to finish" | tee -a "$LOG"
tail --pid="$WAIT_PID" -f /dev/null 2>/dev/null
echo "$(date): groundtruthvscloaked done, starting protective-efficacy evals" | tee -a "$LOG"

for synth in sv2tts seedvc f5tts; do
  out_dir="$OUT_ROOT/$synth"
  mkdir -p "$out_dir"
  echo "$(date): starting protectyouraudio_$synth" | tee -a "$LOG"
  conda run -n antifake2026 --no-capture-output python -u analysis/clean_bonafide_vs_synth.py \
    --system "protectyouraudio_$synth" --out-dir "$out_dir" >> "$LOG" 2>&1
  echo "$(date): finished protectyouraudio_$synth" | tee -a "$LOG"
done

echo "$(date): all ProtectYourAudio protective-efficacy evals finished" | tee -a "$LOG"
