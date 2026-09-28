"""AdaptiveFiltering: per-frequency-bin adaptive attenuation. Adversarial
perturbations tend to show up as narrowband energy that's anomalously
high relative to the bin's own smoothed baseline over time, unlike a
generic noise floor (that's SpectralSubtraction, below). Bins that
spike above their local baseline get pulled back down.
"""
import numpy as np
import librosa

N_FFT = 1024
HOP = 256
BASELINE_WINDOW = 21  # frames, odd
SPIKE_RATIO = 1.8      # bins above baseline*this ratio get attenuated
ATTENUATION = 0.35     # fraction of the excess energy removed


def _median_baseline(magnitude):
    from scipy.ndimage import median_filter
    return median_filter(magnitude, size=(1, BASELINE_WINDOW), mode="nearest")


def apply(wav, sr):
    stft = librosa.stft(wav, n_fft=N_FFT, hop_length=HOP)
    magnitude, phase = np.abs(stft), np.angle(stft)

    baseline = _median_baseline(magnitude) + 1e-9
    ratio = magnitude / baseline
    spike_mask = ratio > SPIKE_RATIO

    gain = np.ones_like(magnitude)
    gain[spike_mask] = 1.0 - ATTENUATION * np.clip((ratio[spike_mask] - SPIKE_RATIO) / SPIKE_RATIO, 0, 1)

    filtered_stft = (magnitude * gain) * np.exp(1j * phase)
    return librosa.istft(filtered_stft, hop_length=HOP, length=len(wav)).astype(np.float32)
