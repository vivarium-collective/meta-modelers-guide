"""Fig 4 · the environment's fields drive the cell's interface ports.

The runnable fig04 composite (meta_modelers_guide.composites.fig04-runnable) wires a
real length-9 diffusing chemical grid — seeded as a nutrient GRADIENT (low at index 0,
high at index 8) — to a single cell at interior index 4. The cell senses its LOCAL
field through one typed interface (SingleCellSpatial) and acts back on the shared
environment. This test asserts the CAUSAL claim the figure makes:

  (a) a higher local chemical field ⇒ a larger `uptake` output (drive the handler
      directly at two field levels);
  (b) `mass` increases monotonically while nutrient is present (run the composite);
  (c) net `location` drift over the run is UP-gradient (toward the higher-field side).

Complements test_cellular_interface_spatial.py (spatial determination of one cell) and
test_compilation.py (that the fig04 handlers conform + compile).
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.handlers_fig04 import GRID_N, SingleCellSpatial

COMPOSITE = (
    Path(__file__).resolve().parent.parent
    / "meta_modelers_guide" / "composites" / "fig04-runnable.composite.json"
)
CELL_INDEX = 4


def _uniform_grid(level: float) -> dict:
    """A flat length-9 field at `level` — isolates the local-value response (no gradient)."""
    return {str(i): level for i in range(GRID_N)}


# ── (a) higher local field ⇒ larger uptake output ────────────────────────────
def test_higher_local_field_drives_larger_uptake():
    core = build_core()
    cell = SingleCellSpatial({"cell_index": CELL_INDEX}, core=core)

    def uptake_at(level: float) -> float:
        state = {"chemical_field": _uniform_grid(level),
                 "mechanical_field": 0.0, "location": float(CELL_INDEX)}
        return float(cell.update(state, 1.0)["uptake"])

    low = uptake_at(0.2)
    high = uptake_at(0.8)
    assert low > 0.0
    assert high > low
    # uptake is linear in the local field: 4× the field ⇒ ~4× the uptake.
    assert abs(high / low - 4.0) < 1e-6


# ── run the runnable composite for (b) and (c) ───────────────────────────────
def _run_trajectory():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def test_mass_increases_monotonically_under_nutrient():
    rows = _run_trajectory()
    mass = [float(r["mass"]) for r in rows]
    assert mass[-1] > mass[0]                      # net growth
    # monotonic non-decreasing: nutrient is present throughout, so mass never falls.
    for a, b in zip(mass, mass[1:]):
        assert b >= a - 1e-9


def test_net_drift_is_up_gradient():
    rows = _run_trajectory()
    loc = [float(r["location"]) for r in rows]
    # the cell starts at index 4 and drifts toward the higher-field side (index 8):
    # net displacement is positive (up-gradient chemotaxis).
    assert loc[-1] - loc[0] > 0.05


def test_uptake_tracks_the_local_sensed_field():
    """The port is driven BY the field: per-step uptake rises/falls with the local
    sensed concentration (the environment→port coupling, over the actual run)."""
    rows = _run_trajectory()
    local = [float(r["chemical_field"][str(CELL_INDEX)]) for r in rows]
    cum = [float(r["uptake_flux"]) for r in rows]
    step_uptake = [cum[i] - cum[i - 1] for i in range(1, len(cum))]
    local_active = local[:-1]  # field the cell sensed when it produced each step's uptake

    n = len(step_uptake)
    ml, mu = sum(local_active) / n, sum(step_uptake) / n
    cov = sum((x - ml) * (y - mu) for x, y in zip(local_active, step_uptake))
    vl = sum((x - ml) ** 2 for x in local_active) ** 0.5
    vu = sum((y - mu) ** 2 for y in step_uptake) ** 0.5
    corr = cov / (vl * vu)
    assert corr > 0.99
