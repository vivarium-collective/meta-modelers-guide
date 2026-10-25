"""Fig 3 (paper §Cellular interface) mechanistic variant — a cell whose interface
ports are COUPLED through a shared ATP pool and a temperature-set enzyme activity.

Where the baseline's ports each respond only to their own driver (independent), here
a perturbation PROPAGATES through shared internal state: nutrient/temperature →
uptake → ATP → growth & maintenance → viability. The metabolically-disabled cell
(catalytic_capacity = ε, NOT 0.0) breaks the propagation — the matched-null control.

Gates carry the reviewer's evidence class (pass_if.kind).
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
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig03-mechanistic.composite.json"
EPS = 1e-9


def _run(cell_over=None, env_over=None, steps=24):
    spec = json.loads(COMPOSITE.read_text())
    if cell_over:
        spec["state"]["cell"]["config"].update(cell_over)
    if env_over:
        spec["state"]["env_driver"]["config"].update(env_over)
        # the driver only emits CHANGES from its base level, so the env store's
        # initial value must match the base config (nutrient_hi / temp_base);
        # keep them in sync when a test overrides the base level.
        if "nutrient_hi" in env_over:
            spec["state"]["env"]["nutrient"]["_default"] = env_over["nutrient_hi"]
        if "temp_base" in env_over:
            spec["state"]["env"]["temperature"]["_default"] = env_over["temp_base"]
    sim = Composite({"state": spec["state"]}, core=build_core())
    sim.run(steps)
    return gather_emitter_results(sim)[("emitter", )]


def _col(rows, key):
    return [float(r[key]) for r in rows]


# ── structural ────────────────────────────────────────────────────────────────

def test_composite_builds_and_runs():
    """REGRESSION_PIN: fig03-mechanistic builds and runs 24 ticks (25 rows)."""
    assert len(_run()) == 25


# ── invariants ────────────────────────────────────────────────────────────────

def test_state_variables_stay_bounded():
    """INVARIANT: the ATP pool stays ≥ 0, viability stays in [0,1], and biomass is
    non-decreasing — the shared state never runs off to nonsense."""
    rows = _run()
    assert all(float(r["atp"]) >= -1e-9 for r in rows)
    assert all(-1e-9 <= float(r["viability"]) <= 1.0 + 1e-9 for r in rows)
    bm = _col(rows, "biomass")
    assert all(bm[i + 1] >= bm[i] - 1e-9 for i in range(len(bm) - 1))


def test_growth_requires_atp_energy_consistency():
    """INVARIANT: growth is paid for out of ATP — when the ATP pool is depleted the
    growth rate collapses toward zero (anabolism cannot run without the shared energy
    currency). Not an independent Monod curve on nutrient."""
    rows = _run()  # heat-shock run drains ATP to 0 by the end
    atp = _col(rows, "atp")
    growth = _col(rows, "growth_rate")
    # at the step with the lowest ATP, growth is far below its pre-stress peak
    i_min = atp.index(min(atp))
    assert growth[i_min] < 0.25 * max(growth), "growth did not fall as ATP depleted"


# ── mechanistic ablations: propagation through shared state ───────────────────

def test_heat_shock_cascades_through_shared_state():
    """MECHANISTIC_ABLATION: one temperature step (37→48 °C at t=12) propagates
    through the SHARED enzyme/ATP state to EVERY downstream port — enzyme activity,
    uptake, ATP, growth AND viability all drop together — not just the thermal port.
    This is physiological coupling, not nine independent driver responses."""
    rows = _run()
    enz, growth, viab = _col(rows, "enzyme_activity"), _col(rows, "growth_rate"), _col(rows, "viability")
    assert enz[13] < 0.4 * enz[11], "enzyme activity did not drop on heat shock"
    assert growth[16] < 0.4 * growth[11], "growth did not fall after heat shock (no propagation)"
    assert viab[-1] < 0.8, "viability did not decline after heat shock"


def test_nutrient_starvation_propagates_to_growth_and_viability():
    """MECHANISTIC_ABLATION: a nutrient step-down (2.0→0.03 at t=12) propagates
    through uptake→ATP→growth AND, as ATP starves below maintenance, to viability —
    the nutrient perturbation moves MULTIPLE ports via shared state."""
    rows = _run(env_over={"nutrient_hi": 2.0, "nutrient_lo": 0.03, "nutrient_step_time": 12.0,
                          "temp_base": 37.0, "temp_step": 37.0, "temp_step_time": 1e9})
    growth, atp, viab = _col(rows, "growth_rate"), _col(rows, "atp"), _col(rows, "viability")
    assert growth[16] < 0.4 * growth[11], "growth did not fall on starvation"
    assert atp[16] < 0.3 * atp[11], "ATP pool did not drain on starvation"
    assert viab[-1] < 0.8, "viability did not decline under energy starvation"


def test_disabled_metabolism_breaks_propagation():
    """MECHANISTIC_ABLATION (matched null, ε): with metabolism disabled
    (catalytic_capacity = ε) the cell cannot turn nutrient into ATP, so NOTHING
    propagates — growth stays ~0 and biomass stays flat regardless of the nutrient
    supply. Proves the coupling runs through the shared ATP node, not direct wires."""
    rows = _run(cell_over={"catalytic_capacity": EPS})
    assert max(_col(rows, "growth_rate")) < 1e-3
    bm = _col(rows, "biomass")
    assert abs(bm[-1] - bm[0]) < 1e-3, "disabled cell still grew — propagation not through metabolism"


def test_cross_port_coupling_off_diagonal():
    """MECHANISTIC_ABLATION: perturbing ONE input moves MULTIPLE outputs (a dense
    response matrix), whereas in the disabled cell a nutrient perturbation moves
    only its own uptake port (diagonal) — the off-diagonal coupling IS the shared
    internal state. We compare final biomass response to a nutrient change."""
    hi = _run(env_over={"nutrient_hi": 2.0, "nutrient_lo": 2.0, "nutrient_step_time": 1e9,
                        "temp_base": 37.0, "temp_step": 37.0, "temp_step_time": 1e9})
    lo = _run(env_over={"nutrient_hi": 0.4, "nutrient_lo": 0.4, "nutrient_step_time": 1e9,
                        "temp_base": 37.0, "temp_step": 37.0, "temp_step_time": 1e9})
    # intact: less nutrient ⇒ less biomass (propagates through ATP to growth)
    assert _col(lo, "biomass")[-1] < _col(hi, "biomass")[-1] - 0.5
    # disabled: nutrient change does NOT move biomass (no propagation)
    hi_d = _run(cell_over={"catalytic_capacity": EPS},
                env_over={"nutrient_hi": 2.0, "nutrient_lo": 2.0, "nutrient_step_time": 1e9})
    lo_d = _run(cell_over={"catalytic_capacity": EPS},
                env_over={"nutrient_hi": 0.4, "nutrient_lo": 0.4, "nutrient_step_time": 1e9})
    assert abs(_col(hi_d, "biomass")[-1] - _col(lo_d, "biomass")[-1]) < 1e-3


# ── formula verification (kept as such, per the review) ──────────────────────

def test_uptake_saturates_formula_only():
    """EMPIRICAL_COMPARISON / formula verification: the uptake transporter saturates
    (Michaelis–Menten in nutrient, at full enzyme activity). This is an
    implementation check of the rate law, NOT evidence of physiology — the physiology
    claim rests on the propagation tests above."""
    from meta_modelers_guide.handlers_fig03_mech import MetabolicCell
    core = build_core()
    cfg = dict(vmax_uptake=1.0, km=0.5, catalytic_capacity=1.0, temp_opt=37.0, temp_width=9.0)

    def uptake_at(c):
        cell = MetabolicCell(cfg, core=core)
        return cell.update({"nutrient": c, "temperature": 37.0, "atp": 1.0, "biomass": 1.0, "viability": 1.0}, 1.0)["uptake"]

    assert uptake_at(100.0) > 0.98 * 1.0          # approaches vmax
    assert uptake_at(0.05) < 0.2 * uptake_at(100.0)  # linear regime far below Km


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
