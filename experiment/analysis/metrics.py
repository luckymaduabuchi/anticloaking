"""Supplementary speaker-verification metrics beyond EER/TAR@FAR:
minDCF, score-distribution separation (d-prime, overlap coefficient),
full and partial ROC-AUC, and bootstrap confidence intervals (both for
single-number metrics and for whole ROC curves, for confidence bands).

All functions take raw (labels, scores) arrays -- label=1 genuine,
label=0 impostor -- matching the score,label CSV convention used
throughout this project.

Also: STOI/PESQ/SI-SDR audio-quality metrics (see the bottom of this
file) -- a different family entirely. Those three take a (reference,
degraded) *waveform* pair of the same content/duration, not
(labels, scores); they only make sense where content is preserved
across the comparison (victim vs. cloaked, cloaked vs. restored), not
for TTS-cloned speech (different text). See
analysis/audio_quality.py, the only caller.
"""
import numpy as np
from sklearn.metrics import roc_curve, roc_auc_score

# -----------------------------------------------------------------------
# minDCF cost parameters. Explicitly stated per standard practice:
#   P_target : prior probability a random trial is genuine (not empirical
#              class balance in our CSVs -- a deployment assumption about
#              how often a real verification attempt is genuine).
#   C_miss   : cost of a false reject (real speaker turned away).
#   C_fa     : cost of a false accept (impostor let through).
# C_fa > C_miss reflects an identity-security setting: an attacker
# successfully impersonating someone is worse than a legitimate user
# needing to retry.
# -----------------------------------------------------------------------
MINDCF_P_TARGET = 0.05
MINDCF_C_MISS = 1.0
MINDCF_C_FA = 10.0


def min_dcf(labels, scores, p_target=MINDCF_P_TARGET, c_miss=MINDCF_C_MISS, c_fa=MINDCF_C_FA):
    """Normalized minimum detection cost function.

    C_det(tau) = C_miss * P_target * P_miss(tau) + C_fa * (1 - P_target) * P_fa(tau)
    minDCF = min_tau C_det(tau), normalized by dividing by the cost of
    the better of the two trivial systems (always-accept / always-reject),
    so a minDCF of 1.0 is "no better than the trivial baseline" and 0.0
    is perfect.
    """
    labels = np.asarray(labels)
    scores = np.asarray(scores)
    far, tar, _ = roc_curve(labels, scores)
    fnr = 1 - tar  # P_miss

    c_det = c_miss * p_target * fnr + c_fa * (1 - p_target) * far
    raw_min_dcf = float(np.min(c_det))

    c_default = min(c_miss * p_target, c_fa * (1 - p_target))
    return raw_min_dcf / c_default


def d_prime(labels, scores):
    """Separation between genuine and impostor score distributions:
    d' = (mu_target - mu_impostor) / sqrt(0.5 * (var_target + var_impostor))
    Larger = better separated = more identity leakage if this is scoring
    an attack's synthesized output.
    """
    labels = np.asarray(labels)
    scores = np.asarray(scores)
    target = scores[labels == 1]
    impostor = scores[labels == 0]
    pooled_std = np.sqrt(0.5 * (target.var() + impostor.var()))
    if pooled_std == 0:
        return float("nan")
    return float((target.mean() - impostor.mean()) / pooled_std)


def overlap_coefficient(labels, scores, bins=200):
    """Fraction of the two score distributions' area that overlaps
    (0 = perfectly separated, 1 = identical distributions), computed
    from shared-bin histograms over the pooled score range.
    """
    labels = np.asarray(labels)
    scores = np.asarray(scores)
    target = scores[labels == 1]
    impostor = scores[labels == 0]

    lo, hi = scores.min(), scores.max()
    if lo == hi:
        return 1.0
    edges = np.linspace(lo, hi, bins + 1)

    target_hist, _ = np.histogram(target, bins=edges, density=True)
    impostor_hist, _ = np.histogram(impostor, bins=edges, density=True)
    bin_width = edges[1] - edges[0]

    return float(np.sum(np.minimum(target_hist, impostor_hist)) * bin_width)


def full_roc_auc(labels, scores):
    """Full ROC-AUC = P(target score > impostor score) for a random
    target/impostor pair. Supplementary only -- weights the high-FAR
    region heavily, where a system can look excellent overall while
    still being weak in the security-relevant FAR<1% region. Don't use
    this alone as evidence of strong (or weak) identity leakage --
    that's what pAUC/TAR@FAR are for.
    """
    return float(roc_auc_score(labels, scores))


def partial_auc(labels, scores, far_max=0.01):
    """Normalized partial AUC over FAR in [0, far_max]: the area under
    the ROC curve restricted to that FAR range, divided by far_max, so
    the result is on a [0, 1] scale where 0.5 = chance (matches a
    diagonal ROC in that region) and 1.0 = perfect separation.
    """
    labels = np.asarray(labels)
    scores = np.asarray(scores)
    far, tar, _ = roc_curve(labels, scores)

    # restrict to FAR <= far_max, adding the exact boundary point via interpolation
    mask = far <= far_max
    far_restricted = far[mask]
    tar_restricted = tar[mask]
    if far_restricted.size == 0 or far_restricted[-1] < far_max:
        boundary_tar = np.interp(far_max, far, tar)
        far_restricted = np.append(far_restricted, far_max)
        tar_restricted = np.append(tar_restricted, boundary_tar)

    area = float(np.trapz(tar_restricted, far_restricted))
    return area / far_max


def bootstrap_ci(labels, scores, metric_fn, n_boot=1000, ci=0.95, seed=0):
    """95% (by default) bootstrap confidence interval for a metric
    function (e.g. compute_eer, min_dcf), resampling genuine and
    impostor trials separately (preserving each class's sample size,
    the standard approach for verification-trial bootstrapping) with
    replacement.
    """
    labels = np.asarray(labels)
    scores = np.asarray(scores)
    target_idx = np.where(labels == 1)[0]
    impostor_idx = np.where(labels == 0)[0]

    rng = np.random.default_rng(seed)
    values = []
    for _ in range(n_boot):
        t_sample = rng.choice(target_idx, size=len(target_idx), replace=True)
        i_sample = rng.choice(impostor_idx, size=len(impostor_idx), replace=True)
        idx = np.concatenate([t_sample, i_sample])
        try:
            values.append(metric_fn(labels[idx], scores[idx]))
        except ValueError:
            continue  # degenerate resample (e.g. all-one-class edge case)

    alpha = (1 - ci) / 2
    lo, hi = np.percentile(values, [100 * alpha, 100 * (1 - alpha)])
    return float(lo), float(hi)


def bootstrap_roc_band(labels, scores, far_grid, n_boot=200, ci=0.95, seed=0):
    """Bootstrap confidence band for a whole ROC curve: for each
    resample, interpolate TAR onto a common FAR grid (each resample's
    own roc_curve has different breakpoints, so a fixed grid is needed
    to compare across resamples), then take percentiles at each grid
    point. Returns (median_tar, lower_tar, upper_tar), each an array
    the same length as far_grid.
    """
    labels = np.asarray(labels)
    scores = np.asarray(scores)
    target_idx = np.where(labels == 1)[0]
    impostor_idx = np.where(labels == 0)[0]

    rng = np.random.default_rng(seed)
    tar_samples = np.empty((n_boot, len(far_grid)))
    for b in range(n_boot):
        t_sample = rng.choice(target_idx, size=len(target_idx), replace=True)
        i_sample = rng.choice(impostor_idx, size=len(impostor_idx), replace=True)
        idx = np.concatenate([t_sample, i_sample])
        far, tar, _ = roc_curve(labels[idx], scores[idx])
        order = np.argsort(far)
        tar_samples[b] = np.interp(far_grid, far[order], tar[order])

    alpha = (1 - ci) / 2
    lo = np.percentile(tar_samples, 100 * alpha, axis=0)
    hi = np.percentile(tar_samples, 100 * (1 - alpha), axis=0)
    median = np.percentile(tar_samples, 50, axis=0)
    return median, lo, hi


# -----------------------------------------------------------------------
# Audio-quality metrics: reference vs. degraded *waveform* pairs of the
# same content (e.g. victim vs. cloaked, or cloaked vs. restored) --
# not applicable to TTS-cloned speech, which has different content.
# All three trim to the shorter of the two signals rather than erroring
# on a length mismatch, since restoration techniques like
# Downsampling/Upsampling can shift sample count by a handful of samples.
# -----------------------------------------------------------------------
# How quality-metric inputs are aligned. "delay" (default) estimates and
# removes the time offset between the two signals first; "truncate" is the
# old behavior (just cut both to the shorter length, no delay estimation),
# kept so the effect of alignment can be measured directly.
ALIGN_MODE = "delay"
MAX_LAG_SAMPLES = 16000       # +-1 s at 16 kHz, the rate quality is scored at
MIN_PEAK_CORRELATION = 0.05   # below this the correlation peak is not trusted
MIN_GAIN_OVER_LAG0 = 1.5      # a shift must beat lag 0 by this factor in |correlation|


def _align_truncate(reference, degraded):
    reference = np.asarray(reference, dtype=np.float64)
    degraded = np.asarray(degraded, dtype=np.float64)
    n = min(len(reference), len(degraded))
    return reference[:n], degraded[:n]


def estimate_delay_ex(reference, degraded, max_lag=MAX_LAG_SAMPLES):
    """Delay (in samples, fractional) of `degraded` relative to
    `reference`: positive = degraded lags. FFT cross-correlation, integer
    peak refined by parabolic interpolation. Returns dict(delay, peak,
    gain_over_lag0, at_edge): peak is the normalized correlation at the
    chosen lag (0..1), gain_over_lag0 how much larger |correlation| is
    there than at lag 0, at_edge whether the peak sits at the search
    window's boundary (the window may then be too small)."""
    reference = np.asarray(reference, dtype=np.float64)
    degraded = np.asarray(degraded, dtype=np.float64)
    nfft = 1 << int(np.ceil(np.log2(len(reference) + len(degraded))))
    cc = np.fft.irfft(np.conj(np.fft.rfft(reference, nfft)) * np.fft.rfft(degraded, nfft), nfft)
    lags = np.arange(-max_lag, max_lag + 1)
    vals = np.abs(cc[lags % nfft])
    k = int(np.argmax(vals))
    frac = 0.0
    if 0 < k < len(vals) - 1:
        y0, y1, y2 = vals[k - 1], vals[k], vals[k + 1]
        denom = y0 - 2 * y1 + y2
        if denom != 0:
            frac = float(np.clip(0.5 * (y0 - y2) / denom, -0.5, 0.5))
    norm = np.linalg.norm(reference) * np.linalg.norm(degraded) + 1e-12
    return {"delay": float(lags[k] + frac), "peak": float(vals[k] / norm),
            "gain_over_lag0": float(vals[k] / (abs(cc[0]) + 1e-12)),
            "at_edge": bool(k <= 2 or k >= len(vals) - 3)}


def estimate_delay(reference, degraded, max_lag=MAX_LAG_SAMPLES):
    """(delay, peak) -- see estimate_delay_ex."""
    e = estimate_delay_ex(reference, degraded, max_lag)
    return e["delay"], e["peak"]


def _advance(signal, delay):
    """Shift `signal` earlier by `delay` samples (fractional, via a linear
    phase in the frequency domain), zero-padded so nothing wraps around."""
    pad = int(np.ceil(abs(delay))) + 16
    x = np.concatenate([np.zeros(pad), signal, np.zeros(pad)])
    freqs = np.fft.rfftfreq(len(x))
    y = np.fft.irfft(np.fft.rfft(x) * np.exp(2j * np.pi * freqs * delay), len(x))
    return y[pad:pad + len(signal)]


LOCAL_SEGMENT = 8000        # 0.5 s pieces used to test whether a lag is constant
LOCAL_MAX_LAG = 200         # +-12.5 ms search per piece (also: offsets above this are never artifacts)
LOCAL_MIN_PEAK = 0.10       # a piece with weaker correlation keeps the previous lag
LOCAL_TRIGGER = 4.0         # local lags above this many samples (0.25 ms) mean "not constant"


def _local_lag_spread(reference, degraded):
    """Largest |lag| (samples) of any 0.5 s piece of `degraded` relative to
    `reference`, searching +-LOCAL_MAX_LAG. Pieces with too little
    correlation inherit the previous lag. 0.0 if the clip is shorter than
    two pieces (nothing to test)."""
    n = min(len(reference), len(degraded))
    if n < 2 * LOCAL_SEGMENT:
        return 0.0
    worst, prev = 0.0, 0.0
    for a in range(0, n - LOCAL_SEGMENT + 1, LOCAL_SEGMENT):
        e = estimate_delay_ex(reference[a:a + LOCAL_SEGMENT], degraded[a:a + LOCAL_SEGMENT], LOCAL_MAX_LAG)
        prev = e["delay"] if e["peak"] >= LOCAL_MIN_PEAK else prev
        worst = max(worst, abs(prev))
    return worst


ENVELOPE_FRAME = 320        # 20 ms frames for the loudness-envelope agreement check
ENVELOPE_MARGIN = 0.02      # a shift must raise envelope correlation by at least this much


def _envelope_corr(reference, degraded):
    """Correlation of the two signals' short-time loudness envelopes (20 ms
    RMS frames) -- the thing STOI is sensitive to, and tolerant of jitter."""
    n = (min(len(reference), len(degraded)) // ENVELOPE_FRAME) * ENVELOPE_FRAME
    if n < 4 * ENVELOPE_FRAME:
        return 0.0
    er = np.sqrt((reference[:n].reshape(-1, ENVELOPE_FRAME) ** 2).mean(axis=1))
    ed = np.sqrt((degraded[:n].reshape(-1, ENVELOPE_FRAME) ** 2).mean(axis=1))
    if er.std() < 1e-9 or ed.std() < 1e-9:
        return 0.0
    return float(np.corrcoef(er, ed)[0, 1])


def align_signals(reference, degraded, max_lag=MAX_LAG_SAMPLES):
    """Remove a constant time offset between the signals, and say whether
    the rest of the misalignment is time-varying.

    1. Estimate the global delay (FFT cross-correlation). It is applied
       only if the correlation is trustworthy AND either the remaining
       local lags (per 0.5 s piece) are then all tiny (a genuinely
       constant offset), or -- when local lags still wander -- the shift
       demonstrably makes the loudness envelopes agree better.
    2. If, after that, local lags still wander, the misalignment is
       time-varying: a single shift cannot fix it (and chasing a
       waveform-correlation peak can make envelope-based metrics worse).
       No shift is applied in that case and info["time_varying"] is True;
       si_sdr() then returns NaN, because a waveform-level comparison is
       not meaningful when timing jitters. STOI/PESQ, which tolerate
       millisecond-scale offsets, are still computed.

    Returns (ref, deg, info); info = dict(delay, peak, applied, at_edge,
    time_varying, local_lag_max).
    """
    reference = np.asarray(reference, dtype=np.float64)
    degraded = np.asarray(degraded, dtype=np.float64)
    est = estimate_delay_ex(reference, degraded, max_lag)
    delay, peak = est["delay"], est["peak"]
    reliable = (peak >= MIN_PEAK_CORRELATION and abs(delay) > 1e-3
                and est["gain_over_lag0"] >= MIN_GAIN_OVER_LAG0)

    r0, d0 = _align_truncate(reference, degraded)
    applied, time_varying = False, False
    chosen, spread = (r0, d0), 0.0
    if reliable:
        shifted = _advance(degraded, delay)
        trim = int(np.ceil(abs(delay))) + 1
        n = min(len(reference), len(shifted))
        r1, d1 = reference[trim:n - trim], shifted[trim:n - trim]
        if len(r1) >= 1600:
            spread = _local_lag_spread(r1, d1)
            if spread <= LOCAL_TRIGGER:
                chosen, applied = (r1, d1), True
            else:
                # Lags still wander after the shift: time-varying. Keep the
                # shift only if it really makes the loudness envelopes
                # agree better (a genuine large offset does; a spurious
                # waveform-correlation peak on already-aligned audio does not).
                time_varying = True
                if _envelope_corr(r1, d1) > _envelope_corr(r0, d0) + ENVELOPE_MARGIN:
                    chosen, applied = (r1, d1), True
                else:
                    spread = _local_lag_spread(r0, d0)
    else:
        spread = _local_lag_spread(r0, d0)
        time_varying = spread > LOCAL_TRIGGER
    return chosen[0], chosen[1], {"delay": delay, "peak": peak, "applied": applied,
                                  "at_edge": est["at_edge"], "time_varying": time_varying,
                                  "local_lag_max": float(spread)}


def _align(reference, degraded):
    if ALIGN_MODE == "truncate":
        return _align_truncate(reference, degraded)
    ref, deg, _ = align_signals(reference, degraded)
    return ref, deg


def stoi_score(reference, degraded, sample_rate, extended=False):
    """Short-Time Objective Intelligibility, in [0, 1] (higher = more
    intelligible). Wraps the `pystoi` package.
    """
    from pystoi import stoi
    reference, degraded = _align(reference, degraded)
    return float(stoi(reference, degraded, sample_rate, extended=extended))


def pesq_score(reference, degraded, sample_rate):
    """Perceptual Evaluation of Speech Quality (ITU-T P.862), roughly in
    [-0.5, 4.5] (higher = better perceived quality). Wraps the `pesq`
    package; wideband mode ('wb') requires 16kHz, narrowband ('nb') 8kHz
    -- this project's SAMPLE_RATE is 16kHz throughout, so 'wb' is used
    unless sample_rate is 8000.
    """
    from pesq import pesq
    reference, degraded = _align(reference, degraded)
    mode = "wb" if sample_rate == 16000 else "nb"
    return float(pesq(sample_rate, reference, degraded, mode))


def si_sdr(reference, degraded):
    """Scale-Invariant Signal-to-Distortion Ratio, in dB (higher =
    less distortion). Self-implemented (no extra dependency needed,
    matching this project's plain-numpy style for the other
    score-separation metrics above): projects the degraded signal onto
    the reference, scaled to minimize residual energy, then compares
    projection energy to residual energy.
    """
    if ALIGN_MODE == "truncate":
        reference, degraded = _align_truncate(reference, degraded)
    else:
        reference, degraded, info = align_signals(reference, degraded)
        if info["time_varying"]:
            return float("nan")  # waveform-level comparison not meaningful under jittering timing
    reference = reference - reference.mean()
    degraded = degraded - degraded.mean()
    scale = np.dot(degraded, reference) / (np.dot(reference, reference) + 1e-9)
    projection = scale * reference
    residual = degraded - projection
    ratio = (np.sum(projection ** 2) + 1e-9) / (np.sum(residual ** 2) + 1e-9)
    return float(10 * np.log10(ratio))
