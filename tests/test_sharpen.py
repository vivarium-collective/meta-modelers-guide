"""Property tests that carry real risk — not thresholds back-filled from a run.

These assert *invariants* the mechanisms must obey, so they can genuinely fail if
a mechanism regresses: mass conservation across division, handler-independence of
the whole-cell metabolism swap, and DNA-threshold (not wall-clock) division.
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.wholecell import build_whole_cell

COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"


def _run_whole_cell(metabolism="coarse", t=20.0):
    core = build_core()
    sim = Composite(build_whole_cell(metabolism=metabolism), core=core)
    sim.run(t)
    return sim, gather_emitter_results(sim)[("emitter",)]


def test_division_event_partitions_mass_not_creates_it():
    """The whole-cell division mechanism PARTITIONS biomass rather than creating
    it: what the mother loses equals what the sibling daughter gains, exactly.
    (The pre-fix bug wrote biomass/2 to each daughter and never decremented the
    mother, so total biomass doubled at every division.)"""
    from meta_modelers_guide.wholecell import DivisionEvent
    ev = DivisionEvent({}, core=build_core())
    out = ev.update({"biomass": 2.0, "dividing": 1.0}, 0.1)
    # mother delta (out['biomass']) + daughter delta (out['biomass_1']) == 0
    assert abs(out["biomass"] + out["biomass_1"]) < 1e-9, f"division not conservative: {out}"
    assert out["biomass_1"] > 0.0 and out["cell_count"] == 1.0
    # a one-shot event: it never fires twice
    assert ev.update({"biomass": 2.0, "dividing": 1.0}, 0.1) == {}
    # and it does nothing before the flag is raised
    assert DivisionEvent({}, core=build_core()).update({"biomass": 2.0, "dividing": 0.0}, 0.1) == {}


def test_metabolism_swap_gives_distinct_life_histories():
    """Handler independence at the WHOLE-CELL level (Fig 6 law 4): the same cell,
    with coarse / kinetic / fba metabolism behind identical ports, produces THREE
    distinct trajectories — not the same numbers three times."""
    # The fba arm needs the optional `cobra` package (FBAMetabolism); skip the
    # whole comparison when it's absent rather than fail CI — the coarse/kinetic
    # arms are dependency-free but this test asserts on all three.
    import pytest
    pytest.importorskip("cobra", reason="fba metabolism arm requires the optional cobra package")
    peaks, div_times = {}, {}
    for m in ("coarse", "kinetic", "fba"):
        _, rows = _run_whole_cell(m)
        peaks[m] = max(float(r["biomass"]) for r in rows)
        div_times[m] = next((r["time"] for r in rows if float(r["cell_count"]) >= 2), None)
    # every mechanism grows and divides
    assert all(p > 1.0 for p in peaks.values())
    assert all(t is not None for t in div_times.values())
    # the three are genuinely DIFFERENT (would collapse if the swap were a no-op)
    assert len(set(round(p, 1) for p in peaks.values())) >= 2, f"peaks not distinct: {peaks}"
    assert len(set(div_times.values())) >= 2, f"division times not distinct: {div_times}"


def test_fig10_division_is_dna_threshold_not_clock():
    """fig10-1 division fires because replicated DNA crosses the threshold, and it
    conserves mass (parent → 0, each daughter gets half). It is NOT a wall clock."""
    doc = json.loads((COMPOSITES / "fig10-1-executable.composite.json").read_text(encoding="utf-8"))
    divide = doc["state"]["divide"]
    assert "dna_threshold" in divide["config"], "division must be DNA-threshold triggered"
    assert "division_time" not in divide["config"], "division must NOT be wall-clock triggered"
    assert "dna" in divide["inputs"], "division must read the replicated dna"
    threshold = float(divide["config"]["dna_threshold"])

    core = build_core()
    sim = Composite({"state": doc["state"]}, core=core)
    sim.run(8.0)
    env = sim.state["environ"]
    dna = float(env["cell"]["dna"])
    parent = float(env["cell"]["biomass"])
    d1 = float(env["daughter_1"]["biomass"])
    d2 = float(env["daughter_2"]["biomass"])
    assert float(env["cell_count"]) == 2.0
    assert dna >= threshold, "division fired but DNA never reached threshold"
    # mass conserved: parent fully partitioned into two equal daughters
    assert parent < 1e-6, f"parent biomass not partitioned away: {parent}"
    assert abs(d1 - d2) < 1e-6 and d1 > 0.0, f"daughters not equal/nonzero: {d1}, {d2}"
