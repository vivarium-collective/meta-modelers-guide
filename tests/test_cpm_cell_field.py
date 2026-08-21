# tests/test_cpm_cell_field.py
"""CpmCellField: a CPM cell that reads a shared nutrient grid at its footprint, runs
dFBA there (uptake→biomass, secretes acetate), grows from biomass, and writes its
uptake/secretion back to the field as a delta."""
from __future__ import annotations
import numpy as np
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

NX = NY = 40

def _state(core):
    glucose = np.full((NY, NX), 10.0)
    acetate = np.zeros((NY, NX))
    return {
        "fields": {"glucose": glucose, "acetate": acetate},
        "cell": {
            "_type": "process",
            "address": "local:CpmCellField",
            "config": {"nx": NX, "ny": NY, "seed_block": [17, 17, 0, 24, 24, 1],
                       "mcs_per_update": 8, "biomass0": 0.1,
                       "grow_per_biomass": 300.0, "box_volume_L": 1e-6},
            "inputs": {"fields": ["fields"]},
            "outputs": {"fields": ["fields"], "volume": ["obs", "volume"],
                        "position": ["obs", "position"], "local_nutrient": ["obs", "local_nutrient"],
                        "biomass": ["obs", "biomass"], "acetate_secreted": ["obs", "acetate_secreted"]},
        },
        "obs": {"volume": 0.0, "position": [0.0, 0.0], "local_nutrient": 0.0,
                "biomass": 0.0, "acetate_secreted": 0.0},
    }

def test_cell_metabolizes_grows_and_reshapes_field():
    core = build_core()
    comp = Composite({"state": _state(core)}, core=core)
    g0 = float(comp.state["fields"]["glucose"].mean())
    comp.run(12)
    obs = comp.state["obs"]
    assert obs["biomass"] > 0.1                              # grew biomass via dFBA
    assert obs["volume"] > 40.0                              # CPM cell grew
    assert float(comp.state["fields"]["glucose"].mean()) < g0  # depleted glucose locally
    assert float(comp.state["fields"]["acetate"].sum()) > 0.0  # secreted byproduct
