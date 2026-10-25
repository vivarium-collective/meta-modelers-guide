"""Fig 11 mechanistic variant — a real Wright–Fisher population under selection,
mutation and heritable variation.

Each gate carries the reviewer's evidence class (pass_if.kind). CRUCIALLY, the
selection/robustness claims are quantified over MANY independent seeds with spread —
a single seeded rerun verifies reproducibility, not robustness. Matched-null
controls use the neutral/no_mutation switches (which set the strength to 0 inside
the engine), not a float 0.0 config.

The baseline place-graph toy (fig11-evolution, one seed, capacity 12) is unaffected
and keeps its gates in test_fig11_dynamics.py.
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pytest
from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.handlers_fig11_mech import EvolvingPopulation, ensemble

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig11-mechanistic.composite.json"


def _run_composite():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


# ── composite / engine ───────────────────────────────────────────────────────

def test_composite_builds_and_runs():
    """REGRESSION_PIN: fig11-mechanistic builds and runs 40 generations (41 rows)."""
    rows = _run_composite()
    assert len(rows) == 41


def test_demographic_bookkeeping_conserved():
    """INVARIANT: every generation has exactly N individuals, and every offspring's
    parent index is a valid member of the previous generation (no phantom ancestors,
    no id reuse). Newborn topology is well-formed."""
    pop = EvolvingPopulation(seed=0, capacity=200, mut_sigma=0.1)
    for _ in range(25):
        n_before = pop.N
        pop.step()
        assert pop.traits.shape[0] == pop.N == n_before, "population size not conserved at N"
        parents = pop.ancestry[-1]
        assert parents.shape[0] == pop.N
        assert parents.min() >= 0 and parents.max() < pop.N, "parent index out of range"


# ── selection vs neutral drift (MANY seeds) ──────────────────────────────────

def test_selection_beats_neutral_drift_many_seeds():
    """MECHANISTIC_ABLATION over 40 seeds: with selection the population tracks the
    drifting optimum (small, bounded lag); the matched NEUTRAL control (sel→0, pure
    drift) wanders far away. The separation is large relative to the across-seed
    spread — a statistical result, not a single-seed anecdote."""
    _, lag_sel, _ = ensemble(generations=40, n_seeds=40, drift=0.06, sel_strength=1.0,
                             mut_sigma=0.12, capacity=300)
    _, lag_neu, _ = ensemble(generations=40, n_seeds=40, drift=0.06, neutral=True, capacity=300)
    sel_final, neu_final = lag_sel[:, -1], lag_neu[:, -1]
    assert sel_final.mean() < 0.4 * neu_final.mean(), "selection did not beat neutral drift"
    # separation exceeds the pooled spread (clearly distinguishable)
    assert neu_final.mean() - sel_final.mean() > 3 * (sel_final.std() + neu_final.std())


def test_heritability_is_near_one():
    """EMPIRICAL_COMPARISON: under clonal inheritance plus Gaussian mutation the
    realized (narrow-sense) heritability — the parent–offspring regression slope —
    is ≈ 1, as the quantitative-genetics theory predicts."""
    slopes = []
    for s in range(10):
        par, off = EvolvingPopulation(seed=s, capacity=400, mut_sigma=0.12).parent_offspring()
        slopes.append(np.polyfit(par, off, 1)[0])
    assert abs(np.mean(slopes) - 1.0) < 0.05, f"h² = {np.mean(slopes):.3f}, expected ≈ 1"


def test_no_mutation_erodes_variance():
    """MECHANISTIC_ABLATION (matched null): with mutation off, no new variation is
    introduced, so selection + drift erode the heritable variance toward zero — the
    population loses its capacity to respond. Isolates the role of mutation."""
    pop = EvolvingPopulation(seed=1, capacity=300, no_mutation=True, trait_sd0=0.5)
    h = pop.run(30)
    assert h["var"][-1] < 0.1 * h["var"][0], "variance should erode without mutation"


# ── adaptation failure (prospective threshold) ───────────────────────────────

def test_adaptation_fails_when_optimum_moves_too_fast():
    """PROSPECTIVE_PREDICTION: the per-generation selection response is bounded
    (R = h²·S, limited by the standing variance), so the tracking lag must GROW with
    the optimum's drift rate and run away once the drift exceeds what selection can
    supply. Predicted before running; verified by a drift sweep over many seeds."""
    lags = {d: ensemble(generations=40, n_seeds=20, drift=d, sel_strength=1.0,
                        mut_sigma=0.12, capacity=300)[1][:, -1].mean()
            for d in (0.02, 0.10, 0.30, 0.55)}
    vals = [lags[d] for d in (0.02, 0.10, 0.30, 0.55)]
    assert all(vals[i + 1] > vals[i] for i in range(len(vals) - 1)), "lag should grow with drift"
    assert vals[-1] > 5 * vals[0], "lag should run away at high drift (adaptation failure)"


# ── reproducibility is NOT robustness ────────────────────────────────────────

def test_same_seed_reproduces_exactly_but_seeds_differ():
    """REGRESSION_PIN + robustness note: the same seed reproduces an identical
    trajectory (reproducibility), but DIFFERENT seeds give different realizations
    whose spread is non-negligible — so a single seeded rerun verifies
    reproducibility, not robustness. (Directly answers the review.)"""
    a = EvolvingPopulation(seed=5, capacity=200).run(30)["mean"]
    b = EvolvingPopulation(seed=5, capacity=200).run(30)["mean"]
    assert np.allclose(a, b), "same seed should reproduce exactly"
    finals = [EvolvingPopulation(seed=s, capacity=200).run(30)["mean"][-1] for s in range(20)]
    assert np.std(finals) > 1e-3, "across-seed spread should be non-trivial (robustness ≠ reproducibility)"


# ── executable-trait fitness ─────────────────────────────────────────────────

def test_uptake_mode_tracks_derived_optimum():
    """MECHANISTIC_ABLATION: with fitness derived from an executable metabolic
    tradeoff (Michaelis–Menten uptake minus a quadratic cost), the moving optimum a*
    is an EMERGENT consequence of the drifting resource, not an imposed Gaussian — and
    the evolved mean trait climbs with it (positive correlation over generations)."""
    m, _, opt = ensemble(generations=50, n_seeds=25, fitness_mode="uptake", drift=0.05,
                         mut_sigma=0.05, capacity=300, trait_mean0=0.4, trait_sd0=0.1)
    mean_traj = m.mean(0)
    assert mean_traj[-1] > mean_traj[0] + 0.3, "evolved trait should climb toward the metabolic optimum"
    assert np.corrcoef(mean_traj, opt)[0, 1] > 0.95, "evolved mean should track the derived optimum a*"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
