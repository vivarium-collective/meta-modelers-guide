#!/usr/bin/env python
"""development-and-evolution study, Tier C ensemble runner (reviewer issues M3 + M8).

Runs BOTH evolution arms -- selection-ON (`development-evolution-spatial`) and
no-selection (`development-evolution-no-selection`) -- across N seeds, collects
the per-seed population-mean `vmax` delta (final - founder) for each arm, and
tests whether the selection-ON directional shift is distinguishable from the
no-selection (neutral drift) envelope. This REPLACES the earlier under-powered
claim -- "selection-ON up in 4/5 seeds, gated on the flagship seed 3" -- with an
honest ensemble statistic.

M3 (evolution significance): per-arm delta distribution (mean, sd, per-seed
    list) + a Mann-Whitney U rank test (selection-ON vs no-selection deltas)
    with p-value and rank-biserial effect size + a drift-null check (is the
    selection-ON shift outside the no-selection drift envelope?).
M8 (development band): `rim_core_ratio` across the same N selection-ON seeds
    (per-seed values + mean +/- sd), replacing the single-seed 1.0 -> ~1.44
    (flagship seed 3) reading with a seed band.

Honest-null rule: this TESTS a claim that may fail. If selection is not
significant at N seeds, that is a valid finding -- reported, not hidden.

Usage:
    python scripts/run_dev_evo_ensemble.py [--seeds N] [--steps T]
                                           [--workers W] [--json OUT.json]
Runs sequentially unless --workers > 1. Prints a full report to stdout.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
VMAX0 = 1.5
SEL_ARM = "development-evolution-spatial"
NOSEL_ARM = "development-evolution-no-selection"


def _run_arm_seed(args):
    """Run one composite at one seed, return the final `obs` dict of interest.

    Imports are inside the function so this works as a ProcessPoolExecutor
    worker (each process builds its own core / cobra model registry)."""
    name, seed, steps = args
    from process_bigraph import Composite
    from meta_modelers_guide.core import build_core

    core = build_core()
    state = copy.deepcopy(
        json.loads((COMPOSITES / f"{name}.composite.json").read_text())["state"]
    )
    state["evo"]["config"]["seed"] = int(seed)
    comp = Composite({"state": state}, core=core)
    comp.run(steps)
    obs = comp.state["obs"]
    # per-cell local_glucose split into core/rim (the scatter behind rim_core_ratio)
    position = obs.get("position", {})
    local_glc = obs.get("local_glucose", {})
    core_glc, rim_glc = _core_rim_glucose(position, local_glc)
    return {
        "arm": name,
        "seed": int(seed),
        "mean_vmax": float(obs["mean_vmax"]),
        "var_vmax": float(obs["var_vmax"]),
        "n_cells": float(obs["n_cells"]),
        "rim_core_ratio": float(obs["rim_core_ratio"]),
        "core_glucose": core_glc,
        "rim_glucose": rim_glc,
    }


def _core_rim_glucose(position_obs, local_glucose_obs):
    """Split per-cell local glucose into core/rim groups by the same median
    radial split `CpmEvolution._rim_core_ratio` uses -- the per-cell scatter
    behind the rim_core_ratio scalar (M8)."""
    ids = sorted(position_obs.keys())
    if len(ids) < 2:
        return [], []
    pos = np.array([position_obs[c] for c in ids], dtype=float)
    centroid = pos.mean(axis=0)
    dist = np.linalg.norm(pos - centroid, axis=1)
    median = float(np.median(dist))
    core_mask = dist <= median
    glc = np.array([local_glucose_obs.get(c, 0.0) for c in ids], dtype=float)
    return glc[core_mask].tolist(), glc[~core_mask].tolist()


# --------------------------------------------------------------------------
# Statistics -- scipy if present, else honest hand-rolled fallbacks.
# --------------------------------------------------------------------------

def mann_whitney_u(x, y):
    """Two-sided Mann-Whitney U. Returns (U1, p, rank_biserial, cles, backend).

    Uses scipy.stats.mannwhitneyu when available (exact/normal approx with tie
    correction); otherwise a hand-rolled U with the normal approximation.
    U1 is the statistic for x (selection-ON). Effect sizes, signed so POSITIVE
    means x tends to exceed y: common-language effect size CLES = U1/(n1*n2)
    (prob a random x-delta exceeds a random y-delta) and rank-biserial
    r = 2*CLES - 1 in [-1, 1]."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n1, n2 = len(x), len(y)
    try:
        from scipy.stats import mannwhitneyu
        res = mannwhitneyu(x, y, alternative="two-sided")
        U1 = float(res.statistic)
        p = float(res.pvalue)
        backend = "scipy.stats.mannwhitneyu"
    except Exception:
        # hand-rolled: rank the pooled sample, U1 from rank sum of x
        pooled = np.concatenate([x, y])
        order = pooled.argsort()
        ranks = np.empty_like(order, dtype=float)
        ranks[order] = np.arange(1, len(pooled) + 1)
        # average ties
        _assign_tie_ranks(pooled, ranks)
        R1 = ranks[:n1].sum()
        U1 = R1 - n1 * (n1 + 1) / 2.0
        mu = n1 * n2 / 2.0
        sigma = np.sqrt(n1 * n2 * (n1 + n2 + 1) / 12.0)
        z = (U1 - mu) / sigma if sigma > 0 else 0.0
        p = float(2.0 * _norm_sf(abs(z)))
        backend = "hand-rolled U (normal approx)"
    cles = U1 / (n1 * n2)
    r_rb = 2.0 * cles - 1.0
    return U1, p, r_rb, cles, backend


def _assign_tie_ranks(values, ranks):
    order = values.argsort()
    sv = values[order]
    i = 0
    n = len(sv)
    while i < n:
        j = i
        while j + 1 < n and sv[j + 1] == sv[i]:
            j += 1
        if j > i:
            avg = ranks[order[i:j + 1]].mean()
            ranks[order[i:j + 1]] = avg
        i = j + 1


def _norm_sf(z):
    # standard-normal survival function via erfc
    import math
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def wilcoxon_vs_center(deltas, center):
    """One-sample Wilcoxon signed-rank of (deltas - center) against 0 --
    is the selection-ON shift located above the no-selection drift center?
    Returns (statistic, p) or (None, None) if scipy is unavailable / degenerate."""
    d = np.asarray(deltas, dtype=float) - center
    d = d[d != 0]
    if len(d) < 1:
        return None, None
    try:
        from scipy.stats import wilcoxon
        res = wilcoxon(d, alternative="greater")
        return float(res.statistic), float(res.pvalue)
    except Exception:
        return None, None


def summarize(deltas):
    a = np.asarray(deltas, dtype=float)
    return {
        "n": int(len(a)),
        "mean": float(a.mean()),
        "sd": float(a.std(ddof=1)) if len(a) > 1 else 0.0,
        "median": float(np.median(a)),
        "min": float(a.min()),
        "max": float(a.max()),
        "n_up": int((a > 0.05).sum()),
    }


def analyze(sel_results, nosel_results):
    sel_deltas = [r["mean_vmax"] - VMAX0 for r in sel_results]
    nosel_deltas = [r["mean_vmax"] - VMAX0 for r in nosel_results]

    U, p, r_rb, cles, backend = mann_whitney_u(sel_deltas, nosel_deltas)

    # drift-null: envelope from the no-selection (neutral) arm.
    nosel = np.asarray(nosel_deltas, dtype=float)
    drift_hi = float(np.percentile(nosel, 95))
    drift_center = float(np.median(nosel))
    frac_above_envelope = float(np.mean(np.asarray(sel_deltas) > drift_hi))
    w_stat, w_p = wilcoxon_vs_center(sel_deltas, drift_center)

    rim = [r["rim_core_ratio"] for r in sel_results]
    return {
        "sel_deltas": sel_deltas,
        "nosel_deltas": nosel_deltas,
        "sel_summary": summarize(sel_deltas),
        "nosel_summary": summarize(nosel_deltas),
        "mannwhitney": {"U": U, "p": p, "rank_biserial": r_rb, "cles": cles,
                        "backend": backend},
        "drift_null": {
            "envelope_95pct": drift_hi,
            "center_median": drift_center,
            "frac_sel_above_envelope": frac_above_envelope,
            "wilcoxon_stat": w_stat,
            "wilcoxon_p_greater": w_p,
        },
        "rim_core": {
            "per_seed": rim,
            "mean": float(np.mean(rim)),
            "sd": float(np.std(rim, ddof=1)) if len(rim) > 1 else 0.0,
            "min": float(np.min(rim)),
            "max": float(np.max(rim)),
        },
        "sel_results": sel_results,
    }


def run_ensemble(seeds, steps, workers):
    jobs = [(SEL_ARM, s, steps) for s in seeds] + [(NOSEL_ARM, s, steps) for s in seeds]
    t0 = time.time()
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            out = list(ex.map(_run_arm_seed, jobs))
    else:
        out = [_run_arm_seed(j) for j in jobs]
    elapsed = time.time() - t0
    sel = sorted([r for r in out if r["arm"] == SEL_ARM], key=lambda r: r["seed"])
    nosel = sorted([r for r in out if r["arm"] == NOSEL_ARM], key=lambda r: r["seed"])
    return sel, nosel, elapsed


def print_report(res, seeds, steps, elapsed):
    ss, ns = res["sel_summary"], res["nosel_summary"]
    mw, dn, rc = res["mannwhitney"], res["drift_null"], res["rim_core"]
    print("=" * 74)
    print(f"DEV-EVO ENSEMBLE  N={len(seeds)} seeds  steps={steps}  ({elapsed:.0f}s)")
    print("=" * 74)
    print("\nM3 -- EVOLUTION: per-seed mean_vmax delta (final - founder 1.5)")
    print(f"  selection-ON : {[round(d,3) for d in res['sel_deltas']]}")
    print(f"     mean={ss['mean']:+.3f}  sd={ss['sd']:.3f}  median={ss['median']:+.3f} "
          f"range=[{ss['min']:+.3f},{ss['max']:+.3f}]  up={ss['n_up']}/{ss['n']}")
    print(f"  no-selection : {[round(d,3) for d in res['nosel_deltas']]}")
    print(f"     mean={ns['mean']:+.3f}  sd={ns['sd']:.3f}  median={ns['median']:+.3f} "
          f"range=[{ns['min']:+.3f},{ns['max']:+.3f}]  up={ns['n_up']}/{ns['n']}")
    print(f"\n  Mann-Whitney U (sel vs no-sel, two-sided): U={mw['U']:.1f}  "
          f"p={mw['p']:.4g}  rank-biserial r={mw['rank_biserial']:+.3f}  "
          f"CLES={mw['cles']:.3f}")
    print(f"     backend: {mw['backend']}")
    sig = mw["p"] < 0.05
    print(f"     -> {'SIGNIFICANT' if sig else 'NOT significant'} at alpha=0.05")
    print(f"\n  Drift-null check (no-selection = neutral envelope):")
    print(f"     no-sel 95th-pctile delta = {dn['envelope_95pct']:+.3f}; "
          f"frac of selection-ON seeds above it = {dn['frac_sel_above_envelope']:.2f}")
    if dn["wilcoxon_p_greater"] is not None:
        print(f"     Wilcoxon(sel deltas > no-sel median): stat={dn['wilcoxon_stat']:.1f} "
              f"p={dn['wilcoxon_p_greater']:.4g}")
    print(f"\nM8 -- DEVELOPMENT: rim_core_ratio across the {len(seeds)} selection-ON seeds")
    print(f"  per-seed: {[round(x,3) for x in rc['per_seed']]}")
    print(f"  mean={rc['mean']:.3f}  sd={rc['sd']:.3f}  range=[{rc['min']:.3f},{rc['max']:.3f}]")
    print("=" * 74)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30, help="number of seeds (1..N)")
    ap.add_argument("--steps", type=int, default=45)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--json", type=str, default=None, help="write full results JSON here")
    args = ap.parse_args(argv)

    seeds = list(range(1, args.seeds + 1))
    sel, nosel, elapsed = run_ensemble(seeds, args.steps, args.workers)
    res = analyze(sel, nosel)
    print_report(res, seeds, args.steps, elapsed)

    if args.json:
        Path(args.json).write_text(json.dumps(
            {"seeds": seeds, "steps": args.steps, "elapsed_s": elapsed, "analysis": res},
            indent=2))
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
