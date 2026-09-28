"""SpectralSubtraction: classic blind spectral subtraction. A real
attacker has no access to the original clean audio, so the noise
profile is estimated from the cloaked signal's own lowest-energy
frames (its quietest 10%) rather than a ground-truth reference, then
subtracted from every frame's magnitude spectrum.
"""
import numpy as np
import librosa

N_FFT = 1024
HOP = 256
QUIET_FRAME_PERCENTILE = 10
OVER_SUBTRACTION = 1.2
SPECTRAL_FLOOR = 0.05


def apply(wav, sr):
    stft = librosa.stft(wav, n_fft=N_FFT, hop_length=HOP)
    magnitude, phase = np.abs(stft), np.angle(stft)

    frame_energy = np.sum(magnitude ** 2, axis=0)
    threshold = np.percentile(frame_energy, QUIET_FRAME_PERCENTILE)
    quiet_frames = magnitude[:, frame_energy <= threshold]
    noise_profile = np.mean(quiet_frames, axis=1, keepdims=True) if quiet_frames.size else np.zeros((magnitude.shape[0], 1))

    subtracted = magnitude - OVER_SUBTRACTION * noise_profile
    floor = SPECTRAL_FLOOR * magnitude
    cleaned_magnitude = np.maximum(subtracted, floor)

    cleaned_stft = cleaned_magnitude * np.exp(1j * phase)
    return librosa.istft(cleaned_stft, hop_length=HOP, length=len(wav)).astype(np.float32)
