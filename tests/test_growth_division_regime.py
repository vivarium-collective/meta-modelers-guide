# tests/test_growth_division_regime.py
"""The growth-and-division regime is legible: the population steps up (n_cells 1->2->4->8...)
as cells grow past the volume threshold and divide, per-cell volume sawtoothing."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from process_bigraph import Composite

from meta_modelers_guide.core import build_core

pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")
pytest.importorskip("cobra")

COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"


def test_population_steps_up_by_division():
    core = build_core()
    state = json.loads((COMPOSITES / "growth-division-spatial.composite.json").read_text())["state"]
    comp = Composite({"state": state}, core=core)

    ns = []
    all_vols = []
    for _ in range(12):
        comp.run(3)
        ns.append(comp.state["obs"]["n_cells"])
        all_vols.append(dict(comp.state["obs"]["volume"]))

    assert ns[0] <= 2  # starts as ~1 cell
    assert max(ns) >= 4  # reaches at least 2 generations (4 cells)
    assert ns == sorted(ns)  # monotonic non-decreasing staircase: division only adds cells

    # bounded cell sizes throughout the run: no runaway single cell, no zero-volume phantom daughters
    for vols in all_vols:
        assert all(8 < v < 200 for v in vols.values())


def test_division_desynchronizes_from_lockstep_powers_of_two():
    """§Growth and division (paper): daughters "remain coupled through shared
    environmental state, so their interfaces are not independent ... enabling
    both coordination and divergence." Sibling cells sharing one glucose field
    grow at different local rates as the colony crowds (a fed-rim cell
    out-competes one boxed into a depleting interior), so division timing
    desynchronizes: the n_cells staircase departs from clean powers of two
    (1,2,4,8,16,32,...) rather than staying in lockstep -- this is the first
    emergent multicellular heterogeneity in the investigation, not a nuisance
    survived."""
    core = build_core()
    state = json.loads((COMPOSITES / "growth-division-spatial.composite.json").read_text())["state"]
    comp = Composite({"state": state}, core=core)

    ns = []
    for _ in range(12):
        comp.run(3)
        ns.append(comp.state["obs"]["n_cells"])

    powers_of_two = {1.0, 2.0, 4.0, 8.0, 16.0, 32.0}
    non_lockstep = [n for n in ns if n not in powers_of_two]
    assert non_lockstep, (
        f"expected the staircase {ns} to reach a non-power-of-two intermediate "
        "once sibling division timing diverges")
    assert ns == sorted(ns)  # divergence still only adds cells; never loses one

    # By the final sampled tick, cells at several different generations coexist
    # in the same colony -- direct evidence siblings are not dividing in lockstep.
    gens = comp.state["obs"]["generation"]
    assert len(set(gens.values())) >= 3


def test_lineage_compounds_into_a_multigeneration_tree():
    """max_generation/generation/lineage (Phase 1) turn the population count into
    an actual genealogy: per Fig 10a,b ("daughter systems ... inherit"), the tree
    is the object, not just the count. Every live cell's generation traces back
    to the founder through the process's own lineage bookkeeping (built from
    divide_cells' own return value, never scripted)."""
    core = build_core()
    state = json.loads((COMPOSITES / "growth-division-spatial.composite.json").read_text())["state"]
    comp = Composite({"state": state}, core=core)

    for _ in range(12):
        comp.run(3)

    max_gen = comp.state["obs"]["max_generation"]
    assert max_gen >= 3.0  # the lineage compounds several generations deep

    gens = comp.state["obs"]["generation"]
    volumes = comp.state["obs"]["volume"]
    assert set(gens.keys()) == set(volumes.keys())  # every live cell has a generation
    assert gens[str(1)] == 0.0  # the founder's own generation never changes

    proc = comp.state["cell"]["instance"]
    # every non-founder id traces back to the founder through recorded parent ids
    for daughter_id, parent_id in proc.lineage.items():
        assert parent_id in proc.generation
        assert proc.generation[daughter_id] == proc.generation[parent_id] + 1
