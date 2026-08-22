# tests/test_flagship_field.py
"""The flagship sense/act loop: over the run the cell depletes local glucose, grows
biomass + volume, secretes acetate into the field, and diffusion spreads it — a real
spatial realization of Fig 5 cell-environment coupling (niche construction).

Skipped when the optional ``cobra`` dependency is absent (CpmCellField requires it,
matching ``tests/test_cpm_cell_field.py``)."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pytest
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

pytest.importorskip("cobra")  # entire module skips without COBRApy
pytest.importorskip("cpm")  # + the spatial frameworks (absent from base CI)
pytest.importorskip("spatio_flux")

COMP = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites" / "single-cell-in-a-field.composite.json"
COMP_O2UNCAPPED = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites" / "single-cell-in-a-field-o2uncapped.composite.json"


def _run_acetate(comp_path):
    """Run a flagship-family composite for 20 ticks; return (field-wide acetate, obs)."""
    core = build_core()
    state = json.loads(comp_path.read_text())["state"]
    comp = Composite({"state": state}, core=core)
    comp.run(20)
    return float(np.asarray(comp.state["fields"]["acetate"]).sum()), comp.state["obs"]


def test_flagship_sense_act_loop():
    core = build_core()
    state = json.loads(COMP.read_text())["state"]
    comp = Composite({"state": state}, core=core)
    glc0 = float(np.asarray(comp.state["fields"]["glucose"]).sum())
    comp.run(20)
    obs = comp.state["obs"]
    assert obs["biomass"] > state["cell"]["config"]["biomass0"]   # metabolized
    assert obs["volume"] > 40.0                                    # grew
    assert float(np.asarray(comp.state["fields"]["acetate"]).sum()) > 0.0  # secreted
    assert float(np.asarray(comp.state["fields"]["glucose"]).sum()) < glc0  # consumed net


def test_o2_cap_is_what_forces_acetate_overflow():
    """Foundational mechanism control: the acetate the flagship secretes is *caused by*
    the O2 cap, not an artifact of the coupling. Lifting the oxygen bound
    (single-cell-in-a-field-o2uncapped, oxygen_vmax 2.5 -> 1000) lets unconstrained
    e_coli_core respire fully — pure aerobic respiration is growth-optimal, so EX_ac_e
    sits at 0 — and the cell secretes essentially no acetate, while the capped flagship
    secretes a clearly-positive plume. This turns the study's overflow claim from a code
    assertion into a demonstrated experiment."""
    capped_acetate, capped_obs = _run_acetate(COMP)
    uncapped_acetate, uncapped_obs = _run_acetate(COMP_O2UNCAPPED)

    # Capped flagship: a real, clearly-positive acetate plume.
    assert capped_acetate > 1.0
    # O2-uncapped control: full respiration -> ~0 acetate overflow.
    assert uncapped_acetate < 1e-6
    # And the mechanism, not merely the threshold: the cap makes a decisive difference.
    assert capped_acetate > 100.0 * max(uncapped_acetate, 1e-9)
    # The uncapped cell still metabolizes and grows (it just respires instead of
    # overflowing) — the control isolates the O2 cap, it doesn't break the cell.
    assert uncapped_obs["biomass"] > capped_obs["biomass"]
