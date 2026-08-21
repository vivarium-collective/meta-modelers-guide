"""The two cell-cell regimes are legible over a bounded run: competition => divergent
biomass; cross-feeding => both cells viable via an acetate handoff.

Tuned constants and observed metrics (task 4, 20-step run, deterministic potts seed):

  cellcell-compete  (glucose_vmax 10.0 vs 4.0, uniform 3.0 mM glucose)
    biomass  {"1": 237.9, "2": 64.5}   -> ratio 3.69x  (assert > 1.5x)
    volume   {"1": 3511,  "2": 81}     -> winner claims the lattice

  cellcell-crossfeed  (localized glucose depot 20 mM in cols 0-18; secretor O2 cap 5;
                       acetate diffusion 15.0 vs glucose 0.4; seeds x8-16 / x22-30;
                       consumer acetate_vmax 20; grow_per_biomass 30)
    consumer local_glucose  {"2": 0.0}    (< 0.5: it can't touch glucose)
    consumer biomass        {"2": 3.79}   (init 1.25 -> net-grew ~3x on acetate)
    consumer local_acetate  {"2": 1.30}   (> 0: the secretor's plume reached it)

Thresholds below were chosen with margin against these observed values, not at the edge.
"""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

pytest.importorskip("cobra"); pytest.importorskip("cpm"); pytest.importorskip("spatio_flux")
COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"


def obs_initial_biomass():
    # The ACTUAL CpmColonyField init biomass (config default, colony_field.py).
    return 1.25


def _run(name, steps):
    core = build_core()
    state = json.loads((COMPOSITES / f"{name}.composite.json").read_text())["state"]
    comp = Composite({"state": state}, core=core)
    comp.run(steps)
    return comp.state["obs"]


def test_competition_excludes_the_slower_cell():
    obs = _run("cellcell-compete", 20)
    # faster competitor (id 1) ends with materially more biomass AND lattice volume
    assert obs["biomass"]["1"] > 1.5 * obs["biomass"]["2"]
    assert obs["volume"]["1"] > obs["volume"]["2"]


def test_crossfeeding_keeps_the_consumer_viable():
    obs = _run("cellcell-crossfeed", 20)
    # consumer (id 2) has ~no local glucose yet grows -- it must be living on acetate
    assert obs["local_glucose"]["2"] < 0.5
    assert obs["biomass"]["2"] > obs_initial_biomass()  # net-grew despite no glucose
    assert obs["local_acetate"]["2"] > 0.0              # acetate plume reached it
