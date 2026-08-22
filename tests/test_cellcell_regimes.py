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

  cellcell-crossfeed-knockout  (secretor cell REMOVED -> no acetate produced anywhere;
                       consumer alone, now id "1", same seed/field as cross-feed)
    consumer biomass        {"1": 1.25}   (== seed: fails to grow with no acetate source)
    consumer local_acetate  {"1": 0.0}    (== 0: no secretor, no plume)
    consumer volume         {"1": 35}     (persists on the lattice, just doesn't grow)

Competition viability floor (VIABLE_BIOMASS_FLOOR == the 1.25 seed biomass): a cell below
its seed biomass is in net mass-loss (non-viable trajectory); above it, metabolically viable.
Over the 20-tick compete run the LOSER (id 2) ends at biomass 64.5 -- it GREW ~51.6x from the
1.25 seed and sits far above the floor. It is spatially DISPLACED (volume 81 px vs the winner's
3511 px == 97.5% of the 3600-px lattice), not driven below any viability bound: "competitive
exclusion" here is asymmetric growth toward finite-size saturation, not death of the loser.

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


# A cell seeded at obs_initial_biomass() is viable; one that has fallen BELOW its
# seed biomass is in net mass-loss (a non-viable trajectory). This is the minimal
# viable-biomass floor the study measures the competition loser against.
VIABLE_BIOMASS_FLOOR = 1.25


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


def test_competition_loser_is_displaced_not_excluded():
    """Honest boundary on the competition claim: the LOSER is out-competed spatially
    but stays FAR above the viable-biomass floor -- it is displaced, not driven below
    any viability bound. "Competitive exclusion" here is asymmetric growth toward a
    finite-size saturation endpoint (the winner claims ~97.5% of the lattice), NOT the
    death of the loser. This study couples state (a shared field) but imposes no
    viability CONSTRAINT (no death, no viability bound), so strict exclusion is not
    reached over the run measured -- see the paper's Cell-cell coupling distinction
    that what is coupled is state, not necessarily constraint (paper section
    Cell-cell coupling)."""
    obs = _run("cellcell-compete", 20)
    loser = obs["biomass"]["2"]
    # The loser GREW from its 1.25 seed (to ~64.5) -- it is nowhere near the floor.
    assert loser > VIABLE_BIOMASS_FLOOR      # survives above the viability floor
    assert loser > obs_initial_biomass()     # in fact net-grew; not shrinking to death
    # ... yet it is spatially displaced: it holds a small fragment of the lattice while
    # the winner (id 1) claims the overwhelming majority. Displaced, not excluded.
    assert obs["volume"]["1"] > 10.0 * obs["volume"]["2"]


def test_crossfeeding_knockout_consumer_fails_to_grow():
    """Secretor-knockout NECESSITY control: with the acetate secretor removed from the
    cross-feed composite, no acetate is produced anywhere, and the otherwise-identical
    consumer (now the only cell, id "1") FAILS to grow -- its biomass stays at the 1.25
    seed and its local acetate stays 0.0. This is the genuine negative control closing
    the handoff-necessity argument: the consumer's growth in cellcell-crossfeed is
    caused by the secretor's acetate, not by anything intrinsic to the consumer."""
    obs = _run("cellcell-crossfeed-knockout", 20)
    assert obs["local_acetate"]["1"] == 0.0                 # no secretor -> no plume
    # biomass does NOT climb -- stays at (never exceeds) its seed value
    assert obs["biomass"]["1"] <= obs_initial_biomass() + 1e-6
