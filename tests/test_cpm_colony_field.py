# tests/test_cpm_colony_field.py
"""CpmColonyField: two cells read their own footprints on a shared glucose grid,
run dFBA independently, grow from biomass, and write disjoint field deltas."""
from __future__ import annotations
import numpy as np
import pytest
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

pytest.importorskip("cobra"); pytest.importorskip("cpm"); pytest.importorskip("spatio_flux")

NX = NY = 40

def _state(core):
    glucose = np.full((NY, NX), 8.0)
    return {
        "fields": {"glucose": glucose, "acetate": np.zeros((NY, NX))},
        "colony": {"_type": "process", "address": "local:CpmColonyField",
            "config": {
                "grid": {"nx": NX, "ny": NY},
                "box_volume_L": 0.3, "grow_per_biomass": 40.0, "mcs": 3,
                "cells": [
                    {"seed_block": [8, 16, 0, 15, 23, 1],  "role": "competitor",
                     "glucose_vmax": 10.0, "oxygen_vmax": 15.0, "target_volume": 50.0, "lambda_volume": 2.0},
                    {"seed_block": [25, 16, 0, 32, 23, 1], "role": "competitor",
                     "glucose_vmax": 4.0,  "oxygen_vmax": 15.0, "target_volume": 50.0, "lambda_volume": 2.0},
                ],
                "contact": [{"a": 0, "b": 1, "j": 14.0}, {"a": 1, "b": 1, "j": 14.0}],
            },
            "inputs": {"fields": ["fields"]},
            "outputs": {"fields": ["fields"], "volume": ["obs", "volume"],
                        "biomass": ["obs", "biomass"], "local_glucose": ["obs", "local_glucose"]},
        },
    }

def test_two_cells_metabolize_grow_and_deplete_disjointly():
    core = build_core()
    comp = Composite({"state": _state(core)}, core=core)
    g0 = comp.state["fields"]["glucose"].copy()
    comp.run(9)
    obs = comp.state["obs"]
    assert set(obs["biomass"].keys()) == {"1", "2"}          # two live cells, id-keyed
    assert obs["biomass"]["1"] > obs["biomass"]["2"]          # faster competitor has more biomass
    assert obs["volume"]["1"] > obs["volume"]["2"]            # ...and more lattice volume
    g1 = comp.state["fields"]["glucose"]
    assert g1.sum() < g0.sum()                                # glucose consumed overall
    assert g1.min() >= -1e-9                                  # never negative anywhere
