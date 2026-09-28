"""Adaptive frequency filtering (centroid-based), matching the paper's
own description: a single spectral centroid C is computed for the
whole signal, and a high-pass cutoff f_HP = alpha*C and low-pass cutoff
f_LP = beta*C are derived from it, under the hypothesis that cloaking
redistributes energy across frequency bands and that partially
restoring the spectral balance around the centroid may recover
identity cues. Most relevant when cloaking behaves like spectral
shaping; less effective against non-linear or phase-sensitive
distortions, and sensitive to the choice of alpha/beta.

Separate from purify/adaptive_filter.py (an unrelated per-bin temporal-
baseline narrowband-spike suppressor already in this project, despite
the similar name) -- this module does not replace it, since we still
need that one too.

The paper does not specify alpha/beta values; we default to alpha=0.5,
beta=1.5 (so the passband straddles the centroid, from half of it up
to 1.5x it), reusing the same 1.5 multiplier already established in
purify/lowpass.py/lowpass_gain.py for consistency across techniques in
this codebase. These are defaults, not values taken from the paper --
adjust if given different ones.
"""
import numpy as np
from scipy import signal

ALPHA_DEFAULT = 0.5   # f_HP = alpha * centroid
BETA_DEFAULT = 1.5    # f_LP = beta * centroid
FILTER_ORDER = 10


def _spectral_centroid(wav, sr):
    magnitude = np.abs(np.fft.rfft(wav))
    freqs = np.fft.rfftfreq(len(wav), d=1.0 / sr)
    return float(np.sum(freqs * magnitude) / (np.sum(magnitude) + 1e-9))


def apply(wav, sr, alpha=ALPHA_DEFAULT, beta=BETA_DEFAULT, filter_type="butterworth"):
    centroid = _spectral_centroid(wav, sr)
    nyquist_cap = sr / 2 * 0.98
    f_hp = max(min(alpha * centroid, nyquist_cap - 1), 1.0)
    f_lp = max(min(beta * centroid, nyquist_cap), f_hp + 1.0)

    if filter_type == "butterworth":
        sos = signal.butter(FILTER_ORDER, [f_hp, f_lp], btype="bandpass", fs=sr, output="sos")
    elif filter_type == "chebyshev":
        sos = signal.cheby1(FILTER_ORDER, 1, [f_hp, f_lp], btype="bandpass", fs=sr, output="sos")
    elif filter_type == "bessel":
        sos = signal.bessel(FILTER_ORDER, [f_hp, f_lp], btype="bandpass", fs=sr, output="sos", norm="phase")
    else:
        raise ValueError(f"unknown filter_type: {filter_type}")

    return signal.sosfiltfilt(sos, wav).astype(np.float32)
