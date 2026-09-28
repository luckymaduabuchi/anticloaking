"""SimulatedReRecord: emulate playing the cloaked audio through a
speaker and recapturing it with a microphone -- convolution with a
synthetic room impulse response, band-limited mic/speaker frequency
coloring, and a touch of ambient noise. Physical re-recording is a
classic way real-world attackers try to wash out digital adversarial
perturbations.
"""
import numpy as np
from scipy import signal

RT60_SECONDS = 0.25       # reverberation decay time
NOISE_FLOOR_DB = -35
MIC_BANDPASS = (120.0, 7000.0)


def _synthetic_rir(sr, rt60):
    length = int(sr * rt60)
    t = np.arange(length) / sr
    decay = np.exp(-6.9 * t / rt60)  # -60dB at t=rt60
    rng = np.random.default_rng(0)
    noise = rng.standard_normal(length)
    rir = noise * decay
    rir[0] = 1.0  # direct path dominates
    return (rir / np.max(np.abs(rir))).astype(np.float32)


def apply(wav, sr):
    rir = _synthetic_rir(sr, RT60_SECONDS)
    reverberant = signal.fftconvolve(wav, rir, mode="full")[: len(wav)]

    sos = signal.butter(4, MIC_BANDPASS, btype="bandpass", fs=sr, output="sos")
    colored = signal.sosfiltfilt(sos, reverberant)

    noise_amp = 10 ** (NOISE_FLOOR_DB / 20)
    rng = np.random.default_rng(1)
    noisy = colored + noise_amp * rng.standard_normal(len(colored))

    peak = np.max(np.abs(noisy)) + 1e-9
    return (noisy / peak * np.max(np.abs(wav))).astype(np.float32)
