# tests/test_cellular_interface_spatial.py
"""The spatial cellular-interface demonstration: the UNCHANGED CellularInterfaceHandler
(local:CellularInterfaceHandler, the abstract fig03b cellular interface) composed with a
real 2D spatio-flux DiffusionAdvection chemical field via a small field-point adapter
(local:FieldPointCoupling). Same interface contract as the lumped fig04 composites --
only the process behind the chemical port has changed, now spatial.

Asserts the two behaviors that make the coupling real:
  * niche construction -- the chemical field DEPLETES at the cell's footprint (the
    interface's net uptake flux is written back into the field where the cell feeds);
  * spatial determination -- the concentration the interface SENSES (chemical_ext)
    reflects the LOCAL field, so a cell on the low side of the gradient senses less
    (and grows less) than one on the high side; it is not a fixed constant.

Skipped when the optional ``spatio_flux`` dependency is absent (no cobra here -- the
handler's chemistry is a lumped Monod law, not an FBA model)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from process_bigraph import Composite

from meta_modelers_guide.core import build_core

pytest.importorskip("spatio_flux")  # composes DiffusionAdvection; absent from base CI

COMP = (
    Path(__file__).resolve().parent.parent
    / "meta_modelers_guide" / "composites" / "cellular-interface-spatial.composite.json"
)


def _footprint(cx, cy, radius, n):
    yy, xx = np.mgrid[0:n, 0:n]
    return ((xx - cx) ** 2 + (yy - cy) ** 2) <= radius * radius


def _spec():
    return json.loads(COMP.read_text())


def _run(spec, steps=20):
    core = build_core()
    comp = Composite({"state": spec["state"]}, core=core)
    return comp


def test_builds_and_depletes_field_at_footprint():
    """The composite builds and runs; the field depletes at the cell's footprint
    (niche construction) while the interface itself runs unchanged and grows."""
    spec = _spec()
    cfg = spec["state"]["couple"]["config"]
    n, cx, cy, r = int(cfg["nx"]), int(cfg["cx"]), int(cfg["cy"]), float(cfg["radius"])
    fp = _footprint(cx, cy, r, n)

    comp = _run(spec, steps=20)
    field0 = np.asarray(comp.state["fields"]["chemical"]).copy()
    fp_mean0 = float(field0[fp].mean())
    total0 = float(field0.sum())

    comp.run(20)

    field1 = np.asarray(comp.state["fields"]["chemical"])
    # niche construction: the footprint is depleted relative to its initial value,
    # and the field's total mass drops (net uptake removed real chemical).
    assert float(field1[fp].mean()) < fp_mean0
    assert float(field1.sum()) < total0

    # the UNCHANGED interface actually ran on the field: it sensed chemical, took it
    # up (negative flux), and grew.
    assert float(comp.state["interface"]["chemical"]) < 0.0        # net uptake
    assert float(comp.state["interface"]["growth_rate"]) > 0.0     # Monod growth
    assert float(comp.state["interface"]["shape"]) > 1.0           # accreted volume


def test_sensed_chemical_is_spatially_determined():
    """chemical_ext reflects the LOCAL field, not a fixed constant: a cell placed on
    the low side of the left-low-to-right-high gradient senses less nutrient -- and
    grows less -- than one on the high side. This is the evidence the interface is
    substrate-independent: the same handler, moved in space, senses a different world."""

    def sensed_and_growth(cx):
        spec = _spec()
        spec["state"]["couple"]["config"]["cx"] = cx  # move the footprint along the gradient
        comp = _run(spec)
        comp.run(20)
        return (float(comp.state["environment"]["chemical"]),
                float(comp.state["interface"]["growth_rate"]))

    n = int(_spec()["state"]["couple"]["config"]["nx"])
    low_sensed, low_growth = sensed_and_growth(cx=n // 5)          # low-concentration side
    high_sensed, high_growth = sensed_and_growth(cx=4 * n // 5)    # high-concentration side

    # spatially varying, not a constant: the two placements sense clearly different
    # concentrations, ordered by the gradient.
    assert low_sensed < high_sensed
    assert (high_sensed - low_sensed) > 0.5
    # and the interface's growth follows the sensed field (more nutrient -> faster).
    assert low_growth < high_growth
