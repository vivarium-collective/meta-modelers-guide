"""M7 peer-review controls for the cell-cell coupling study.

M7a -- realistic-diffusivity cross-feed. The flagship cross-feed uses a 37.5x
acetate/glucose diffusion ratio (15.0 vs 0.4), ~20x the physical ~2:1. Re-run at
the PHYSICAL 2:1 ratio (0.8 vs 0.4), the acetate handoff FAILS to complete within
a legible horizon: the consumer's own footprint acetate peaks ~0.21 (vs 1.60 at
37.5x) and its biomass rises only ~2% (1.25 -> ~1.28, vs 1.25 -> 3.79) before it
is competitively displaced off the lattice by the growing secretor around t=20.
Feeding scales monotonically with transport acceleration (consumer biomass gain
+14%/+45%/+102%/+203% at 5x/10x/20x/37.5x), so the flagship's accelerated
transport is load-bearing for the legible handoff at this geometry, not cosmetic.

M7b -- dividing-population competition. Two DIVIDING founder lineages (fast vmax
10 vs slow vmax 4) race for one boundary-supplied glucose pool with a maintenance
cost and a viability floor (biomass < 1.25 -> the cell is removed). The robust
outcome is population-level competitive DOMINANCE of the fast lineage (~9x the
slow lineage's biomass by t=40, all seeds). It is competition-driven, not
intrinsic non-viability: the slow lineage SURVIVES in monoculture under the
identical supply/maintenance/floor (the slowmono control) but is suppressed to a
few cells when the fast lineage preempts the shared glucose (Tilman R*). FULL
exclusion (slow -> 0) occurs at the headline seed by t~56 and in 2/5 seeds of a
robustness sweep, but is NOT robust -- in the other seeds the suppressed slow
lineage persists in spatial refugia. So the earned term is competitive DOMINANCE,
not deterministic competitive exclusion.
"""
from __future__ import annotations
import json
from pathlib import Path

import pytest
from process_bigraph import Composite, gather_emitter_results
from meta_modelers_guide.core import build_core

pytest.importorskip("cobra"); pytest.importorskip("cpm"); pytest.importorskip("spatio_flux")
COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"


def _series(name, steps):
    core = build_core()
    state = json.loads((COMPOSITES / f"{name}.composite.json").read_text())["state"]
    comp = Composite({"state": state}, core=core)
    comp.run(steps)
    return gather_emitter_results(comp)[("emitter",)], comp.state["obs"]


# ----------------------------- M7a -----------------------------------------

def test_crossfeed_realistic_diffusivity_handoff_fails():
    """At the PHYSICAL 2:1 acetate/glucose diffusivity, the cross-feeding handoff
    does NOT feed the consumer within a legible horizon: the consumer's own local
    acetate stays low and its biomass never meaningfully climbs (contrast the 37.5x
    legibility regime, where the same consumer reaches local_acetate 1.60 and
    biomass 3.79). The consumer is competitively displaced before the slow,
    steeply-graded plume can raise its footprint concentration to a feeding level."""
    series, _ = _series("cellcell-crossfeed-realistic", 20)
    peak_biomass = 0.0
    peak_local_ac = 0.0
    for rec in series:
        if rec.get("time") is None:
            continue
        bm = rec.get("biomass", {})
        la = rec.get("local_acetate", {})
        if "2" in bm:
            peak_biomass = max(peak_biomass, bm["2"])
        if "2" in la:
            peak_local_ac = max(peak_local_ac, la["2"])
    # consumer never establishes acetate feeding at the physical diffusivity
    assert peak_local_ac < 0.5    # vs 1.60 at 37.5x
    assert peak_biomass < 1.4     # 1.25 seed; vs 3.79 at 37.5x -- essentially no net growth


# ----------------------------- M7b -----------------------------------------

def test_dividing_competition_fast_lineage_dominates():
    """Robust population-level outcome: the fast-uptake lineage (founder 1)
    competitively DOMINATES the slow lineage (founder 2) -- many-fold more biomass
    and more cells -- over dividing populations with a viability floor."""
    _, obs = _series("cellcell-compete-div", 40)
    # fast lineage holds several-fold the slow lineage's biomass and outnumbers it
    assert obs["biomass_fast"] > 3.0 * obs["biomass_slow"]
    assert obs["n_fast"] > obs["n_slow"]
    # divisions actually happened (population grew well beyond the 2 founders)
    assert obs["n_cells"] > 4.0
    assert obs["max_generation"] >= 1.0


def test_slow_lineage_viable_in_monoculture_control():
    """Competition necessity control: the slow lineage SURVIVES on its own under
    the identical boundary supply / maintenance / viability floor. Its collapse in
    cellcell-compete-div is therefore caused by COMPETITION (the fast lineage
    preempting the shared glucose below the slow lineage's break-even), not by
    intrinsic non-viability at this maintenance/floor."""
    _, obs = _series("cellcell-compete-div-slowmono", 40)
    # NB: the lone slow lineage is seeded first, so it is founder id 1 -- its
    # biomass lands in `biomass_fast`. Assert on the population totals instead.
    assert obs["n_cells"] > 5.0                              # grows & persists alone
    assert (obs["biomass_fast"] + obs["biomass_slow"]) > 5.0  # net-positive standing biomass
