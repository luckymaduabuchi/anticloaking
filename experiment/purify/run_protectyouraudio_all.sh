#!/usr/bin/env bash
# Applies all 10 restoration techniques to ProtectYourAudio's
# cloaked_bonafide output, mirroring what's already been done for
# POP/attack-vc/AntiFake. Each *_cloaked_bonafide.py script's
# SOURCE_DIRS/config dicts were extended to include "ProtectYourAudio"
# (2026-09-17) -- running them again is safe and cheap for the other
# three methods since each script's own existing-file check skips
# already-restored clips, so only ProtectYourAudio's ~4850 clips are
# actually processed here. Pure signal processing (no GPU), run
# sequentially to avoid CPU contention across techniques.
set -uo pipefail
cd "$(dirname "$0")"

LOG=/tmp/pya_restoration_all.log
: > "$LOG"

SCRIPTS=(
  adaptive_filter_centroid_cloaked_bonafide.py
  ensemble_averaging_perturbed_cloaked_bonafide.py
  highpass_cloaked_bonafide.py
  lowpass_cloaked_bonafide.py
  lowpass_gain_search_cloaked_bonafide.py
  mel_inversion_cloaked_bonafide.py
  quantization_cloaked_bonafide.py
  re_recording_cloaked_bonafide.py
  resampling_cloaked_bonafide.py
  second_cloak_noise_cloaked_bonafide.py
  spectral_subtraction_cloaked_bonafide.py
)

for script in "${SCRIPTS[@]}"; do
  echo "$(date): starting $script" | tee -a "$LOG"
  conda run -n antifake2026 --no-capture-output python -u "$script" >> "$LOG" 2>&1
  echo "$(date): finished $script" | tee -a "$LOG"
done

echo "$(date): all ProtectYourAudio restoration techniques finished" | tee -a "$LOG"
