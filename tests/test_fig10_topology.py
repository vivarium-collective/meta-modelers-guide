"""Fig 10.2 (biofilm) and 10.3 (evolution) as time-driven place-graph rewrites:
running the composite makes the PLACE GRAPH change over steps — a biofilm that
colonizes then secretes ECM, and a population where a mutant lineage sweeps —
captured as per-step frames the loom run/animate feature plays.

Complements test_fig10_rewrite.py (division) with the other two topology figures.
"""
from __future__ import annotations

from process_bigraph import Composite, gather_emitter_results

from viva_meta_modelers_guide.core import build_core
from viva_meta_modelers_guide.fig10_topology import (
    build_fig10_biofilm, build_fig10_evolution,
)


def _nodes(tree, control):
    """Top-level child keys of a tree[node] frame whose _control == control."""
    if not isinstance(tree, dict):
        return []
    return [k for k, v in tree.items()
            if not k.startswith("_") and isinstance(v, dict) and v.get("_control") == control]


def _frames(build, key, total):
    core = build_core()
    sim = Composite(build, core=core)
    sim.run(total)
    return [r[key] for r in gather_emitter_results(sim)[("emitter",)]]


# ── 10.2 biofilm ────────────────────────────────────────────────────────────
def _biofilm_frames(total=14.0):
    return _frames(build_fig10_biofilm(grow_every=2.0, capacity=5.0), "biofilm", total)


def test_biofilm_starts_as_one_cell():
    frames = _biofilm_frames()
    assert _nodes(frames[0], "cell") == ["cell"]
    assert _nodes(frames[0], "ecm") == []


def test_biofilm_colonizes_to_capacity():
    frames = _biofilm_frames()
    cell_counts = [len(_nodes(f, "cell")) for f in frames]
    assert cell_counts[0] == 1
    assert max(cell_counts) == 5                      # grows to carrying capacity
    assert cell_counts == sorted(cell_counts)         # monotonic — cells only added


def test_biofilm_secretes_ecm_after_maturing():
    frames = _biofilm_frames()
    # ECM only appears once the community is full (5 cells), never before.
    for f in frames:
        if _nodes(f, "ecm"):
            assert len(_nodes(f, "cell")) == 5
    assert max(len(_nodes(f, "ecm")) for f in frames) >= 1


# ── 10.3 evolution ──────────────────────────────────────────────────────────
def _evolution_frames(total=16.0):
    return _frames(build_fig10_evolution(generation=2.0, mutate_at=4.0,
                                         founders=3.0, capacity=6.0), "population", total)


def test_evolution_starts_as_one_wildtype():
    frames = _evolution_frames()
    assert _nodes(frames[0], "organism") == ["organism"]
    assert _nodes(frames[0], "mutant") == []


def test_evolution_mutant_arises_then_sweeps():
    frames = _evolution_frames()
    # A mutant appears at some point...
    assert any(_nodes(f, "mutant") for f in frames), "no mutant ever arose"
    # ...and by the end the mutant lineage has replaced the wildtype (selection).
    last = frames[-1]
    assert len(_nodes(last, "mutant")) >= 2
    assert len(_nodes(last, "organism")) == 0


def test_evolution_total_population_bounded():
    frames = _evolution_frames()
    totals = [len(_nodes(f, "organism")) + len(_nodes(f, "mutant")) for f in frames]
    assert max(totals) <= 6                            # never exceeds capacity
