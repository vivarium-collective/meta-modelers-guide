"""Fig 8 mechanistic variant — a self-maintaining cell with a boundary, turnover,
repair and viability. Where the baseline shows DEPENDENCE via knockout but only
accumulates, this variant shows the properties that make self-maintenance
meaningful: PERSISTENCE at a steady state, component REPLACEMENT against turnover,
RECOVERY after a membrane injury, and viability COLLAPSE when any edge of the
operational-closure loop is broken.

Each gate carries the reviewer's evidence class (pass_if.kind). Matched-null
controls use an EPSILON, never 0.0 (a float 0.0 config is restored to the schema
default by bigraph_schema).

Honest scope: this demonstrates operational closure, homeostasis and recovery —
NOT autopoiesis in the strong sense (the boundary is a scalar `area`, the viability
target is scripted). See the study.yaml findings/limitations.
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
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig08-mechanistic.composite.json"
EPS = 1e-9
POOLS = ["membrane", "enzymes", "energy", "precursor", "nutrient_int"]


def _run(cell_over=None, reservoir_over=None, steps=None):
    spec = json.loads(COMPOSITE.read_text())
    if steps is None:
        steps = spec["default_n_steps"]
    if cell_over:
        spec["state"]["cell"]["config"].update(cell_over)
    if reservoir_over:
        spec["state"]["reservoir"]["config"].update(reservoir_over)
    sim = Composite({"state": spec["state"]}, core=build_core())
    sim.run(steps)
    return gather_emitter_results(sim)[("emitter",)]


def _series(rows, key):
    return [float(r[key]) for r in rows]


# ── structural / invariant ────────────────────────────────────────────────────

def test_composite_builds_and_runs():
    """REGRESSION_PIN: fig08-mechanistic builds and runs 90 ticks (91 rows)."""
    assert len(_run()) == 91


def test_all_pools_positive_and_bounded():
    """INVARIANT: every component stays strictly positive and bounded over the run —
    nothing collapses to zero (the cell persists) and nothing explodes."""
    rows = _run()
    for k in POOLS:
        s = _series(rows, k)
        assert min(s) > 0.0, f"{k} collapsed to zero"
        assert max(s) < 100.0, f"{k} exploded"


def test_persists_at_a_steady_state():
    """INVARIANT: with no injury the cell grows to a far-from-equilibrium STEADY
    STATE and holds it — second-half drift is small. Persistence, not monotonic
    accumulation (the baseline's membrane just piles up)."""
    rows = _run(cell_over={"perturb_at": -1.0})
    drift = max(abs(_series(rows, k)[-1] - _series(rows, k)[60]) / max(_series(rows, k)[60], 1e-9)
                for k in ["membrane", "enzymes", "energy"])
    assert drift < 0.1, f"pools still drifting {drift:.3f} — not a steady state"


# ── component replacement against turnover ───────────────────────────────────

def test_turnover_requires_active_replacement():
    """MECHANISTIC_ABLATION: the steady-state membrane is HELD by repair balancing
    first-order degradation (component replacement). Knock out repair and the
    membrane decays away — the steady level is maintained, not inert."""
    full = _series(_run(cell_over={"perturb_at": -1.0}), "membrane")
    norepair = _series(_run(cell_over={"perturb_at": -1.0, "k_repair": EPS}), "membrane")
    assert full[-1] > 2.0, "membrane not maintained at a steady level"
    assert norepair[-1] < 0.3 * full[-1], "without repair the membrane should decay (turnover unopposed)"


# ── recovery after perturbation ──────────────────────────────────────────────

def test_recovers_after_membrane_injury():
    """MECHANISTIC_ABLATION: a one-time membrane injury at tick 45 (−60%) drops the
    boundary and depresses viability; the cell then REPAIRS the membrane and
    viability RECOVERS to its pre-injury steady state. Self-repair, not a scripted
    bounce — removing repair leaves it collapsed."""
    rows = _run()  # perturb_at = 45 by default
    mem = _series(rows, "membrane")
    v = _series(rows, "viability")
    assert mem[45] < 0.6 * mem[44], "injury did not remove membrane"
    assert min(v[45:63]) < 0.85 * v[44], "viability did not dip after injury"
    assert mem[-1] > 0.9 * mem[44], "membrane did not recover"
    assert v[-1] > 0.95 * v[44], "viability did not recover"
    # recovery requires repair: with repair off, no bounce-back
    norepair = _series(_run(cell_over={"k_repair": EPS}), "membrane")
    assert norepair[-1] < 0.3 * mem[-1], "recovery should require active repair"


def test_repeated_perturbation_persists():
    """MECHANISTIC_ABLATION: the cell survives and recovers from an injury even when
    it lands during the growth phase — persistence across perturbation, not a
    one-off tuned bounce."""
    rows = _run(cell_over={"perturb_at": 25.0})
    mem = _series(rows, "membrane")
    v = _series(rows, "viability")
    assert mem[-1] > 0.9 * max(mem), "cell did not recover from an early injury"
    assert v[-1] > 0.9, "viability did not return to health after an early injury"


# ── operational closure: break any edge → collapse ───────────────────────────

@pytest.mark.parametrize("ko", ["k_transport", "k_met", "k_expr", "k_repair"])
def test_knockout_collapses_viability(ko):
    """MECHANISTIC_ABLATION: operational closure means every edge of the loop is
    required. Knock out import / metabolism / enzyme-synthesis / repair (epsilon,
    not 0.0) and the membrane collapses and viability falls to ~0 — dependence on
    each coupling edge, demonstrated, not asserted."""
    rows = _run(cell_over={ko: EPS, "perturb_at": -1.0})
    assert _series(rows, "viability")[-1] < 0.1, f"{ko} knockout did not collapse viability"
    assert _series(rows, "membrane")[-1] < 0.5, f"{ko} knockout did not collapse the membrane"


def test_depends_on_external_input():
    """MECHANISTIC_ABLATION (matched external-input accounting): on a non-replenished
    medium (closed) the external nutrient is drawn down and the cell cannot
    self-maintain — viability collapses. The self-maintenance is of ORGANIZATION,
    not of matter/energy: it runs on a throughput the medium must supply."""
    rows = _run(reservoir_over={"replenish": EPS}, cell_over={"perturb_at": -1.0})
    assert _series(rows, "nutrient_ext")[-1] < 0.2, "external nutrient should deplete without replenishment"
    assert _series(rows, "viability")[-1] < 0.3, "cell should not persist on a depleted medium"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
