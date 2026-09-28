"""EnsembleAveraging: run several independent purification techniques
and average their outputs sample-by-sample. Each technique attacks a
different property (frequency band, bit depth, mel projection); a
perturbation that survives any single one may not survive all of them
at once, so averaging can cancel residual adversarial structure while
speech content -- shared across all variants -- reinforces itself.
"""
import numpy as np

from . import lowpass, highpass, downsample, upsample, quantization, spectral_subtraction, adaptive_filter, mel_inversion

MEMBER_MODULES = [lowpass, highpass, downsample, upsample, quantization, spectral_subtraction, adaptive_filter, mel_inversion]


def apply(wav, sr):
    variants = [m.apply(wav, sr) for m in MEMBER_MODULES]
    min_len = min(len(v) for v in variants)
    stacked = np.stack([v[:min_len] for v in variants])
    return np.mean(stacked, axis=0).astype(np.float32)
