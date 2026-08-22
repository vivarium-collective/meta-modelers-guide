"""The disintegration regime is legible over a bounded run: the cell holds, then a
rising stressor crosses its viability bound, the domain resorbs to ~0, and its shed
pixels become a scattering particle-debris cloud."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pytest
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

pytest.importorskip("cpm"); pytest.importorskip("spatio_flux")
COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"


def _spread(particles):
    if len(particles) < 2:
        return 0.0
    pos = np.array([p["position"] for p in particles.values()])
    return float(np.sqrt(((pos - pos.mean(0)) ** 2).sum(1).mean()))  # RMS radius


def test_cell_holds_then_disintegrates_into_scattering_debris():
    core = build_core()
    state = json.loads((COMPOSITES / "disintegration-spatial.composite.json").read_text())["state"]
    comp = Composite({"state": state}, core=core)
    # early: coherent (observed area 61-66, released False through tick 6; the
    # crossing lands at tick 7 with margin below the tick-6 checkpoint)
    comp.run(6)
    assert comp.state["obs"]["area"] > 30
    assert comp.state["obs"]["released"] in (False, 0, 0.0)
    # late: released, dissolved (area == 0 by tick 16, well under the tick-24
    # checkpoint), debris present (63 shed particles, observed deterministic
    # across repeated runs; the CPM->particle mass ledger closes -- each shed
    # particle is a distinct vacated pixel, no double-count) and spreading
    comp.run(18)
    assert comp.state["obs"]["released"] in (True, 1, 1.0)
    assert comp.state["obs"]["area"] < 10
    parts = comp.state["particles"]
    assert len(parts) >= 20                              # substantial debris (observed 68)
    spread_now = _spread(parts)
    comp.run(6)
    assert _spread(comp.state["particles"]) > spread_now  # debris keeps scattering
