"""LowPassFiltering: attenuate high-frequency content, where adversarial
perturbations tend to concentrate, using a steep Butterworth filter."""
import numpy as np
from scipy import signal

CUTOFF_MULTIPLIER = 1.5  # relative to spectral centroid
FILTER_ORDER = 10


def apply(wav, sr):
    magnitude = np.abs(np.fft.rfft(wav))
    freqs = np.fft.rfftfreq(len(wav), d=1.0 / sr)
    centroid = float(np.sum(freqs * magnitude) / (np.sum(magnitude) + 1e-9))
    cutoff = min(centroid * CUTOFF_MULTIPLIER, sr / 2 * 0.98)

    sos = signal.butter(FILTER_ORDER, cutoff, btype="low", fs=sr, output="sos")
    return signal.sosfiltfilt(sos, wav).astype(np.float32)
