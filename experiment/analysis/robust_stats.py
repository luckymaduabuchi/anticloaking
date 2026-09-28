#!/usr/bin/env python3
"""Statistics that respect how the trials are actually generated.

Replaces two weaknesses of the original metrics:

1. TAR at a low FAR was linearly *interpolated* between ROC vertices
   (results_table.tar_at_far). At FAR = 0.01% with ~48,500 impostor
   trials that is ~5 false accepts (1.5 with 15,000), so the value is not
   a measured operating point. `attainable_tar_at_far` instead picks an
   actual threshold whose empirical FAR is <= the target and reports the
   TAR there, together with the number of false accepts it rests on;
   `is_resolvable` says whether a target FAR is backed by enough false
   accepts to carry a claim at all.

2. bootstrap_ci resampled individual genuine/impostor *scores*
   independently. Really, each clip (stem) contributes one genuine trial
   and ~10 impostor trials that share the same query, and clips from the
   same speaker recur, so trials are not independent and those intervals
   are too narrow. `cluster_bootstrap` resamples whole clusters (default:
   stem; or speaker) and keeps every trial of a chosen cluster.
   `paired_cluster_bootstrap_diff` does the same for a difference between
   two conditions scored on the same clips: the same resampled clusters
   are applied to both conditions (complete cases only), giving a CI for
   the difference itself instead of comparing two independent CIs.

Score CSVs need the stem column (see clean_bonafide_vs_synth.CSV_COLUMNS);
for older files without it, `backfill_stems` can recover it from the
deterministic row order when (and only when) it validates.
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import beta
from sklearn.metrics import roc_curve

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis.results_table import compute_eer

MIN_FALSE_ACCEPTS = 10  # below this many FAs a low-FAR TAR is not reportable


# ---------------------------------------------------------------------------
# Attainable (non-interpolated) TAR at a target FAR
# ---------------------------------------------------------------------------
def attainable_tar_at_far(labels, scores, target_far):
    """TAR at the most permissive real threshold with empirical FAR <=
    target_far (accept = score strictly greater than the threshold).
    Returns dict(tar, n_fa, far, threshold, n_imp, n_gen).
    """
    labels = np.asarray(labels)
    scores = np.asarray(scores, dtype=float)
    imp = np.sort(scores[labels == 0])[::-1]  # descending
    gen = scores[labels == 1]
    n_imp = len(imp)
    allowed = int(np.floor(target_far * n_imp + 1e-9))
    thr = -np.inf if allowed >= n_imp else float(imp[allowed])
    n_fa = int((imp > thr).sum())
    return {
        "tar": float((gen > thr).mean()) if len(gen) else float("nan"),
        "n_fa": n_fa,
        "far": n_fa / n_imp if n_imp else float("nan"),
        "threshold": thr,
        "n_imp": n_imp,
        "n_gen": len(gen),
    }


def is_resolvable(target_far, n_imp, min_fa=MIN_FALSE_ACCEPTS):
    """True if the target FAR corresponds to at least `min_fa` expected
    false accepts, i.e. the operating point is measured, not extrapolated."""
    return target_far * n_imp >= min_fa


def binomial_ci(k, n, ci=0.95):
    """Clopper-Pearson interval for a proportion k/n."""
    a = (1 - ci) / 2
    lo = 0.0 if k == 0 else beta.ppf(a, k, n - k + 1)
    hi = 1.0 if k == n else beta.ppf(1 - a, k + 1, n - k)
    return float(lo), float(hi)


# ---------------------------------------------------------------------------
# Metric functions (labels, scores) -> float
# ---------------------------------------------------------------------------
def eer_metric(labels, scores):
    far, tar, _ = roc_curve(labels, scores)
    return compute_eer(far, tar)


def tar_metric(target_far):
    def fn(labels, scores):
        return attainable_tar_at_far(labels, scores, target_far)["tar"]
    return fn


DEFAULT_METRICS = {"EER": eer_metric, "TAR@1%": tar_metric(0.01)}


# ---------------------------------------------------------------------------
# Clustered trial sets
# ---------------------------------------------------------------------------
class ClusteredTrials:
    """Trials grouped by a cluster key. Resampling a cluster keeps all of
    its rows (its genuine trial and every impostor trial)."""

    def __init__(self, scores, labels, cluster_ids):
        self.scores = np.asarray(scores, dtype=float)
        self.labels = np.asarray(labels)
        cluster_ids = np.asarray(cluster_ids)
        order = np.argsort(cluster_ids, kind="stable")
        sorted_ids = cluster_ids[order]
        self.ids, starts = np.unique(sorted_ids, return_index=True)
        self.rows = np.split(order, starts[1:])  # row indices per cluster

    def __len__(self):
        return len(self.ids)

    def take(self, cluster_positions):
        idx = np.concatenate([self.rows[i] for i in cluster_positions])
        return self.labels[idx], self.scores[idx]

    def restrict(self, keep_ids):
        keep = np.isin(self.ids, keep_ids)
        pos = np.flatnonzero(keep)
        rows = np.concatenate([self.rows[i] for i in pos])
        ids = np.concatenate([[self.ids[i]] * len(self.rows[i]) for i in pos])
        return ClusteredTrials(self.scores[rows], self.labels[rows], ids)


def load_trials(csv_path, cluster_by="stem", speaker_of=None, require_genuine=True):
    """Load an ID-bearing score CSV as ClusteredTrials.

    cluster_by: "stem" (one cluster per scored clip) or "speaker" (needs
    `speaker_of`, a dict stem -> speaker_id, e.g. from the manifest).
    require_genuine: drop stems with no genuine row (a failed genuine
    trial leaves no rows at all, but impostor-only stems would otherwise
    distort complete-case comparisons).
    """
    df = pd.read_csv(csv_path)
    if "stem" not in df.columns:
        raise ValueError(f"{csv_path} has no stem column; rescore it or use backfill_stems()")
    return trials_from_df(df, cluster_by, speaker_of, require_genuine)


def trials_from_df(df, cluster_by="stem", speaker_of=None, require_genuine=True):
    """Same as load_trials but from an in-memory dataframe with a stem
    column (e.g. the output of backfill_stems)."""
    if require_genuine:
        has_gen = set(df.loc[df.label == 1, "stem"])
        df = df[df.stem.isin(has_gen)]
    if cluster_by == "stem":
        cluster = df.stem.to_numpy()
    elif cluster_by == "speaker":
        if speaker_of is None:
            raise ValueError("cluster_by='speaker' needs speaker_of")
        cluster = df.stem.map(speaker_of).to_numpy()
    else:
        raise ValueError(cluster_by)
    trials = ClusteredTrials(df.score, df.label, cluster)
    trials.stems = df.stem.to_numpy()
    return trials


# ---------------------------------------------------------------------------
# Cluster bootstrap CIs
# ---------------------------------------------------------------------------
def cluster_bootstrap(trials, metrics=None, n_boot=1000, ci=0.95, seed=0):
    """Point estimate and percentile CI for each metric, resampling whole
    clusters with replacement. Returns {name: dict(point, lo, hi)}."""
    metrics = metrics or DEFAULT_METRICS
    rng = np.random.default_rng(seed)
    n = len(trials)
    all_pos = np.arange(n)
    point = {k: fn(*trials.take(all_pos)) for k, fn in metrics.items()}
    draws = {k: [] for k in metrics}
    for _ in range(n_boot):
        labels, scores = trials.take(rng.integers(0, n, n))
        if labels.min() == labels.max():
            continue
        for k, fn in metrics.items():
            draws[k].append(fn(labels, scores))
    a = (1 - ci) / 2
    return {k: {"point": point[k],
                "lo": float(np.percentile(draws[k], 100 * a)),
                "hi": float(np.percentile(draws[k], 100 * (1 - a)))}
            for k in metrics}


def paired_cluster_bootstrap_diff(trials_a, trials_b, metrics=None, n_boot=1000, ci=0.95, seed=0):
    """CI for metric(A) - metric(B) over the clusters present in BOTH
    conditions (complete cases). The same resampled clusters are applied
    to A and B each round, so the pairing is preserved. Returns
    {name: dict(n_matched, a, b, diff, lo, hi, p)} where p is the
    two-sided bootstrap p-value for diff == 0.
    """
    metrics = metrics or DEFAULT_METRICS
    common = np.intersect1d(trials_a.ids, trials_b.ids)
    a = trials_a.restrict(common)
    b = trials_b.restrict(common)
    n = len(common)
    if n == 0:
        raise ValueError("no matched clusters between the two conditions")
    all_pos = np.arange(n)
    point_a = {k: fn(*a.take(all_pos)) for k, fn in metrics.items()}
    point_b = {k: fn(*b.take(all_pos)) for k, fn in metrics.items()}

    rng = np.random.default_rng(seed)
    diffs = {k: [] for k in metrics}
    for _ in range(n_boot):
        pick = rng.integers(0, n, n)
        la, sa = a.take(pick)
        lb, sb = b.take(pick)
        if la.min() == la.max() or lb.min() == lb.max():
            continue
        for k, fn in metrics.items():
            diffs[k].append(fn(la, sa) - fn(lb, sb))
    al = (1 - ci) / 2
    out = {}
    for k in metrics:
        d = np.asarray(diffs[k])
        p = 2 * min((d <= 0).mean(), (d >= 0).mean())
        out[k] = {"n_matched": n, "a": point_a[k], "b": point_b[k],
                  "diff": point_a[k] - point_b[k],
                  "lo": float(np.percentile(d, 100 * al)),
                  "hi": float(np.percentile(d, 100 * (1 - al))),
                  "p": float(min(1.0, p))}
    return out


def reversal_verdict(diffs_by_verifier):
    """Paired-difference version of the restoration 'reversal' criterion.
    Input: {verifier: paired_cluster_bootstrap_diff(...)['EER']} with
    A = restored, B = no-restoration baseline, so diff < 0 means EER went
    down (toward the clean ceiling). 'REVERSE' only if the whole CI of the
    difference is below zero on every verifier."""
    sig = [v for v, r in diffs_by_verifier.items() if r["hi"] < 0]
    worse = [v for v, r in diffs_by_verifier.items() if r["lo"] > 0]
    if len(sig) == len(diffs_by_verifier):
        return "REVERSE (all verifiers)"
    if sig:
        return f"partial ({len(sig)}/{len(diffs_by_verifier)})"
    if len(worse) == len(diffs_by_verifier):
        return "worse (all verifiers)"
    return "no"


def protection_verdict(diffs_by_verifier):
    """Cloaked-source clone (A) vs clean-audio ceiling (B): the cloak
    protects if EER(A) - EER(B) is significantly ABOVE zero. Verdict only
    when the whole paired CI is on one side of zero, per verifier."""
    n = len(diffs_by_verifier)
    up = [v for v, r in diffs_by_verifier.items() if r["lo"] > 0]
    down = [v for v, r in diffs_by_verifier.items() if r["hi"] < 0]
    if len(up) == n:
        return "PROTECTED (EER significantly higher, all verifiers)"
    if up:
        return f"partly protected ({len(up)}/{n} verifiers)"
    if down:
        return f"cloaked EER LOWER on {len(down)}/{n} verifiers"
    return "no significant effect"


# ---------------------------------------------------------------------------
# Recovering stems for legacy (pre-ID) score CSVs
# ---------------------------------------------------------------------------
def backfill_stems(csv_path, synth_dir, manifest_by_stem, stems=None):
    """Recover the stem column of an old score,label,group CSV.

    The scorer wrote, per clip in sorted-filename order, one genuine row
    (label 1) followed by its impostor rows (label 0); a clip whose
    genuine trial failed left no rows. So each label-1 row starts a new
    clip block. Blocks are mapped onto the sorted synth files ONLY when the
    block count equals the file count AND the per-block demographic group
    sequence matches the manifest exactly; otherwise this raises rather
    than guess. `stems` (optional) gives the scored clip list explicitly
    when the directory no longer matches what was scored (e.g. the
    original 1,500-clip clean SV2TTS ceiling). Returns the dataframe with stem and trial columns added
    (ref_stem left blank: it depends on the RNG stream).
    """
    name = str(csv_path) if isinstance(csv_path, (str, os.PathLike)) else "<score table>"
    df = pd.read_csv(csv_path) if isinstance(csv_path, (str, os.PathLike)) else csv_path.copy()
    if stems is None:
        files = sorted(f for f in os.listdir(synth_dir) if f.endswith(".wav"))
        stems = [os.path.splitext(f)[0] for f in files]
    else:  # explicit list of what was scored (e.g. a fixed subset), scoring order
        stems = sorted(stems, key=lambda s: s + ".wav")
    block = (df.label == 1).cumsum().to_numpy() - 1
    n_blocks = int(block.max()) + 1 if len(df) else 0
    if n_blocks != len(stems):
        raise ValueError(f"{name}: {n_blocks} clip blocks vs {len(stems)} clips expected ({synth_dir})")
    expected = [
        f"{manifest_by_stem[s]['descent']}-{manifest_by_stem[s]['gender']}"
        if "descent" in manifest_by_stem[s] else "" for s in stems
    ]
    first_rows = df.groupby(block).head(1)["group"].fillna("").tolist()
    if first_rows != expected:
        raise ValueError(f"{name}: group sequence does not match the expected clips; not backfilling")
    df["stem"] = [stems[b] for b in block]
    df["trial"] = np.where(df.label == 1, "genuine",
                           "impostor_" + (df.groupby(block).cumcount()).astype(str))
    df["ref_stem"] = ""
    return df
