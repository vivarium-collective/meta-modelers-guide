"""Two disjoint footprint deltas summed into one shared map[array] fields store
conserve mass — the additive-writer assumption the colony process relies on."""
from __future__ import annotations
import numpy as np
import pytest
from process_bigraph import Composite, Process
from meta_modelers_guide.core import build_core

pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")

NX = NY = 20


class _TwoWriter(Process):
    """Removes 1.0 glucose from each of two disjoint single-pixel footprints per tick."""
    config_schema = {}

    def inputs(self):
        return {"fields": "map[array]"}

    def outputs(self):
        return {"fields": "map[array]"}

    def update(self, state, interval):
        d = np.zeros((NY, NX))
        d[5, 5] = -1.0      # cell-1 pixel
        d[5, 15] = -1.0     # cell-2 pixel (disjoint)
        return {"fields": {"glucose": d}}


def test_two_disjoint_writers_sum_and_conserve():
    core = build_core()
    # `register_process` is not the real core API — process_bigraph's Core exposes
    # `register_link(name, cls)` (see meta_modelers_guide/core.py's own use of it
    # to register this workspace's Process classes into the link registry).
    core.register_link("_TwoWriter", _TwoWriter)
    field = np.full((NY, NX), 10.0)
    state = {
        "fields": {"glucose": field},
        "w": {"_type": "process", "address": "local:_TwoWriter", "config": {},
              "inputs": {"fields": ["fields"]}, "outputs": {"fields": ["fields"]}},
    }
    comp = Composite({"state": state}, core=core)
    before = float(np.sum(comp.state["fields"]["glucose"]))
    comp.run(3)
    g = comp.state["fields"]["glucose"]
    assert g[5, 5] == pytest.approx(7.0)      # 10 - 3*1
    assert g[5, 15] == pytest.approx(7.0)     # both writers applied, independently
    assert float(np.sum(g)) == pytest.approx(before - 6.0)  # 2 pixels * 3 ticks
