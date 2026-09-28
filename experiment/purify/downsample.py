"""Downsampling: reduce sample rate then upsample back, so the
resampling filter's anti-aliasing lowpass acts as an implicit purifier."""
import librosa

TARGET_SR = 8000


def apply(wav, sr):
    down = librosa.resample(wav, orig_sr=sr, target_sr=TARGET_SR)
    back = librosa.resample(down, orig_sr=TARGET_SR, target_sr=sr)
    return back
