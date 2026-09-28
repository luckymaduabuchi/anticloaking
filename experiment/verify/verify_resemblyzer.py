"""Resemblyzer d-vector speaker verifier (cosine similarity)."""
import functools

import numpy as np


@functools.lru_cache(maxsize=1)
def _model():
    from resemblyzer import VoiceEncoder
    return VoiceEncoder()


def embed(wav_path):
    from resemblyzer import preprocess_wav
    from pathlib import Path
    wav = preprocess_wav(Path(wav_path))
    return _model().embed_utterance(wav)


def similarity(wav_a_path, wav_b_path):
    a, b = embed(wav_a_path), embed(wav_b_path)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
