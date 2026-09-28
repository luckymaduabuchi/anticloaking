"""Low-pass filtering with gain multiplier search, matching the paper's
own description: y_LP(t) = x(t) * h_LP(t), y_mult(t) = M * y_LP(t),
where M is swept over a range (e.g. 1.2 to 2.0) and Butterworth,
Chebyshev, and Bessel filter designs are compared (Butterworth reported
as the main configuration). This targets cloaks that leave residual
identity cues in the low-frequency band, testing whether amplifying
that region increases recoverability -- over-amplification can
introduce low-frequency noise and reduce perceptual quality.

Separate from purify/lowpass.py (a plain fixed-gain low-pass filter,
already in use elsewhere in this project) -- this module adds the gain
sweep and multi-filter-design comparison that plain module doesn't
implement; it does not replace it.

Reuses the same adaptive spectral-centroid cutoff heuristic as
purify/lowpass.py for the cutoff itself (the paper excerpt available to
us doesn't specify a cutoff-selection rule), so a gain of 1.0 under the
"butterworth" design here reproduces purify/lowpass.py's output
exactly.
"""
import numpy as np
from scipy import signal

CUTOFF_MULTIPLIER = 1.5  # relative to spectral centroid, matches purify/lowpass.py
FILTER_ORDER = 10

FILTER_DESIGNS = ("butterworth", "chebyshev", "bessel")
GAIN_VALUES = (1.2, 1.4, 1.6, 1.8, 2.0)  # 5-point sweep over the paper's 1.2-2.0 range


def _cutoff_for(wav, sr):
    magnitude = np.abs(np.fft.rfft(wav))
    freqs = np.fft.rfftfreq(len(wav), d=1.0 / sr)
    centroid = float(np.sum(freqs * magnitude) / (np.sum(magnitude) + 1e-9))
    return min(centroid * CUTOFF_MULTIPLIER, sr / 2 * 0.98)


def _design_sos(filter_type, cutoff, sr, order=FILTER_ORDER):
    if filter_type == "butterworth":
        return signal.butter(order, cutoff, btype="low", fs=sr, output="sos")
    if filter_type == "chebyshev":
        # 1 dB passband ripple -- a typical default, not specified in the
        # paper excerpt available to us.
        return signal.cheby1(order, 1, cutoff, btype="low", fs=sr, output="sos")
    if filter_type == "bessel":
        return signal.bessel(order, cutoff, btype="low", fs=sr, output="sos", norm="phase")
    raise ValueError(f"unknown filter_type: {filter_type}")


def apply(wav, sr, gain=1.0, filter_type="butterworth"):
    """Low-pass filter wav, then multiply the filtered signal by gain.
    gain=1.0 is the plain filtered output (no amplification)."""
    cutoff = _cutoff_for(wav, sr)
    sos = _design_sos(filter_type, cutoff, sr)
    filtered = signal.sosfiltfilt(sos, wav)
    return (gain * filtered).astype(np.float32)
