# tests/test_cellcell_presaturation.py
"""PRE-SATURATION colony substitutability (peer-review issue M2).

`tests/test_cellcell_substitutability.py` compares the dFBA colony
(`cellcell-compete`) against the tuned MM colony (`cellcell-compete-mm`) at 20
ticks, where the colony has grown to ~99.8% of the 60x60 = 3600-px lattice. At
that ceiling every observable agrees within ~6% -- but part of that agreement is
a SATURATION ARTIFACT: two quantities that are pinned near the lattice/field
ceiling at 20 ticks (total CPM volume, and the total acetate plume) coincide
there regardless of how well the surrogate tracks the trajectory that got them
there.

This module measures the SAME dFBA-vs-MM comparison in a NON-saturated regime --
10 ticks, ~50% lattice occupancy, well below the ceiling -- with the MM params
FROZEN at their shipped tuned values (read from the composite, never re-fit). The
result separates the real agreement from the artifact:

  * The GROWTH / COMPETITION observables are genuinely substitutable pre-saturation:
    total biomass ~9%, competition ratio ~1%, total CPM volume ~2%, net glucose
    depletion ~1% -- so the headline competition result is not a ceiling artifact.

  * The ACETATE agreement IS a ceiling artifact. dFBA's acetate plume saturates
    early (~431 units by ~8 ticks and flat thereafter); the MM overflow surrogate
    climbs roughly linearly and only CATCHES UP at the saturated 20-tick endpoint
    (~0.2% apart). Pre-saturation at 10 ticks the MM plume is barely half-built and
    diverges from dFBA by ~68%. The tuned mm_overflow matched the saturated
    endpoint, not the trajectory.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest
from process_bigraph import Composite

from meta_modelers_guide.core import build_core

pytest.importorskip("cpm")           # the CPM engine (absent from base CI)
pytest.importorskip("spatio_flux")   # the diffusion-advection field framework

COMP_DIR = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
COMP_DFBA = COMP_DIR / "cellcell-compete.composite.json"
COMP_MM = COMP_DIR / "cellcell-compete-mm.composite.json"

LATTICE_PX = 60 * 60          # 3600
PRESAT_TICKS = 10            # ~50% occupancy, well below the ~97.5%+ ceiling
SAT_TICKS = 20               # ~99.8% occupancy -- the saturated regime

# Pre-saturation band for the growth/competition observables. Observed worst-case
# is ~9-10% at 10 ticks; a 15% band is a floor above that.
GROWTH_TOL = 0.15


def _state(path):
    return json.loads(path.read_text())["state"]


def _run(state, ticks):
    core = build_core()
    comp = Composite({"state": copy.deepcopy(state)}, core=core)
    glc0 = float(np.asarray(comp.state["fields"]["glucose"]).sum())
    comp.run(ticks)
    obs = comp.state["obs"]
    b1 = float(obs["biomass"]["1"]); b2 = float(obs["biomass"]["2"])
    v1 = float(obs["volume"]["1"]); v2 = float(obs["volume"]["2"])
    return {
        "biomass_1": b1, "biomass_2": b2, "biomass_total": b1 + b2,
        "compete_ratio": b1 / b2, "volume_total": v1 + v2,
        "acetate": float(np.asarray(comp.state["fields"]["acetate"]).sum()),
        "glc_depleted": glc0 - float(np.asarray(comp.state["fields"]["glucose"]).sum()),
    }


def _rel(a, b):
    return abs(a - b) / abs(a) if a else float("nan")


def _mm_params_are_frozen():
    """Guard: the MM colony keeps its shipped TUNED params, never re-fit to the
    pre-saturation regime (that would defeat the test)."""
    cfg = _state(COMP_MM)["colony"]["config"]
    assert cfg["mechanism"] == "mm"
    assert cfg["mm_yield"] == 0.075 and cfg["mm_overflow"] == 0.034


def test_mm_colony_params_frozen_at_tuned_values():
    _mm_params_are_frozen()


def test_presaturation_growth_observables_substitutable():
    """PRE-SATURATION (10 ticks, ~50% occupancy), MM params frozen: the growth and
    competition observables genuinely agree -- total biomass ~9%, competition ratio
    ~1%, total CPM volume ~2%, net glucose depletion ~1%. The headline competition
    result is substitutable below the saturation ceiling, not only at it."""
    pytest.importorskip("cobra")  # dFBA baseline needs cobra; compare only if present
    _mm_params_are_frozen()
    dfba = _run(_state(COMP_DFBA), PRESAT_TICKS)
    mm = _run(_state(COMP_MM), PRESAT_TICKS)

    # sanity: we really are pre-saturation, not at the ceiling
    occ = dfba["volume_total"] / LATTICE_PX
    assert occ < 0.6, f"expected pre-saturation occupancy, got {occ:.0%}"

    # competition direction preserved by both mechanisms
    assert dfba["biomass_1"] > dfba["biomass_2"]
    assert mm["biomass_1"] > mm["biomass_2"]

    for key in ("biomass_1", "biomass_2", "biomass_total", "compete_ratio",
                "volume_total", "glc_depleted"):
        rel = _rel(dfba[key], mm[key])
        assert rel < GROWTH_TOL, (
            f"PRE-SATURATION ({PRESAT_TICKS} ticks) observable {key!r} diverges {rel:.0%} "
            f"(dFBA={dfba[key]:.4g}, MM={mm[key]:.4g}) -- exceeds band {GROWTH_TOL:.0%}")


def test_acetate_match_is_a_saturation_artifact():
    """The honest finding: the ~0.2% colony acetate agreement is a SATURATION
    ARTIFACT. At the saturated 20-tick endpoint dFBA and MM acetate coincide
    (< 5% apart), but pre-saturation at 10 ticks (~50% occupancy) the MM overflow
    surrogate is barely half-built and diverges from dFBA by > 40% -- the tuned
    mm_overflow matched the endpoint, not the trajectory."""
    pytest.importorskip("cobra")
    _mm_params_are_frozen()

    dfba_sat = _run(_state(COMP_DFBA), SAT_TICKS)
    mm_sat = _run(_state(COMP_MM), SAT_TICKS)
    dfba_pre = _run(_state(COMP_DFBA), PRESAT_TICKS)
    mm_pre = _run(_state(COMP_MM), PRESAT_TICKS)

    rel_sat = _rel(dfba_sat["acetate"], mm_sat["acetate"])
    rel_pre = _rel(dfba_pre["acetate"], mm_pre["acetate"])

    # at saturation the acetate plumes coincide ...
    assert rel_sat < 0.05, f"expected saturated acetate agreement, got {rel_sat:.0%}"
    # ... but pre-saturation they diverge badly: the agreement was an artifact
    assert rel_pre > 0.40, (
        f"expected pre-saturation acetate divergence (the artifact), got {rel_pre:.0%} "
        f"(dFBA={dfba_pre['acetate']:.4g}, MM={mm_pre['acetate']:.4g})")
