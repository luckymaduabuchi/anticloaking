"""Central configuration for the AntiFake2026 reenactment experiment.

Fully self-contained: every stage below is implemented with plain
pip-installable libraries (torch, torchaudio, speechbrain, resemblyzer,
transformers, TTS, librosa, scipy). Nothing calls into, imports from,
or subprocesses out to any of the old external repos on this machine
(~/Desktop/AntiFake, ~/Desktop/protect, ~/Downloads/antifake_synthesizer_bundle,
~/Downloads/LUCKY, ~/Downloads/experiment (Copy)). The only thing this
experiment takes from those locations is a one-time COPY of a handful
of real, publicly-recorded speech .wav files (see data/prepare_manifest.py),
used purely as raw audio data, not code.

One deliberate exception: SV2TTS (synth/sv2tts/) is a *vendored* copy of
Real-Time-Voice-Cloning -- there's no pip package for it, so it's been
copied wholesale into this folder (not called from outside) and runs in
its own env (ENV_SV2TTS) since its pinned dependencies (numpy 1.20,
torch 1.13) can't coexist with the rest of the antifake2026 env.
"""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

# -----------------------------------------------------------------------
# Single conda environment for the whole pipeline (see environments/antifake2026.yml).
# -----------------------------------------------------------------------
ENV_NAME = "antifake2026"

# -----------------------------------------------------------------------
# One-time real-audio source, used only to seed data/raw/ with real
# speech (see data/prepare_manifest.py). Read-only, data only.
# -----------------------------------------------------------------------
EXTERNAL_AUDIO_POOL = "/home/vm-user/Desktop/AntiFake/speakers_database"
EXTERNAL_VICTIM_SAMPLES = "/home/vm-user/Desktop/AntiFake/samples"
EXTERNAL_LARGE_POOL = "/home/vm-user/Desktop/protect/project/acsac/target_speaker"

# -----------------------------------------------------------------------
# Dataset location. Kept at the Antifake2026 project level (sibling to
# this experiment/ folder), per explicit placement request, rather than
# nested under experiment/data/.
# -----------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(ROOT)
RAW_DIR = os.path.join(PROJECT_ROOT, "Dataset")
VICTIM_DIR = os.path.join(RAW_DIR, "victims")
IMPOSTOR_DIR = os.path.join(RAW_DIR, "impostors")
DECOY_DIR = os.path.join(RAW_DIR, "decoys")
MANIFEST_PATH = os.path.join(RAW_DIR, "manifest.json")

# -----------------------------------------------------------------------
# "Does voice cloning preserve identity at all" sanity check: clone
# each Dataset/victims/ clip with two real zero-shot TTS systems and
# check whether the 3 judges still recognize it as the same speaker.
# -----------------------------------------------------------------------
CLEAN_SYNTHESIZE_DIR = os.path.join(RAW_DIR, "clean_synthesize")
CLEAN_SYNTHESIZE_SV2TTS_DIR = os.path.join(CLEAN_SYNTHESIZE_DIR, "sv2tts")
CLEAN_SYNTHESIZE_F5TTS_DIR = os.path.join(CLEAN_SYNTHESIZE_DIR, "f5tts")
CLEAN_SYNTHESIZE_SEEDVC_DIR = os.path.join(CLEAN_SYNTHESIZE_DIR, "seedvc")

# Protective-efficacy step: clone the POP-*cloaked* recordings (not the
# clean originals) with the same three systems, so the resulting clones
# can be compared back against clean_bonafide to see whether POP's
# perturbation actually degrades what a downstream cloning attacker
# extracts (as opposed to tab:calibration/tab:synth-ceiling, which only
# establish the clean-audio baseline this is meant to be compared to).
CLOAKED_BONAFIDE_POP_DIR = os.path.join(RAW_DIR, "cloaked_bonafide", "POP")
CLOAKED_SYNTHESIZE_POP_DIR = os.path.join(RAW_DIR, "cloaked_synthesize", "POP")
CLOAKED_SYNTHESIZE_POP_SV2TTS_DIR = os.path.join(CLOAKED_SYNTHESIZE_POP_DIR, "sv2tts")
CLOAKED_SYNTHESIZE_POP_F5TTS_DIR = os.path.join(CLOAKED_SYNTHESIZE_POP_DIR, "f5tts")
CLOAKED_SYNTHESIZE_POP_SEEDVC_DIR = os.path.join(CLOAKED_SYNTHESIZE_POP_DIR, "seedvc")

# Same protective-efficacy step, for attack-vc's cloaked output.
CLOAKED_BONAFIDE_ATTACKVC_DIR = os.path.join(RAW_DIR, "cloaked_bonafide", "attackvc")
CLOAKED_SYNTHESIZE_ATTACKVC_DIR = os.path.join(RAW_DIR, "cloaked_synthesize", "attack-vc")
CLOAKED_SYNTHESIZE_ATTACKVC_SV2TTS_DIR = os.path.join(CLOAKED_SYNTHESIZE_ATTACKVC_DIR, "sv2tts")
CLOAKED_SYNTHESIZE_ATTACKVC_SEEDVC_DIR = os.path.join(CLOAKED_SYNTHESIZE_ATTACKVC_DIR, "seedvc")
CLOAKED_SYNTHESIZE_ATTACKVC_F5TTS_DIR = os.path.join(CLOAKED_SYNTHESIZE_ATTACKVC_DIR, "f5tts")

# Same protective-efficacy step, for AntiFake's cloaked output.
CLOAKED_BONAFIDE_ANTIFAKE_DIR = os.path.join(RAW_DIR, "cloaked_bonafide", "Antifake")
CLOAKED_SYNTHESIZE_ANTIFAKE_DIR = os.path.join(RAW_DIR, "cloaked_synthesize", "Antifake")
CLOAKED_SYNTHESIZE_ANTIFAKE_SV2TTS_DIR = os.path.join(CLOAKED_SYNTHESIZE_ANTIFAKE_DIR, "sv2tts")
CLOAKED_SYNTHESIZE_ANTIFAKE_SEEDVC_DIR = os.path.join(CLOAKED_SYNTHESIZE_ANTIFAKE_DIR, "seedvc")
CLOAKED_SYNTHESIZE_ANTIFAKE_F5TTS_DIR = os.path.join(CLOAKED_SYNTHESIZE_ANTIFAKE_DIR, "f5tt5")

# Same protective-efficacy step, for ProtectYourAudio's cloaked output.
CLOAKED_BONAFIDE_PROTECTYOURAUDIO_DIR = os.path.join(RAW_DIR, "cloaked_bonafide", "ProtectYourAudio")
CLOAKED_SYNTHESIZE_PROTECTYOURAUDIO_DIR = os.path.join(RAW_DIR, "cloaked_synthesize", "ProtectYourAudio")
CLOAKED_SYNTHESIZE_PROTECTYOURAUDIO_SV2TTS_DIR = os.path.join(CLOAKED_SYNTHESIZE_PROTECTYOURAUDIO_DIR, "sv2tts")
CLOAKED_SYNTHESIZE_PROTECTYOURAUDIO_SEEDVC_DIR = os.path.join(CLOAKED_SYNTHESIZE_PROTECTYOURAUDIO_DIR, "seedvc")
CLOAKED_SYNTHESIZE_PROTECTYOURAUDIO_F5TTS_DIR = os.path.join(CLOAKED_SYNTHESIZE_PROTECTYOURAUDIO_DIR, "f5tts")

# Adaptive-attacker test: LowPassFiltering applied to the cloaked audio
# *before* cloning (purify/lowpass_cloaked_bonafide.py), to check
# whether a knowledgeable attacker can restore what the cloak degraded.
RESTORATION_TECHNIQUES_DIR = os.path.join(RAW_DIR, "restoration techniques")
CLOAKED_BONAFIDE_LOWPASS_DIR = os.path.join(RESTORATION_TECHNIQUES_DIR, "low_pass")
CLOAKED_BONAFIDE_LOWPASS_POP_DIR = os.path.join(CLOAKED_BONAFIDE_LOWPASS_DIR, "POP")
CLOAKED_BONAFIDE_LOWPASS_ATTACKVC_DIR = os.path.join(CLOAKED_BONAFIDE_LOWPASS_DIR, "attackvc")
CLOAKED_BONAFIDE_LOWPASS_PROTECTYOURAUDIO_DIR = os.path.join(CLOAKED_BONAFIDE_LOWPASS_DIR, "ProtectYourAudio")
CLOAKED_SYNTHESIZE_POP_LOWPASS_SV2TTS_DIR = os.path.join(CLOAKED_SYNTHESIZE_POP_DIR, "sv2tts_lowpass")
CLOAKED_SYNTHESIZE_ATTACKVC_LOWPASS_SV2TTS_DIR = os.path.join(CLOAKED_SYNTHESIZE_ATTACKVC_DIR, "sv2tts_lowpass")

# Low-pass + gain-multiplier sweep (purify/lowpass_gain.py, the paper's
# "gain multiplier search" method) -- one restored-audio dir per (cloak
# method, gain value), and one downstream-synthesis dir per (cloak
# method, gain value, synthesizer) across all three systems in
# Table~tab:synth (SV2TTS, Seed-VC, F5-TTS), not just SV2TTS.
LOWPASS_GAIN_VALUES = (1.2, 1.4, 1.6, 1.8, 2.0)
LOWPASS_GAIN_SYNTHESIZERS = ("sv2tts", "seedvc", "f5tts")
LOWPASS_GAIN_DIR = os.path.join(RESTORATION_TECHNIQUES_DIR, "low_pass_gain")
CLOAKED_BONAFIDE_LOWPASS_GAIN_DIRS = {
    (method, gain): os.path.join(LOWPASS_GAIN_DIR, method, f"gain_{gain}")
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
    for gain in LOWPASS_GAIN_VALUES
}
# Downstream clones of the restored (low-pass + gain) audio -- kept
# self-contained under its own tree (one gain folder per cloak method,
# each with its own sv2tts/f5tts/seedvc subfolders) rather than mixed
# into the plain cloaked_synthesize/ tree used by the no-restoration
# protective-efficacy runs.
RESTORED_SYNTHESIZE_DIR = os.path.join(RAW_DIR, "restored_synthesize")
LOWPASS_GAIN_SYNTH_DIR = os.path.join(RESTORED_SYNTHESIZE_DIR, "Low_pass")
CLOAKED_SYNTHESIZE_LOWPASS_GAIN_DIRS = {
    (method, gain, synth): os.path.join(LOWPASS_GAIN_SYNTH_DIR, method, f"gain_{gain}", synth)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
    for gain in LOWPASS_GAIN_VALUES
    for synth in LOWPASS_GAIN_SYNTHESIZERS
}

# Adaptive frequency filtering (purify/adaptive_filter_centroid.py, the
# paper's centroid-based high-pass+low-pass method) -- one restored-audio
# dir per cloak method, one downstream-synthesis dir per (cloak method,
# synthesizer). Single alpha/beta default, no sweep (unlike the low-pass
# gain multiplier, the paper doesn't call for sweeping alpha/beta).
ADAPTIVE_FILTER_CENTROID_DIR = os.path.join(RESTORATION_TECHNIQUES_DIR, "adaptive_filter_centroid")
CLOAKED_BONAFIDE_ADAPTIVE_FILTER_CENTROID_DIRS = {
    method: os.path.join(ADAPTIVE_FILTER_CENTROID_DIR, method)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
}
ADAPTIVE_FILTER_CENTROID_SYNTH_DIR = os.path.join(RESTORED_SYNTHESIZE_DIR, "Adaptive_filter_centroid")
CLOAKED_SYNTHESIZE_ADAPTIVE_FILTER_CENTROID_DIRS = {
    (method, synth): os.path.join(ADAPTIVE_FILTER_CENTROID_SYNTH_DIR, method, synth)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
    for synth in LOWPASS_GAIN_SYNTHESIZERS
}

# Ensemble averaging of perturbed variants (purify/ensemble_averaging_perturbed.py,
# the paper's N-lightly-perturbed-copies method) -- one restored-audio dir
# per cloak method, one downstream-synthesis dir per (cloak method, synthesizer).
ENSEMBLE_AVERAGING_PERTURBED_DIR = os.path.join(RESTORATION_TECHNIQUES_DIR, "ensemble_averaging_perturbed")
CLOAKED_BONAFIDE_ENSEMBLE_AVERAGING_PERTURBED_DIRS = {
    method: os.path.join(ENSEMBLE_AVERAGING_PERTURBED_DIR, method)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
}
ENSEMBLE_AVERAGING_PERTURBED_SYNTH_DIR = os.path.join(RESTORED_SYNTHESIZE_DIR, "Ensemble_averaging_perturbed")
CLOAKED_SYNTHESIZE_ENSEMBLE_AVERAGING_PERTURBED_DIRS = {
    (method, synth): os.path.join(ENSEMBLE_AVERAGING_PERTURBED_SYNTH_DIR, method, synth)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
    for synth in LOWPASS_GAIN_SYNTHESIZERS
}

# QuantizationFiltering (purify/quantization.py, already faithful to the
# paper's bit-depth quantize/dequantize method -- no new module needed).
QUANTIZATION_DIR = os.path.join(RESTORATION_TECHNIQUES_DIR, "quantization")
CLOAKED_BONAFIDE_QUANTIZATION_DIRS = {
    method: os.path.join(QUANTIZATION_DIR, method)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
}
QUANTIZATION_SYNTH_DIR = os.path.join(RESTORED_SYNTHESIZE_DIR, "Quantization")
CLOAKED_SYNTHESIZE_QUANTIZATION_DIRS = {
    (method, synth): os.path.join(QUANTIZATION_SYNTH_DIR, method, synth)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
    for synth in LOWPASS_GAIN_SYNTHESIZERS
}

# Resampling (purify/downsample.py + purify/upsample.py, already
# faithful to the paper's decimation / zero-insertion+interpolation
# description -- the round-trip back to the original sample rate is a
# pipeline-compatibility necessity, not a deviation: it can't recover
# content above the intermediate rate's Nyquist either way, matching
# the paper's own "upsampling cannot add new information" caveat). Two
# variants under one technique, like low-pass+gain's gain values.
RESAMPLING_VARIANTS = ("downsample", "upsample")
RESAMPLING_DIR = os.path.join(RESTORATION_TECHNIQUES_DIR, "resampling")
CLOAKED_BONAFIDE_RESAMPLING_DIRS = {
    (method, variant): os.path.join(RESAMPLING_DIR, method, variant)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
    for variant in RESAMPLING_VARIANTS
}
RESAMPLING_SYNTH_DIR = os.path.join(RESTORED_SYNTHESIZE_DIR, "Resampling")
CLOAKED_SYNTHESIZE_RESAMPLING_DIRS = {
    (method, variant, synth): os.path.join(RESAMPLING_SYNTH_DIR, method, variant, synth)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
    for variant in RESAMPLING_VARIANTS
    for synth in LOWPASS_GAIN_SYNTHESIZERS
}

# Mel-spectrogram inversion (purify/mel_inversion.py, already faithful
# to the paper's mel-projection + Griffin-Lim reconstruction method).
MEL_INVERSION_DIR = os.path.join(RESTORATION_TECHNIQUES_DIR, "mel_spectrogram_inversion")
CLOAKED_BONAFIDE_MEL_INVERSION_DIRS = {
    method: os.path.join(MEL_INVERSION_DIR, method)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
}
MEL_INVERSION_SYNTH_DIR = os.path.join(RESTORED_SYNTHESIZE_DIR, "Mel_spectrogram_inversion")
CLOAKED_SYNTHESIZE_MEL_INVERSION_DIRS = {
    (method, synth): os.path.join(MEL_INVERSION_SYNTH_DIR, method, synth)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
    for synth in LOWPASS_GAIN_SYNTHESIZERS
}

# Re-recording / simulated analog channel (purify/sim_rerecord.py,
# already faithful to the paper's x_cloaked + sensor-noise +
# RIR/ambient-interference description).
RE_RECORDING_DIR = os.path.join(RESTORATION_TECHNIQUES_DIR, "re_recording")
CLOAKED_BONAFIDE_RE_RECORDING_DIRS = {
    method: os.path.join(RE_RECORDING_DIR, method)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
}
RE_RECORDING_SYNTH_DIR = os.path.join(RESTORED_SYNTHESIZE_DIR, "Re_recording")
CLOAKED_SYNTHESIZE_RE_RECORDING_DIRS = {
    (method, synth): os.path.join(RE_RECORDING_SYNTH_DIR, method, synth)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
    for synth in LOWPASS_GAIN_SYNTHESIZERS
}

# Second-cloak application: x_double = x_original + p1 + p2 -- re-run
# the SAME cloaking attack a second time, this time against the
# already-cloaked output rather than the clean_bonafide original, to
# test whether layered perturbations interfere destructively. Unlike
# every other restoration technique, this is not a lightweight signal-
# processing transform -- it re-invokes the actual cloak-generation
# pipeline (POP's 200-step PGD, attack-vc's embedding attack), so it's
# roughly as expensive as the original cloaking run itself.
SECOND_CLOAK_DIR = os.path.join(RESTORATION_TECHNIQUES_DIR, "second_cloak_application")
CLOAKED_BONAFIDE_SECOND_CLOAK_DIRS = {
    method: os.path.join(SECOND_CLOAK_DIR, method)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
}
SECOND_CLOAK_SYNTH_DIR = os.path.join(RESTORED_SYNTHESIZE_DIR, "Second_cloak_application")
CLOAKED_SYNTHESIZE_SECOND_CLOAK_DIRS = {
    (method, synth): os.path.join(SECOND_CLOAK_SYNTH_DIR, method, synth)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
    for synth in LOWPASS_GAIN_SYNTHESIZERS
}

# Second-cloak application, corrected definition (purify/second_cloak_noise.py):
# a cloak-agnostic attacker adds generic Gaussian noise on top of
# already-cloaked audio, rather than re-running a specific cloak's own
# attack (which the attacker has no way to know or reproduce -- that
# was the flaw in the SECOND_CLOAK_DIR constants above, whose output is
# left untouched, not deleted). Separate directory tree so this never
# collides with the earlier, incorrect implementation's output.
SECOND_CLOAK_NOISE_DIR = os.path.join(RESTORATION_TECHNIQUES_DIR, "second_cloak_noise")
CLOAKED_BONAFIDE_SECOND_CLOAK_NOISE_DIRS = {
    method: os.path.join(SECOND_CLOAK_NOISE_DIR, method)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
}
SECOND_CLOAK_NOISE_SYNTH_DIR = os.path.join(RESTORED_SYNTHESIZE_DIR, "Second_cloak_noise")
CLOAKED_SYNTHESIZE_SECOND_CLOAK_NOISE_DIRS = {
    (method, synth): os.path.join(SECOND_CLOAK_NOISE_SYNTH_DIR, method, synth)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
    for synth in LOWPASS_GAIN_SYNTHESIZERS
}

# Spectral subtraction (purify/spectral_subtraction.py, already
# faithful to the paper's |X| = |Y| - |N| method with rectification --
# floored rather than clipped to zero, a standard refinement to avoid
# musical-noise artifacts, not a deviation from the paper's mechanism).
SPECTRAL_SUBTRACTION_DIR = os.path.join(RESTORATION_TECHNIQUES_DIR, "spectral_subtraction")
CLOAKED_BONAFIDE_SPECTRAL_SUBTRACTION_DIRS = {
    method: os.path.join(SPECTRAL_SUBTRACTION_DIR, method)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
}
SPECTRAL_SUBTRACTION_SYNTH_DIR = os.path.join(RESTORED_SYNTHESIZE_DIR, "Spectral_subtraction")
CLOAKED_SYNTHESIZE_SPECTRAL_SUBTRACTION_DIRS = {
    (method, synth): os.path.join(SPECTRAL_SUBTRACTION_SYNTH_DIR, method, synth)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
    for synth in LOWPASS_GAIN_SYNTHESIZERS
}

# High-pass filtering (purify/highpass.py, already faithful to the
# paper's ideal H_HP(f) brick-wall response -- realized as a practical
# order-10 Butterworth high-pass, the same ideal-to-realizable
# translation already used for low-pass/adaptive-filter-centroid).
HIGHPASS_DIR = os.path.join(RESTORATION_TECHNIQUES_DIR, "highpass")
CLOAKED_BONAFIDE_HIGHPASS_DIRS = {
    method: os.path.join(HIGHPASS_DIR, method)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
}
HIGHPASS_SYNTH_DIR = os.path.join(RESTORED_SYNTHESIZE_DIR, "Highpass")
CLOAKED_SYNTHESIZE_HIGHPASS_DIRS = {
    (method, synth): os.path.join(HIGHPASS_SYNTH_DIR, method, synth)
    for method in ("POP", "attackvc", "Antifake", "ProtectYourAudio")
    for synth in LOWPASS_GAIN_SYNTHESIZERS
}

SV2TTS_REPO = os.path.join(ROOT, "synth", "sv2tts")
ENV_SV2TTS = "sv2tts_vendored"

SEEDVC_REPO = os.path.join(ROOT, "synth", "seedvc_vendored")
ENV_SEEDVC = "seedvc_vendored"
# Seed-VC is voice *conversion* (content + timbre in, converted-timbre
# audio out), not TTS -- it needs a source clip to supply the linguistic
# content. Reuse the same fixed content clip for every clean_bonafide
# target, mirroring how SYNTH_TEXT below is held fixed across every TTS
# clone: content stays constant, only the cloned identity varies.
SEEDVC_SOURCE_CONTENT = os.path.join(
    ROOT, "cloak", "protectyouraudio_vendored", "source_speaker", "content.wav"
)

CLOAK_DIR = os.path.join(ROOT, "cloak_output")
CLOAK_ANTIFAKE_DIR = os.path.join(CLOAK_DIR, "antifake")
CLOAK_PROTECT_DIR = os.path.join(CLOAK_DIR, "protect")

PURIFY_DIR = os.path.join(ROOT, "purify_output")
SYNTH_DIR = os.path.join(ROOT, "synth_output")

# -----------------------------------------------------------------------
# Results location. Also kept at the Antifake2026 project level (sibling
# to experiment/ and Dataset/), same reasoning as Dataset's placement --
# outputs live separately from code.
# -----------------------------------------------------------------------
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
VERIFY_DIR = os.path.join(RESULTS_DIR, "verify")
CSV_DIR = os.path.join(VERIFY_DIR, "csvs")

ANALYSIS_DIR = os.path.join(RESULTS_DIR, "analysis")
PLOTS_DIR = os.path.join(ANALYSIS_DIR, "plots")

# -----------------------------------------------------------------------
# The three measurement stages (see README.md "The three measurement points"):
#   1. BASELINE_LABEL   -- original, unprotected audio -> synth -> verify
#   2. RAW_LABEL        -- cloaked audio, no restoration -> synth -> verify
#   3. TECHNIQUES       -- cloaked audio, restoration technique applied -> synth -> verify
# -----------------------------------------------------------------------
BASELINE_LABEL = "Baseline"
RAW_LABEL = "Raw"

DATASETS = ["AntiFake", "ProtectYourAudio"]

# The 10 restoration/inversion techniques (matches the paper's own
# "Inversion Techniques" figure exactly). SecondCloak is deliberately
# excluded: it stacks a second perturbation rather than restoring
# anything, so it isn't a restoration technique.
TECHNIQUES = [
    "LowPassFiltering",
    "HighPassFiltering",
    "Downsampling",
    "Upsampling",
    "QuantizationFiltering",
    "AdaptiveFiltering",
    "SpectralSubtraction",
    "EnsembleAveraging",
    "MelSpectrogram",
    "SimulatedReRecord",
]

VERIFIER_MODELS = ["SpeechBrain", "Resemblyzer", "WavLM"]

# Fixed FAR operating points reported in the results table.
FAR_OPERATING_POINTS = [0.01, 0.001, 0.0001]  # 1%, 0.1%, 0.01%

SAMPLE_RATE = 16000

SYNTH_TEXT = (
    "This is a test of the voice cloning system used to evaluate audio protection methods. "
    "Please listen carefully and notice how closely the synthesized voice matches the original "
    "speaker across different words, tones, and sentence rhythms. Every recording, whether real "
    "or generated, carries subtle traces of the speaker's identity that these systems are "
    "designed to detect."
)

# -----------------------------------------------------------------------
# Scale. Cloak generation + synthesis are the expensive steps (one PGD/
# mask-search optimization and one TTS clone per victim per condition),
# so victim count stays modest. Verification scoring is cheap, so the
# impostor pool is scored many-to-one against every synthesized clip to
# get a statistically usable number of impostor trials for the low-FAR
# operating points, without needing extra expensive synthesis runs.
# -----------------------------------------------------------------------
NUM_VICTIM_UTTERANCES = 8
NUM_IMPOSTOR_UTTERANCES = 20   # scored many-to-one against every synthesized clip
NUM_DECOY_UTTERANCES = 10      # candidate decoy-target pool for AntiFake-style cloaking

# -----------------------------------------------------------------------
# Cloak generation hyperparameters (self-contained reimplementations).
# -----------------------------------------------------------------------
ANTIFAKE_PGD_STEPS = 300
ANTIFAKE_PGD_STEP_SIZE = 0.0008
ANTIFAKE_LINF_BUDGET = 0.02       # max |perturbation| per sample, in [-1, 1] audio scale

PROTECT_MASK_STEPS = 300
PROTECT_MASK_LR = 0.05
PROTECT_MASK_MIN_GAIN = 0.15      # magnitude floor per mel-bin (can't fully zero a bin)


def ensure_dirs():
    for d in [
        VICTIM_DIR, IMPOSTOR_DIR, DECOY_DIR,
        CLOAK_ANTIFAKE_DIR, CLOAK_PROTECT_DIR,
        PURIFY_DIR, SYNTH_DIR, CSV_DIR, PLOTS_DIR,
        CLEAN_SYNTHESIZE_SV2TTS_DIR, CLEAN_SYNTHESIZE_F5TTS_DIR, CLEAN_SYNTHESIZE_SEEDVC_DIR,
        CLOAKED_SYNTHESIZE_POP_SV2TTS_DIR, CLOAKED_SYNTHESIZE_POP_F5TTS_DIR, CLOAKED_SYNTHESIZE_POP_SEEDVC_DIR,
        CLOAKED_SYNTHESIZE_ATTACKVC_SV2TTS_DIR, CLOAKED_SYNTHESIZE_ATTACKVC_SEEDVC_DIR,
        CLOAKED_SYNTHESIZE_ATTACKVC_F5TTS_DIR,
    ]:
        os.makedirs(d, exist_ok=True)
