# tests/test_dev_evo_ensemble.py
"""development-and-evolution, Tier C -- the ENSEMBLE re-gate (reviewer M3 + M8).

Replaces the earlier flagship-seed-3 gate with a gate on the ENSEMBLE
statistic: run both evolution arms across N seeds and test whether the
selection-ON population-mean-`vmax` shift is statistically distinguishable from
the no-selection (neutral drift) envelope.

M3 (evolution significance): a Mann-Whitney U rank test on the per-seed deltas
    (selection-ON vs no-selection) must be significant (p < 0.05) with the
    effect in the selection-ON direction, AND a drift-null check (Wilcoxon of
    the selection-ON deltas above the no-selection median) must reject neutral
    drift. This is the re-gate the study's own "next step (Tier C)" named.
M8 (development band): rim_core_ratio across the same N selection-ON seeds must
    average clearly above 1.0 -- an ensemble band, not the single-seed reading.

Honest-null note: this TESTS a claim that could have failed. It did NOT -- at
N=30 the rank test is p=5.3e-4 (rank-biserial r=+0.52, CLES 0.76) and the
drift-null Wilcoxon is p=1.2e-5. The gate here runs N=20 (still p~1e-2, ~4x
margin) so CI stays affordable; the study.yaml headline reports the N=30 run.

The run is deterministic (seed threads into both the potts world and the
mutation RNG -- tests/test_cpm_evolution_spike.py::test_seed_threads...), so
the ensemble statistic is reproducible.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")
pytest.importorskip("cobra")

# Put scripts/ on sys.path and import the runner by NAME (not importlib from a
# file path) so that ProcessPoolExecutor's spawned workers -- which re-import
# the module to unpickle the worker function -- can find it too (spawn
# propagates the parent's sys.path). Reuses the exact ensemble + statistics the
# study.yaml headline numbers come from, so the test and the reported figures
# cannot drift.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import run_dev_evo_ensemble as runner  # noqa: E402

# N=20: robustly significant (p~0.01, ~4x margin below alpha) yet ~40 runs, so
# with a small worker pool it finishes in well under a minute.
N_SEEDS = 20
WORKERS = min(8, (os.cpu_count() or 2))


@pytest.fixture(scope="module")
def ensemble():
    seeds = list(range(1, N_SEEDS + 1))
    sel, nosel, _elapsed = runner.run_ensemble(seeds, steps=45, workers=WORKERS)
    return runner.analyze(sel, nosel)


def test_selection_significant_vs_drift_null(ensemble):
    """M3 re-gate: the ensemble Mann-Whitney U rank test (selection-ON vs
    no-selection per-seed deltas) is significant, in the selection-ON
    direction, and the drift-null (Wilcoxon of selection-ON deltas above the
    no-selection median) rejects neutral drift. This REPLACES the single-seed
    `mean_vmax > 1.6` (flagship seed 3) acceptance criterion."""
    mw = ensemble["mannwhitney"]
    dn = ensemble["drift_null"]
    ss = ensemble["sel_summary"]
    ns = ensemble["nosel_summary"]

    print(f"\nN={N_SEEDS}: selection-ON mean delta {ss['mean']:+.3f} (up {ss['n_up']}/{ss['n']}) "
          f"vs no-selection {ns['mean']:+.3f} (up {ns['n_up']}/{ns['n']})")
    print(f"Mann-Whitney U={mw['U']:.1f} p={mw['p']:.4g} rank-biserial={mw['rank_biserial']:+.3f} "
          f"CLES={mw['cles']:.3f}; drift-null Wilcoxon p={dn['wilcoxon_p_greater']}")

    # (1) selection-ON vs no-selection is significant
    assert mw["p"] < 0.05, (
        f"rank test not significant at N={N_SEEDS} (p={mw['p']:.4g}) -- "
        "the ensemble does not distinguish selection from drift")
    # (2) the effect is in the selection-ON direction (selection-ON deltas larger)
    assert mw["rank_biserial"] > 0.0, "effect is not in the selection-ON direction"
    assert ss["mean"] > ns["mean"], "selection-ON mean delta not above no-selection"
    # (3) drift-null rejected: selection-ON shift sits above the neutral envelope
    assert dn["wilcoxon_p_greater"] is not None and dn["wilcoxon_p_greater"] < 0.05, (
        f"drift-null not rejected (Wilcoxon p={dn['wilcoxon_p_greater']}) -- "
        "the selection-ON shift is within the neutral drift envelope")


def test_no_selection_is_centered_near_zero(ensemble):
    """The no-selection arm is a genuine neutral-drift null: its per-seed
    delta distribution is centered near zero (undirected), the reference the
    selection-ON shift is tested against."""
    ns = ensemble["nosel_summary"]
    print(f"\nno-selection delta mean={ns['mean']:+.3f} median={ns['median']:+.3f} "
          f"sd={ns['sd']:.3f} up={ns['n_up']}/{ns['n']}")
    assert abs(ns["mean"]) < 0.15, (
        f"no-selection mean delta {ns['mean']:+.3f} is not near-zero -- "
        "the neutral control looks directional")


def test_rim_core_ratio_band(ensemble):
    """M8: the development rim_core_ratio is an ensemble BAND, not a
    single-seed reading -- its mean across the N selection-ON seeds is clearly
    above the 1.0 no-gradient floor (core more depleted than rim)."""
    rc = ensemble["rim_core"]
    print(f"\nrim_core_ratio N={N_SEEDS}: mean={rc['mean']:.3f} sd={rc['sd']:.3f} "
          f"range=[{rc['min']:.3f},{rc['max']:.3f}]")
    assert rc["mean"] > 1.2, (
        f"rim_core_ratio ensemble mean {rc['mean']:.3f} shows no clear "
        "core/rim heterogeneity band")
    assert rc["min"] > 1.0, (
        f"a seed ({rc['min']:.3f}) shows no gradient at all -- band floor breached")
