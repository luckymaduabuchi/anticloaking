"""QuantizationFiltering: reduce bit depth to coarsen the amplitude
resolution the perturbation relies on, then dequantize back to float."""
import numpy as np

BIT_DEPTH = 8


def apply(wav, sr):
    levels = 2 ** BIT_DEPTH
    quantized = np.round((wav + 1.0) / 2.0 * (levels - 1))
    quantized = np.clip(quantized, 0, levels - 1)
    return (quantized / (levels - 1) * 2.0 - 1.0).astype(np.float32)
