# AntiFake2026 experiment

Fully self-contained reenactment: the code lives in this folder
(`experiment/`), the audio data lives in a sibling folder
(`../Dataset/`), and every output this pipeline produces lives in
another sibling folder (`../results/`). No script here imports,
subprocesses, or otherwise calls into any of the older, scattered repos
on this machine (`~/Desktop/AntiFake`, `~/Desktop/protect`,
`~/Downloads/antifake_synthesizer_bundle`, `~/Downloads/LUCKY`,
`~/Downloads/experiment (Copy)`). The exceptions are the `data/prepare_*.py`
scripts, which do one-time **copies** of real, publicly-recorded audio
from local corpora (LibriSpeech, ASVspoof2021, FakeAVCeleb) into
`../Dataset/` -- that's audio data, not code.

```
Antifake2026/
  experiment/    <- this folder, all code
  Dataset/       <- audio data (victims/impostors/decoys + clean_bonafide/)
  results/       <- everything the pipeline produces (CSVs, tables, plots)
  interspeech/   <- paper assets
```

## What this experiment measures

**Threat model:** a victim protects a speech recording with a
*cloaking* system before publishing it, so an attacker can't clone
their voice from it. An attacker downloads the clip, tries one of 10
generic *restoration* techniques to strip the cloak, then feeds the
result into a voice-cloning TTS system. A speaker-verification system
checks whether the resulting clone is mistaken for the real victim.

**Two cloaking systems** are evaluated (`AntiFake`: adversarial
perturbation targeting a decoy speaker; `ProtectYourAudio`: learned
spectral masking that degrades the victim's own embedding), each
reimplemented from scratch in `cloak/` against SpeechBrain ECAPA +
WavLM encoders (see "Design decisions" below for why reimplemented
rather than vendored).

**Three measurement stages**, for every victim utterance:

1. **Baseline** -- the original, *unprotected* audio -> synthesizer -> verify. The ceiling: how well cloning works with no defense at all.
2. **Cloaked (Raw)** -- protected audio, no restoration attempted -> synthesizer -> verify. How much the defense alone degrades cloning.
3. **Cloaked + restored** -- protected audio, one of 10 restoration techniques applied -> synthesizer -> verify, for each technique. Does restoration recover what stage 1 had?

**10 restoration techniques** (matches the paper's own "Inversion
Techniques" figure exactly -- `SecondCloak` is deliberately excluded,
since stacking a second perturbation doesn't restore anything):
LowPass, HighPass, Downsampling, Upsampling, Quantization, Adaptive
Frequency Filtering, Spectral Subtraction, Ensemble Averaging,
Mel-Spectrogram Inversion, Simulated Re-Recording.

**3 speaker-verification systems** score every synthesized clip: SB-ECAPA
(SpeechBrain), Resemblyzer, WavLM.

## Clean-dataset calibration (run this first)

Before the cloak/restore/synthesize pipeline, `Dataset/clean_bonafide/`
establishes how well the 3 verifiers separate genuine (same-speaker)
from impostor (different-speaker) pairs on real, uncloaked,
unsynthesized speech -- the ceiling the rest of the experiment's
numbers get read against. Three real sources, no simulated data:

- **`librispeech/`** -- 500 utterances, LibriSpeech train-clean-100
- **`asvspoof2021/`** -- 500 bonafide-labeled utterances, ASVspoof2021 LA eval (official trial keys)
- **`fakeavceleb/`** -- 3867 unique genuine-audio utterances (deduplicated by content hash) from FakeAVCeleb_v1.2's `RealVideo-RealAudio` + `FakeVideo-RealAudio` subsets, balanced across 5 descents x 2 genders (50 speakers x ~7-8 clips each per group)

Pipeline: `data/prepare_clean_bonafide.py` (copies/dedups audio into
`Dataset/clean_bonafide/`) -> `data/build_clean_bonafide_manifest.py`
(recovers speaker id per file: LibriSpeech from its own filename
convention, ASVspoof2021 from `trial_metadata.txt`, FakeAVCeleb from
its containing `idXXXXX` folder -- verified to match the dataset's own
`meta_data.csv` `source` column for all 21566 rows) ->
`verify/clean_bonafide_metrics.py` (builds genuine/impostor trial
pairs -- within LibriSpeech, within ASVspoof2021, within FakeAVCeleb
overall *and* per descent x gender group, plus cross-corpus impostor
pairs -- and scores them with all 3 verifiers, embeddings cached per
file since the same file appears in many pairs) ->
`analysis/results_table.py` (EER/TAR@FAR table) and
`analysis/clean_bonafide_plots.py` (ROC + score-distribution + FakeAVCeleb
per-group EER bar chart).

**Headline finding:** LibriSpeech scores 0.7-3.9% EER, ASVspoof2021
6.6-14.4% EER, but every one of FakeAVCeleb's 10 descent x gender
groups sits in a 43-53% EER band (near chance) for all 3 verifiers --
verified not a labeling bug (speaker ids cross-checked against
`meta_data.csv`, 0 mismatches across all rows) but a real effect of
restricting impostor trials to the *same* demographic group on short,
in-the-wild, variably-compressed clips (score distributions do show a
correctly-directioned genuine > impostor gap, just swamped by variance).
No group stands out as meaningfully easier/harder than the others.

## Metrics

Primary results table (`analysis/results_table.py`), one row per
(condition, verifier):

| Data | SV | EER | TAR@1% | TAR@0.1% | TAR@0.01% | #T/#I |
|---|---|---|---|---|---|---|

- **Data**: `Baseline`, `<Dataset>/Raw`, or `<Dataset>/<Technique>`
- **SV**: SB-ECAPA / Resemblyzer / WavLM
- **EER**: equal error rate (threshold where FAR=FRR), from the full ROC curve
- **TAR@X%**: true-accept rate at a fixed false-accept rate (1%, 0.1%, 0.01%)
- **#T/#I**: number of target / impostor trials the row is computed from

Every synthesized clip is scored against the real victim (1 target
trial) **and every utterance in a much larger impostor pool** (many
impostor trials per clip) -- verification is cheap, cloak generation
isn't, so this is how low-FAR operating points get enough trials to be
meaningful without extra expensive synthesis runs.

Supplementary: `analysis/roc_curves.py` (full ROC, baseline vs. cloaked
vs. restored), `analysis/score_distributions.py` (target/impostor score
histograms), `analysis/similarity_bar_chart.py` (mean-score bar chart).

Audio quality (`analysis/audio_quality.py`), one row per `<Dataset>/Raw`
or `<Dataset>/<Technique>` condition -- victim original vs. cloaked (or
cloaked-then-restored) audio:

| Data | STOI_mean | STOI_median | PESQ_mean | PESQ_median | SI_SDR_mean_dB | SI_SDR_median_dB | N |
|---|---|---|---|---|---|---|---|

STOI/PESQ/SI-SDR all need a same-content, sample-aligned reference vs.
degraded pair, so this table deliberately excludes `Baseline` and every
TTS-cloned condition (different linguistic content than the victim's
own recording -- there's no aligned reference to compare against).
Requires `purify/run_all.py` to have produced `purify_output/` first.

## Pipeline stages

**Clean-dataset calibration** (run first; only needs stdlib + the audio libs, not the cloak/synth stack):

| # | Stage | Script |
|---|-------|--------|
| 0a | Copy/dedup real audio into `Dataset/clean_bonafide/` | `data/prepare_clean_bonafide.py` |
| 0b | Recover speaker ids, write `Dataset/clean_bonafide/manifest.json` | `data/build_clean_bonafide_manifest.py` |
| 0c | Build trials, score with 3 verifiers | `verify/clean_bonafide_metrics.py` |
| 0d | EER/TAR@FAR table (also covers stage 6 below) + ROC/distribution/per-group plots | `analysis/results_table.py`, `analysis/clean_bonafide_plots.py` |

**Main cloak/restore/synthesize experiment:**

| # | Stage | Script |
|---|-------|--------|
| 1 | Copy real audio, build manifest | `data/prepare_manifest.py` |
| 2a | Generate AntiFake cloaks (PGD vs. decoy speaker) | `cloak/generate_antifake.py` |
| 2b | Generate ProtectYourAudio cloaks (learned spectral mask) | `cloak/generate_protect.py` |
| 3 | Apply 10 restoration techniques (+ Raw passthrough) | `purify/run_all.py` |
| 4 | Voice-clone: Baseline, Raw, and every restored variant | `synth/synthesize.py` |
| 5 | Score with 3 verifiers, target + full impostor pool | `verify/run_all.py` |
| 5b | STOI/PESQ/SI-SDR: victim vs. cloaked/restored (needs stage 3's output) | `analysis/audio_quality.py` |
| 6 | EER/TAR@FAR table + ROC + distributions + bar chart | `analysis/run_all.py` |

Everything runs in a **single** conda environment (`antifake2026`) --
no more juggling three envs for three vendored codebases.

## One-time environment setup

```bash
conda env create -f environments/antifake2026.yml
```

## Running the pipeline

Clean-dataset calibration (produces the LibriSpeech/ASVspoof2021/FakeAVCeleb
EER table and plots):

```bash
conda activate antifake2026
cd experiment
python data/prepare_clean_bonafide.py
python data/build_clean_bonafide_manifest.py
python verify/clean_bonafide_metrics.py
python analysis/results_table.py
python analysis/clean_bonafide_plots.py
```

Main experiment:

```bash
bash run_pipeline.sh
```

or run each stage yourself, in order (see the tables above) -- every
stage is resumable, skipping files/rows that already exist.

Outputs, all under `../results/` (sibling to `experiment/`):
- `verify/csvs/<Data>__<Technique>__<Model>.csv` -- real measured `score,label` pairs (both the clean-dataset calibration and the main experiment write here)
- `analysis/results_table.csv` -- primary EER/TAR@FAR table (all conditions, both pipelines)
- `analysis/plots/` -- `clean_bonafide_*.png` (calibration) and `roc_curves.png`/`score_distributions.png`/`similarity_bar_chart.png` (main experiment)

Audio outputs stay under `experiment/` (not `results/`, since they're large
intermediate artifacts, not results per se):
- `cloak_output/{antifake,protect}/` -- cloaked audio, one file per victim
- `purify_output/<Technique-or-Raw>/<Dataset>/` -- restored variants
- `synth_output/{Baseline,<Dataset>/<Technique-or-Raw>}/` -- voice-cloned attack attempts

And `Dataset/` (sibling to `experiment/`) holds all source audio:
`{victims,impostors,decoys}/` + `manifest.json` for the main experiment,
`clean_bonafide/{librispeech,asvspoof2021,fakeavceleb}/` + `manifest.json`
for the calibration stage.

## Design decisions worth knowing about

- **Cloaks are reimplemented, not vendored.** The original AntiFake
  repo needs Python 3.7/torch 1.13 and a whole RTVC+AVC+CoquiTTS+Tortoise
  stack; ProtectYourAudio needs its own chou/autovc/sv2tts model zoo.
  Vendoring both would mean carrying two more heavyweight, older
  dependency trees into this folder and losing the single-env setup.
  Instead:
  - **AntiFake-style**: bounded L-infinity PGD in the raw waveform
    domain, minimizing an ensemble embedding distance (SpeechBrain
    ECAPA + WavLM) to a decoy speaker selected the same way the
    original paper does (farthest initial embedding from the victim).
  - **ProtectYourAudio-style**: a learned magnitude mask over
    frequency x time blocks of the spectrogram (phase preserved),
    optimized to push the audio's *own* embedding away from itself
    (untargeted) while a distortion penalty keeps the mask near 1.
  - This means these cloaks won't be bit-identical to what the
    original papers' code produces, but they follow the same
    optimization idea documented in each paper.
- **Voice-cloning synthesizer**: Coqui TTS's YourTTS, pip-installable
  and called in-process -- same zero-shot cloning family the original
  AntiFake paper evaluated against, no vendored RTVC checkout needed.
- **`NUM_VICTIM_UTTERANCES` (config.py, default 8)** keeps the
  expensive stages (cloak generation, synthesis) tractable. Raise it
  once the pipeline's been validated end to end.
- **EER at very low sample counts is noisy.** With single-digit victim
  counts, `TAR@0.01%FAR` in particular is an interpolated estimate, not
  a directly observed rate (that needs on the order of 10,000 impostor
  trials). The results table is still useful for relative comparison
  across techniques, but don't over-read the absolute numbers until
  you've scaled up victim/impostor counts.
