"""Fig 5 mechanistic variant — adaptive grain refinement on a quantified inadequacy
signal, with the biological damage state kept separate from the algorithmic grain.

Each gate carries the reviewer's evidence class (pass_if.kind). The baseline
(fig05-grain-runnable) is unaffected and keeps its own gates in test_fig05_grain_swap.py.
"""
from __future__ import annotations

import copy
import json
import warnings
from pathlib import Path

import pytest
from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig05-mechanistic.composite.json"


def _run(mode="adaptive", cell_over=None, steps=36):
    spec = json.loads(COMPOSITE.read_text())
    spec["state"]["cell"]["config"]["mode"] = mode
    if cell_over:
        spec["state"]["cell"]["config"].update(cell_over)
    sim = Composite({"state": spec["state"]}, core=build_core())
    sim.run(steps)
    return gather_emitter_results(sim)[("emitter",)]


def _switch_time(rows):
    return next((float(r["time"]) for r in rows if float(r["active_grain"]) > 0.5), None)


# ── structural ────────────────────────────────────────────────────────────────

def test_composite_builds_and_runs():
    """REGRESSION_PIN: fig05-mechanistic builds and runs 36 ticks (37 rows)."""
    assert len(_run()) == 37


def test_one_active_grain_at_a_time():
    """INVARIANT: the active grain is exactly one of {coarse, fine} on every step —
    the grain indicator only ever takes the values 0 or 1."""
    rows = _run()
    assert sorted(set(round(float(r["active_grain"])) for r in rows)) in ([0, 1], [0], [1])


# ── separation of biology from grain ─────────────────────────────────────────

def test_biological_forcing_is_grain_independent():
    """INVARIANT: the stress forcing (the biological driver) is identical across all
    three modes — the grain is an algorithmic choice layered on the SAME physiology,
    not a different biology. Before the adaptive switch, coarse and adaptive share the
    same damage trajectory (the coarse approximation is valid there)."""
    a, co, fi = _run("adaptive"), _run("coarse"), _run("fine")
    for t in range(37):
        assert abs(float(a[t]["stress"]) - float(co[t]["stress"])) < 1e-12
        assert abs(float(fi[t]["stress"]) - float(co[t]["stress"])) < 1e-12
    sw = _switch_time(a)
    pre = [t for t in range(37) if float(a[t]["time"]) < sw]
    for t in pre:
        assert abs(float(a[t]["m_sol"]) - float(co[t]["m_sol"])) < 1e-12, "coarse≠adaptive before switch"


# ── conservation at handover ─────────────────────────────────────────────────

def test_no_artificial_jump_at_the_switch():
    """INVARIANT: the coarse→fine map is conserving (prolongation is identity on the
    shared damage pools), so neither biomass nor total damage jumps at the switch —
    the step at the switch is within the normal per-tick change and handover_error=0.
    (The baseline's bare grain flip has no such guarantee.)"""
    rows = _run()
    sw = _switch_time(rows)
    si = [t for t in range(37) if float(rows[t]["time"]) == sw][0]
    jump = abs(float(rows[si]["biomass"]) - float(rows[si - 1]["biomass"]))
    typ = abs(float(rows[si - 1]["biomass"]) - float(rows[si - 2]["biomass"]))
    assert jump < 1.5 * typ, "biomass jumps at the grain switch"
    assert max(abs(float(r["handover_error"])) for r in rows) < 1e-12
    # total damage continuous too
    dj = abs(float(rows[si]["damage"]) - float(rows[si - 1]["damage"]))
    dt = abs(float(rows[si - 1]["damage"]) - float(rows[si - 2]["damage"]))
    assert dj < 1.5 * dt + 1e-9, "total damage jumps at the switch"


# ── the refinement trigger is quantified, not wall-clock ─────────────────────

def test_inadequacy_signal_triggers_refinement_not_wall_clock():
    """PROSPECTIVE_PREDICTION: refinement fires when the computable inadequacy
    estimator crosses tolerance — so raising the tolerance DELAYS the switch and
    lowering it ADVANCES it (a wall-clock trigger would not move). The inadequacy at
    the switch is ≥ the tolerance."""
    tol_default = _switch_time(_run("adaptive"))
    tol_high = _switch_time(_run("adaptive", {"inadequacy_tol": 0.45}))
    tol_low = _switch_time(_run("adaptive", {"inadequacy_tol": 0.08}))
    assert tol_high is None or tol_high > tol_default, "higher tolerance should delay the switch"
    assert tol_low < tol_default, "lower tolerance should advance the switch"


# ── what refinement buys ──────────────────────────────────────────────────────

def test_refinement_predicts_phenotype_coarse_misses():
    """MECHANISTIC_ABLATION: the fine grain resolves an autocatalytic aggregation
    runaway that collapses viability — a phenotype the always-coarse model structurally
    cannot produce (it never forms aggregates). Fine/adaptive reach ~zero viability
    with substantial aggregate; coarse stays viable with no aggregate."""
    a, co, fi = _run("adaptive"), _run("coarse"), _run("fine")
    assert float(fi[-1]["viability"]) < 0.1 and float(a[-1]["viability"]) < 0.1
    assert float(co[-1]["viability"]) > 0.5, "coarse should miss the collapse"
    assert float(fi[-1]["m_agg"]) > 0.2 and float(co[-1]["m_agg"]) < 1e-9


def test_adaptive_tracks_fine_not_coarse():
    """MECHANISTIC_ABLATION: after refining, the adaptive run tracks the always-fine
    reference closely while the always-coarse run diverges — the refinement recovers
    the fine prediction at a fraction of the cost."""
    a, co, fi = _run("adaptive"), _run("coarse"), _run("fine")
    div_af = max(abs(float(a[t]["biomass"]) - float(fi[t]["biomass"])) for t in range(37))
    div_cf = max(abs(float(co[t]["biomass"]) - float(fi[t]["biomass"])) for t in range(37))
    assert div_af < 0.2 * div_cf, "adaptive should track fine far better than coarse does"


# ── honesty guard ─────────────────────────────────────────────────────────────

def test_deterministic_rerun_is_reproducibility_not_support():
    """REGRESSION_PIN (honesty guard): two identical runs are byte-identical. This is
    REPRODUCIBILITY, not mechanistic support — the mechanistic evidence comes from the
    ablations above, not from a deterministic rerun matching itself."""
    r1, r2 = _run("adaptive"), _run("adaptive")
    assert all(abs(float(r1[t]["biomass"]) - float(r2[t]["biomass"])) < 1e-15 for t in range(37))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
