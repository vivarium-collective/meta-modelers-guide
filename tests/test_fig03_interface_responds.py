"""Fig 3 · the environment's drivers drive the cell's interface ports.

The runnable fig03 composite (meta_modelers_guide.composites.fig03-runnable) wires a
bounded cell (CellularInterfaceHandler) to an environment that supplies a chemical
concentration and holds a thermal driver ABOVE the cell's optimum (45 °C, opt 37 °C).
The cell senses those drivers through one typed interface and exposes typed ports
(uptake, growth_rate, viability, shape…). This test asserts the CAUSAL claims the
figure makes:

  (a) a higher chemical supply ⇒ a larger `uptake` flux AND a larger `growth_rate`
      (Monod) — drive the handler directly at two supply levels;
  (b) a temperature ABOVE optimum drives `viability` strictly down, step by step
      (first-order Arrhenius thermal death) — over the actual run;
  (c) at the OPTIMAL temperature viability barely changes (death is negligible),
      isolating temperature as the cause in (b).

Complements test_cellular_interface_spatial.py (spatial determination of one cell)
and test_compilation.py (that the fig03b handler conforms + compiles).
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.handlers_fig03b import CellularInterfaceHandler

COMPOSITE = (
    Path(__file__).resolve().parent.parent
    / "meta_modelers_guide" / "composites" / "fig03-runnable.composite.json"
)
TEMP_OPT = 37.0


def _drive(chemical: float, thermal: float) -> dict:
    """One update of a fresh handler at a given chemical supply and temperature."""
    core = build_core()
    cell = CellularInterfaceHandler({}, core=core)
    state = {"chemical_ext": chemical, "mechanical_ext": 0.0,
             "electrical_ext": 0.0, "thermal_ext": thermal}
    return cell.update(state, 1.0)


# ── (a) higher chemical supply ⇒ larger uptake AND larger growth (Monod) ──────
def test_higher_chemical_supply_drives_uptake_and_growth():
    low = _drive(chemical=0.2, thermal=TEMP_OPT)
    high = _drive(chemical=1.0, thermal=TEMP_OPT)

    # uptake flux is negative (net uptake); a higher supply ⇒ a MORE negative flux.
    assert low["chemical"] < 0.0
    assert high["chemical"] < low["chemical"]        # more nutrient taken up
    # uptake is linear in supply: 5× the concentration ⇒ ~5× the uptake magnitude.
    assert abs(high["chemical"] / low["chemical"] - 5.0) < 1e-6

    # growth follows Monod: strictly higher supply ⇒ strictly higher growth_rate.
    assert 0.0 < low["growth_rate"] < high["growth_rate"]


# ── run the runnable composite for the viability claims ──────────────────────
def _run_trajectory(overrides: dict | None = None):
    spec = json.loads(COMPOSITE.read_text())
    if overrides:
        for path, value in overrides.items():
            node, leaf = path
            spec["state"][node][leaf]["_default"] = value
            spec["state"][node][leaf]["_value"] = value
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def test_above_optimum_drives_viability_strictly_down():
    """The composite seeds 45 °C (above 37 °C optimum): viability falls monotonically
    and ends well below where it started — Arrhenius thermal death at the port."""
    rows = _run_trajectory()
    temp = [float(r["thermal_ext"]) for r in rows]
    viab = [float(r["viability"]) for r in rows]

    assert all(x > TEMP_OPT for x in temp)           # driver held above optimum
    assert viab[0] > 0.99                            # starts fully viable
    assert viab[-1] < 0.5                            # collapses over the run
    # strictly decreasing — each step kills a real fraction (Arrhenius death).
    for a, b in zip(viab, viab[1:]):
        assert b < a


def test_at_optimum_viability_barely_changes():
    """Isolate temperature as the cause: hold the thermal driver AT the optimum and
    viability barely moves over the same run (at 37 °C the thermal-death D-value is
    ~10 h, so the loss over 24 min is small) — in stark contrast to the 45 °C run."""
    rows = _run_trajectory(overrides={("environment", "thermal"): TEMP_OPT})
    viab = [float(r["viability"]) for r in rows]
    assert viab[-1] > 0.9                            # stays essentially fully viable
    assert viab[0] - viab[-1] < 0.1                  # only a small decline at optimum


def test_hotter_kills_faster_than_optimum():
    """Directly contrast the two temperatures: after the run, viability at 45 °C is far
    below viability at the optimum — the temperature driver causes the decline."""
    hot = [float(r["viability"]) for r in _run_trajectory()][-1]
    opt = [float(r["viability"]) for r in
           _run_trajectory(overrides={("environment", "thermal"): TEMP_OPT})][-1]
    assert hot < opt
    assert opt - hot > 0.5
