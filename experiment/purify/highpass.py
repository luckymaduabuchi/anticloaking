"""HighPassFiltering: remove low-frequency content, testing whether the
protective perturbation instead concentrates below the speech band."""
import numpy as np
from scipy import signal

CUTOFF_HZ = 80.0
FILTER_ORDER = 10


def apply(wav, sr):
    sos = signal.butter(FILTER_ORDER, CUTOFF_HZ, btype="high", fs=sr, output="sos")
    return signal.sosfiltfilt(sos, wav).astype(np.float32)
