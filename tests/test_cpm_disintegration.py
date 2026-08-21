# tests/test_cpm_disintegration.py
"""CpmDisintegration: a coherent CPM cell holds while the stressor is low, then on
threshold-cross latches `released`, resorbs (area -> 0), and sheds its vacated pixels
as particles into the shared store."""
from __future__ import annotations
import numpy as np
import pytest
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

pytest.importorskip("cpm"); pytest.importorskip("spatio_flux")

NX = NY = 40

def _state(core, stressor_level):
    stressor = np.full((NY, NX), stressor_level)
    return {
        "fields": {"stressor": stressor},
        "particles": {},
        "cell": {"_type": "process", "address": "local:CpmDisintegration",
            "config": {"grid": {"nx": NX, "ny": NY}, "bounds": {"x": NX, "y": NY},
                       "cell": {"seed_block": [16, 16, 0, 24, 24, 1], "target_volume": 64.0,
                                "lambda_volume": 2.0, "temperature": 11.0},
                       "viability_threshold": 0.5, "resorb_per_tick": 6.0,
                       "max_particles_per_tick": 8, "mcs": 3,
                       "contact": [{"a": 0, "b": 1, "j": 14.0}]},
            "inputs": {"fields": ["fields"]},
            "outputs": {"fields": ["fields"], "particles": ["particles"],
                        "area": ["obs", "area"], "released": ["obs", "released"]},
        },
    }

def test_holds_below_threshold():
    core = build_core()
    comp = Composite({"state": _state(core, 0.1)}, core=core)   # stressor below 0.5
    comp.run(12)
    assert comp.state["obs"]["released"] in (False, 0, 0.0)
    assert comp.state["obs"]["area"] > 20                        # cell intact
    assert len(comp.state["particles"]) == 0                     # no debris

def test_releases_and_disintegrates_into_particles():
    core = build_core()
    comp = Composite({"state": _state(core, 0.9)}, core=core)   # stressor above 0.5
    comp.run(20)
    assert comp.state["obs"]["released"] in (True, 1, 1.0)      # latched
    assert comp.state["obs"]["area"] < 10                        # cell dissolved
    assert len(comp.state["particles"]) > 0                      # debris created
