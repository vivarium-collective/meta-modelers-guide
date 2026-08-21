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

COMP = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "cpm" / "composites" / "single-cell-in-a-field.composite.json"


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
