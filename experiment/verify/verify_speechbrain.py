"""SpeechBrain ECAPA-TDNN speaker verifier."""
import functools

import numpy as np


@functools.lru_cache(maxsize=1)
def _model():
    from speechbrain.inference import SpeakerRecognition
    return SpeakerRecognition.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir="pretrained_models/spkrec-ecapa-voxceleb",
    )


def embed(wav_path):
    # speechbrain's own load_audio() goes through soundfile/libsndfile directly,
    # which fails to decode a large fraction of ASVspoof2021's flac files on this
    # system ("unknown error in flac decoder") despite them being valid files --
    # ffprobe and librosa's audioread fallback both read them fine. Loading via
    # librosa here (like the other two verifiers already do) sidesteps that.
    import librosa
    import torch
    model = _model()
    wav, _ = librosa.load(wav_path, sr=16000, mono=True)
    signal = torch.from_numpy(wav).float()
    embedding = model.encode_batch(signal.unsqueeze(0))
    return embedding.squeeze(0).squeeze(0).cpu().numpy()


def similarity(wav_a_path, wav_b_path):
    a, b = embed(wav_a_path), embed(wav_b_path)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
