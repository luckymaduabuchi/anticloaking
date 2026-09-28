"""WavLM x-vector speaker verifier (cosine similarity)."""
import functools

import numpy as np
import torch


@functools.lru_cache(maxsize=1)
def _model():
    from transformers import WavLMForXVector
    model = WavLMForXVector.from_pretrained("microsoft/wavlm-base-plus-sv")
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return model.to(device), device


def embed(wav_path):
    import librosa
    model, device = _model()
    wav, _ = librosa.load(wav_path, sr=16000, mono=True)
    wav_tensor = torch.from_numpy(wav).float().to(device).unsqueeze(0)
    with torch.no_grad():
        embedding = model(wav_tensor).embeddings
    return embedding.squeeze(0).cpu().numpy()


def similarity(wav_a_path, wav_b_path):
    a, b = embed(wav_a_path), embed(wav_b_path)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
