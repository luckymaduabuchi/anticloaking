# Security Analysis of Anti-Cloaking Schemes

Code and results for a reproduction and security evaluation of four proactive
audio-cloaking defenses (POP, attack-vc, AntiFake, ProtectYourAudio) against
three zero-shot voice-cloning/conversion systems (SV2TTS, Seed-VC, F5-TTS),
including an adaptive-attacker restoration study testing whether generic
signal-processing techniques can undo each cloak's protection.

**Digital Forensics Research Group**, Department of Electrical and Computer
Engineering, Iowa State University.
Lucky Onyekwelu-Udoka (lucky@iastate.edu) · Guan Yong (guan@iastate.edu)

## Contents

- `Paper/` — the full paper (LaTeX source + figures).
- `Presentation/` — the research poster and slide-deck build scripts
  (python-pptx), plus their rendered `.pptx` outputs.
- `experiment/analysis/` — the scoring pipeline: speaker-verification
  trial construction, EER/TAR/minDCF/ROC-AUC computation, cluster-bootstrap
  confidence intervals, and the paired protective-efficacy / restoration-
  reversal statistical comparisons.
- `experiment/purify/` — implementations of the ten restoration
  ("anti-cloaking") techniques tested against each cloak (filtering,
  resampling, quantization, spectral subtraction, simulated re-recording,
  ensemble averaging, second-cloak application, …).
- `experiment/verify/` — wrapper scripts around the three speaker
  verifiers used throughout (SpeechBrain ECAPA-TDNN, Resemblyzer, WavLM).
- `results/` — every score table, results table, and paired-comparison
  CSV produced by the pipeline above (numbers only — no audio).

## Not included

This is a subset of a larger private project. Excluded, and not tracked
here:

- **Audio data** (the underlying speech corpora and every cloaked/
  restored/re-cloned clip produced during the experiment) — not ours to
  redistribute and far too large for a git repository.
- **Vendored third-party model code and weights** for the reproduced
  cloaking/synthesis systems (POP, attack-vc, AntiFake, ProtectYourAudio,
  SV2TTS, F5-TTS) — each has its own upstream repository and license; see
  the paper's citations for the original sources.

## Paper

See `Paper/` for the full write-up, or the poster in `Presentation/` for a
one-page summary.
