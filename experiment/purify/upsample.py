"""Upsampling: interpolate to a higher rate then decimate back down,
the mirror image of Downsampling -- a different resampling filter
footprint that can smear or attenuate perturbations differently."""
import librosa

INTERMEDIATE_SR = 48000


def apply(wav, sr):
    up = librosa.resample(wav, orig_sr=sr, target_sr=INTERMEDIATE_SR)
    back = librosa.resample(up, orig_sr=INTERMEDIATE_SR, target_sr=sr)
    return back
