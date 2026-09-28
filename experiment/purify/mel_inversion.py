"""MelSpectrogram (inversion): project to a mel spectrogram -- a lossy,
perceptually-scaled representation adversarial perturbations aren't
optimized against -- then reconstruct phase with Griffin-Lim. Anything
that doesn't survive the mel projection is gone for good.
"""
import numpy as np
import librosa

# Works around a numba/librosa incompatibility in this environment:
# librosa.util.phasor's numba-jitted path raises
# "ufunc '_phasor_angles' did not contain a loop with signature
# matching types <class 'numpy.dtype[float64]'>" on the float64 angles
# griffinlim (used internally by mel_to_audio below) generates. The
# librosa docstring for phasor guarantees np.exp(1j * angles) is
# "numerically identical" to its own (broken) fast path, so this
# substitution changes nothing about the reconstruction algorithm --
# it only avoids the broken accelerated implementation.
librosa.util.phasor = lambda angles, mag=None: (
    np.exp(1j * np.asarray(angles)) * (mag if mag is not None else 1.0)
)

N_FFT = 1024
HOP = 256
N_MELS = 80
GRIFFIN_LIM_ITERS = 60


def apply(wav, sr):
    mel = librosa.feature.melspectrogram(y=wav, sr=sr, n_fft=N_FFT, hop_length=HOP, n_mels=N_MELS)
    reconstructed = librosa.feature.inverse.mel_to_audio(
        mel, sr=sr, n_fft=N_FFT, hop_length=HOP, n_iter=GRIFFIN_LIM_ITERS, length=len(wav),
    )
    return reconstructed.astype(np.float32)
