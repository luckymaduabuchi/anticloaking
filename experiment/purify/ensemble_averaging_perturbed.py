"""Ensemble averaging of perturbed variants, matching the paper's own
description: generate N lightly modified variants of the *same* signal
(small time shifts, low-amplitude additive noise) and average them:
Y_avg(t) = (1/N) * sum(Y_i(t)). Targets cloaks whose perturbations
behave stochastically or are unstable under small input changes -- a
deterministic, input-stable cloak gets limited benefit from this.

Separate from purify/ensemble_averaging.py (already in this project,
despite the similar name) -- that module averages the outputs of
several *different restoration techniques* run on the same input, not
several perturbed *copies* of the same input; this module does not
replace it.

The paper gives examples of perturbation types (time shifts, additive
noise) but not N or their magnitudes; we default to N=5 variants, each
with an independent small random time shift (up to +-0.1ms, i.e. a
single sample at 16kHz) and low-amplitude Gaussian noise (std = 0.5%
of the signal's own RMS) -- defaults, not values taken from the paper.
The shift magnitude was picked empirically: shifts of a millisecond or
more cause enough phase rotation across speech's frequency content
that averaging destructively cancels most of the signal (verified
directly -- a 2ms shift range dropped RMS by ~60%), which would make
this behave like an aggressive implicit filter rather than the
"light" perturbation the paper describes; 0.1ms keeps the RMS change
to ~7%. Fixed seed for reproducibility, matching the fixed-seed
convention already used elsewhere in this project (e.g. attack-vc's
decoy selection).
"""
import numpy as np

N_VARIANTS_DEFAULT = 5
MAX_SHIFT_MS_DEFAULT = 0.1
NOISE_STD_FRACTION_DEFAULT = 0.005
SEED_DEFAULT = 13


def apply(wav, sr, n_variants=N_VARIANTS_DEFAULT, max_shift_ms=MAX_SHIFT_MS_DEFAULT,
          noise_std_fraction=NOISE_STD_FRACTION_DEFAULT, seed=SEED_DEFAULT):
    rng = np.random.RandomState(seed)
    max_shift_samples = max(1, int(max_shift_ms / 1000.0 * sr))
    rms = float(np.sqrt(np.mean(wav ** 2)) + 1e-9)

    variants = []
    for _ in range(n_variants):
        shift = int(rng.randint(-max_shift_samples, max_shift_samples + 1))
        variant = np.roll(wav, shift)
        noise = rng.normal(0.0, rms * noise_std_fraction, size=variant.shape)
        variants.append(variant + noise)

    return np.mean(np.stack(variants), axis=0).astype(np.float32)
