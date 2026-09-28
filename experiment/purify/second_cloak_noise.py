"""Second-cloak application, corrected definition: a real attacker
does not know which cloaking technique (POP, attack-vc, AntiFake) --
or even whether one at all -- produced a given recording, so they
cannot re-run a specific cloak's own attack algorithm against it. What
an attacker without that inside knowledge plausibly *can* do is a
naive, cloak-agnostic move: add their own generic noise on top of the
already-cloaked audio, on the (unfounded but simple) theory that
piling more noise on top might scramble whatever protective
perturbation is already there.

This replaces an earlier, incorrect implementation
(cloak/pop_vendored/protect_already_cloaked.py) that re-ran the
cloak's own attack a second time against its own already-cloaked
output -- that requires knowing the specific cloak used and is not
something a real restoration-side attacker could do; that script and
its output are left untouched, not deleted, but this module is the one
actually reported as "second-cloak application" going forward.

Single-pass additive white Gaussian noise (no averaging -- averaging
several noisy copies is the separate ensemble_averaging_perturbed.py
technique), calibrated to a fixed signal-to-noise ratio rather than an
arbitrary amplitude, since SNR is the standard, interpretable way to
specify "how much generic noise" in the speech-processing literature.
No paper specifies an exact level for this attacker action; we default
to 30 dB SNR, a conventional "mild but real" degradation level (e.g.
the ITU-T P.800-family literature commonly treats human-perceptible
but non-disruptive noise as sitting in the 20-40 dB SNR range), applied
once, no averaging.
"""
import hashlib

import numpy as np

SNR_DB_DEFAULT = 30.0
SEED_DEFAULT = 17


def apply(wav, sr, snr_db=SNR_DB_DEFAULT, seed=SEED_DEFAULT):
    # Python's built-in hash() is randomized per-process (PYTHONHASHSEED),
    # which would silently change every clip's noise draw across separate
    # runs of the resumable driver script; hashlib is stable across runs,
    # so a resumed/rerun job reproduces byte-identical noise per clip.
    digest = hashlib.sha256(wav.tobytes()).digest()
    per_clip_seed = (seed + int.from_bytes(digest[:4], "big")) % (2 ** 32)
    rng = np.random.RandomState(per_clip_seed)
    rms = float(np.sqrt(np.mean(wav ** 2)) + 1e-9)
    noise_rms = rms / (10.0 ** (snr_db / 20.0))
    noise = rng.normal(0.0, noise_rms, size=wav.shape)
    return (wav + noise).astype(np.float32)
