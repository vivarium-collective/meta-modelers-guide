# tests/test_growth_division_regime.py
"""The growth-and-division regime is legible: the population steps up (n_cells 1->2->4->8...)
as cells grow past the volume threshold and divide, per-cell volume sawtoothing."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from process_bigraph import Composite

from meta_modelers_guide.core import build_core

pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")
pytest.importorskip("cobra")

COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"


def test_population_steps_up_by_division():
    core = build_core()
    state = json.loads((COMPOSITES / "growth-division-spatial.composite.json").read_text())["state"]
    comp = Composite({"state": state}, core=core)

    ns = []
    all_vols = []
    for _ in range(12):
        comp.run(3)
        ns.append(comp.state["obs"]["n_cells"])
        all_vols.append(dict(comp.state["obs"]["volume"]))

    assert ns[0] <= 2  # starts as ~1 cell
    assert max(ns) >= 4  # reaches at least 2 generations (4 cells)
    assert ns == sorted(ns)  # monotonic non-decreasing staircase: division only adds cells

    # bounded cell sizes throughout the run: no runaway single cell, no zero-volume phantom daughters
    for vols in all_vols:
        assert all(8 < v < 200 for v in vols.values())
