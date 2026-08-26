# tests/test_cellular_interface_substitutability.py
"""Interface-realization substitutability -- the same thesis, one level up.

`tests/test_substitutability.py` measures substitutability at the *metabolism*
level (dFBA vs Michaelis-Menten behind the `CpmCellField` ports). This test
measures it at the most abstract level the investigation has: the cellular
*interface contract* of Fig 4b itself.

The fig03b executable composite installs ONE handler (`CellularInterfaceHandler`:
first-order uptake + independent Monod growth + Arrhenius thermal death) behind
its typed `cell` ports. Here a SECOND, independent handler
(`CooperativeCellularInterfaceHandler`: a saturable Michaelis-Menten membrane
carrier for uptake + an independent cooperative Moser/Hill (n>1) growth law + Q10
thermal death) is installed behind the SAME ports. We assert:

  1. the two handlers expose BYTE-IDENTICAL `inputs`/`outputs` (the contract);
  2. SWEPT ACROSS THE INTERFACE'S OPERATING RANGE of chemical supply
     (chem in [0.2, 2.5]), the instantaneous interface responses -- chemical flux
     and growth_rate -- agree within tolerance at EVERY sampled concentration; and
  3. driven over a RAMP through that whole range, the integrated interface
     observables (shape, objective, viability) agree within tolerance across the
     whole trajectory.

This is the crux of an honest substitutability claim: the two mechanisms are
genuinely DIFFERENT functional forms (saturable carrier vs first-order line;
cooperative sigmoid vs Monod hyperbola), so they diverge by a real, non-zero
amount -- but that divergence stays under tolerance across the operating range,
not merely at one tuned point. Two independent internal organizations, one
coarse-grained cellular-interface relation.

The comparison is done at the HANDLER level (each handler's `update` is called
across the concentration range), so it needs neither cobra nor spatio_flux; the
handlers run on the base process-bigraph runtime.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from process_bigraph import Composite, allocate_core

from meta_modelers_guide.core import build_core
from meta_modelers_guide.handlers_fig03b import (
    CellularInterfaceHandler,
    CooperativeCellularInterfaceHandler,
)

COMP_DIR = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
COMP_MONOD = COMP_DIR / "fig03b-executable.composite.json"
COMP_COOP = COMP_DIR / "fig03b-executable-alt.composite.json"

# The interface's operating range of chemical supply, and the constant thermal
# environment the fig03b composites hold (37 degC optimum).
CHEM_LO, CHEM_HI = 0.2, 2.5
SWEEP = [round(CHEM_LO + i * 0.2, 3) for i in range(int((CHEM_HI - CHEM_LO) / 0.2) + 1)]
TEMP = 37.0

# Honest tolerance: the two mechanisms are different functional forms, so a
# non-zero divergence is EXPECTED. Measured max across the range is ~10.5%
# (dominated by cooperative-Moser vs Monod growth); a 15% band leaves headroom.
TOL = 0.15


def _fresh(cls):
    return cls({}, core=allocate_core())


def _drive(handler, chem, temp=TEMP):
    """One interface response to a chemical/thermal input. On a FRESH handler the
    set-delta equals the value, so returned `chemical`/`growth_rate` are the actual
    instantaneous flux and growth-rate the interface exposes at this input."""
    return handler.update(
        {"chemical_ext": chem, "mechanical_ext": 0.0, "electrical_ext": 0.0, "thermal_ext": temp},
        1.0,
    )


def test_handlers_expose_identical_ports():
    """Law-2 preservation, made checkable: the two handlers realizing the cellular
    interface declare byte-identical port contracts. A diff of the two port dicts
    is empty -- same externally observable signature, before a single tick runs."""
    core = allocate_core()
    monod = CellularInterfaceHandler({}, core=core)
    coop = CooperativeCellularInterfaceHandler({}, core=core)
    assert monod.inputs() == coop.inputs(), (
        f"input ports diverge: {monod.inputs()} vs {coop.inputs()}")
    assert monod.outputs() == coop.outputs(), (
        f"output ports diverge: {monod.outputs()} vs {coop.outputs()}")


def test_instantaneous_response_agrees_across_concentration_sweep():
    """Sweep chemical_ext across the WHOLE operating range [0.2, 2.5] and compare
    the instantaneous interface responses of the two mechanisms at every point. The
    two boxes are genuinely different (saturable carrier vs first-order line;
    cooperative sigmoid vs Monod hyperbola), so they diverge by a real amount at
    every concentration -- but the max relative divergence over the whole sweep
    stays under tolerance. This is agreement ACROSS THE RANGE, not at one point."""
    worst = {"chemical": 0.0, "growth_rate": 0.0}
    worst_at = {"chemical": None, "growth_rate": None}
    for chem in SWEEP:
        dm = _drive(_fresh(CellularInterfaceHandler), chem)
        dc = _drive(_fresh(CooperativeCellularInterfaceHandler), chem)
        for key in ("chemical", "growth_rate"):
            a, b = dm[key], dc[key]
            if abs(a) > 1e-9:
                rel = abs(a - b) / abs(a)
                if rel > worst[key]:
                    worst[key], worst_at[key] = rel, chem
        # both mechanisms stay in the same interface regime at every concentration
        assert dm["chemical"] < 0 and dc["chemical"] < 0      # net uptake
        assert dm["growth_rate"] > 0 and dc["growth_rate"] > 0  # positive growth

    for key in ("chemical", "growth_rate"):
        assert worst[key] < TOL, (
            f"instantaneous interface response {key!r} diverges {worst[key]:.1%} "
            f"at chem={worst_at[key]} across the sweep -- exceeds tolerance {TOL:.0%}")


def test_integrated_observables_agree_under_ramp():
    """Drive both handlers over the SAME ramp through the whole operating range
    (chem 0.2 -> 2.5) and compare the integrated interface observables -- shape and
    the objective (which accumulate growth) and viability (Q10 vs Arrhenius thermal
    death) -- across the entire trajectory. Max relative divergence over all ticks
    stays under tolerance: the integrated behavior of the two boxes agrees across
    the range, not just their instantaneous responses at one input."""
    n = 24
    ramp = [CHEM_LO + (CHEM_HI - CHEM_LO) * i / (n - 1) for i in range(n)]
    hm = _fresh(CellularInterfaceHandler)
    hc = _fresh(CooperativeCellularInterfaceHandler)
    cum_m = {"shape": 1.0, "objective": 0.0, "viability": 1.0}
    cum_c = {"shape": 1.0, "objective": 0.0, "viability": 1.0}
    worst = {"shape": 0.0, "objective": 0.0, "viability": 0.0}
    for chem in ramp:
        dm = _drive(hm, chem)
        dc = _drive(hc, chem)
        for key in ("shape", "objective", "viability"):
            cum_m[key] += dm[key]
            cum_c[key] += dc[key]
            if abs(cum_m[key]) > 1e-9:
                worst[key] = max(worst[key], abs(cum_m[key] - cum_c[key]) / abs(cum_m[key]))

    # both cells grew and stayed viable over the ramp (same interface regime)
    assert cum_m["shape"] > 1.0 and cum_c["shape"] > 1.0
    assert cum_m["objective"] > 0.0 and cum_c["objective"] > 0.0
    assert cum_m["viability"] > 0.8 and cum_c["viability"] > 0.8

    for key in ("shape", "objective", "viability"):
        assert worst[key] < TOL, (
            f"integrated interface observable {key!r} diverges {worst[key]:.1%} "
            f"over the ramp -- exceeds tolerance {TOL:.0%} "
            f"(Monod final={cum_m[key]:.4g}, Coop final={cum_c[key]:.4g})")


def test_both_composites_build_and_run():
    """Both fig03b executable composites -- the Monod baseline and the cooperative
    alt -- build against the workspace core and run on the base process-bigraph
    runtime (lumped: no cobra, no spatio_flux), producing a growing cell through
    the identical typed interface."""
    for comp_path in (COMP_MONOD, COMP_COOP):
        core = build_core()
        state = json.loads(comp_path.read_text())["state"]
        comp = Composite({"state": state}, core=core)
        comp.run(5)
        iface = comp.state["interface"]
        assert float(iface["chemical"]) < 0.0    # net uptake across the interface
        assert float(iface["growth_rate"]) > 0.0  # the cell grows
        assert float(iface["shape"]) > 1.0        # volume climbs above its seed
