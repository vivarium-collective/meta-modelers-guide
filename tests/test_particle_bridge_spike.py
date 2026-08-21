# tests/test_particle_bridge_spike.py
"""The CPM->particle bridge primitive: a process emitting particles via the map
`_add` sentinel into a shared map[particle] store, moved by a stock BrownianMovement,
makes particles appear then scatter — verified in one real Composite."""
from __future__ import annotations
import numpy as np
import pytest
from process_bigraph import Composite, Process
from meta_modelers_guide.core import build_core

pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")

NX = NY = 20
BOUNDS = (20.0, 20.0)

class _DebrisEmitter(Process):
    """Emits 3 particles on the first update tick, then nothing."""
    config_schema = {}
    def __init__(self, config, core):
        super().__init__(config, core)
        self._done = False
    def inputs(self):  return {}
    def outputs(self): return {"particles": "map[particle]"}
    def update(self, state, interval):
        if self._done:
            return {}                                  # never emit empty _add
        self._done = True
        add = {f"debris_{i}": {"id": f"debris_{i}",
                               "position": (5.0 + i, 5.0), "mass": 1.0} for i in range(3)}
        return {"particles": {"_add": add}}

def test_emit_then_scatter():
    core = build_core()
    core.register_link("_DebrisEmitter", _DebrisEmitter)
    state = {
        "particles": {},
        "emit": {"_type": "process", "address": "local:_DebrisEmitter", "config": {},
                 "outputs": {"particles": ["particles"]}},
        "move": {"_type": "process",
                 "address": "local:!spatio_flux.processes.particles.BrownianMovement",
                 "config": {"bounds": BOUNDS, "n_bins": (NX, NY), "diffusion_rate": 2.0},
                 "inputs": {"particles": ["particles"]}, "outputs": {"particles": ["particles"]}},
    }
    comp = Composite({"state": state}, core=core)
    comp.run(1)
    p1 = {k: tuple(v["position"]) for k, v in comp.state["particles"].items()}
    assert len(p1) == 3                                # emitted
    comp.run(3)
    p2 = {k: tuple(v["position"]) for k, v in comp.state["particles"].items()}
    assert len(p2) == 3                                # still 3
    moved = sum(1 for k in p1 if p2[k] != p1[k])
    assert moved >= 2                                  # scattered
