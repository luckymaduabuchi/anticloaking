"""Shared audio I/O helpers for the purification techniques.

Every technique module exposes a single function `apply(wav, sr) ->
wav` operating on a float32 mono numpy array, so purify/run_all.py can
dispatch to them uniformly.
"""
import numpy as np
import soundfile as sf


def load_wav(path, target_sr):
    import librosa
    wav, sr = librosa.load(path, sr=target_sr, mono=True)
    return wav.astype(np.float32)


def save_wav(path, wav, sr):
    wav = np.clip(wav, -1.0, 1.0).astype(np.float32)
    sf.write(path, wav, sr)


def normalize_peak(wav, peak=0.95):
    max_abs = np.max(np.abs(wav)) + 1e-9
    return wav / max_abs * peak
