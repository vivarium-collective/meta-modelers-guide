"""Fig 11 · evolution as a place-graph rewrite, asserted from the trajectory.

The runnable fig11-evolution composite runs a PopulationEvolution process over a
population `tree[node]` and an environment whose `selection_optimum` DRIFTS: the
founder lineage divides (binary fission with heritable mutation), grows to carrying
capacity, and — under Gaussian selection for the moving optimum — its trait cloud
tracks that optimum. This test asserts the figure's principle FROM THE EMITTED
TRAJECTORY:

  (a) the population grows from the lone founder to carrying capacity;
  (b) the selection optimum drifts over the run (a moving target);
  (c) the mean trait — starting far below the optimum — moves toward it, closing the
      gap: adaptation to the drifting environment;
  (d) division is a genuine place-graph rewrite — a dividing cell is REPLACED by two
      fresh daughters (the parent id is gone, two new ids appear), so growth is
      binary fission, not in-place duplication;
  (e) the whole run is deterministic under the pinned seed (seed=1).

The composite is fixed-seed (seed=1), so the trajectory reproduces exactly run to
run and the pinned integers below are true regression pins.

Mirrors the trajectory-driven style of tests/test_fig10_topology.py.
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core

COMPOSITE = (
    Path(__file__).resolve().parent.parent
    / "meta_modelers_guide" / "composites" / "fig11-evolution.composite.json"
)
OPTIMUM0 = 1.0  # composite's optimum0 default (t=0 leaf is still the raw template string)
CAPACITY = 12   # composite's capacity default (node cap)


def _cells(pop: dict):
    return [k for k, v in pop.items()
            if not k.startswith("_") and isinstance(v, dict) and v.get("_control") == "cell"]


def _mean_trait(pop: dict) -> float:
    traits = [float(pop[k]["contents"].get("trait", 0.0)) for k in _cells(pop)]
    return sum(traits) / len(traits) if traits else 0.0


def _optimum(env: dict) -> float:
    niche = next(k for k, v in env.items()
                 if not k.startswith("_") and isinstance(v, dict) and v.get("_control") == "niche")
    raw = env[niche]["contents"].get("selection_optimum", OPTIMUM0)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return OPTIMUM0


def _rows():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def _trajectory():
    """(size, mean_trait, optimum) per emitted tick."""
    return [(len(_cells(r["population"])), _mean_trait(r["population"]), _optimum(r["environment"]))
            for r in _rows()]


def _cell_sets():
    """frozenset of live cell ids per emitted tick — the population's place graph."""
    return [frozenset(_cells(r["population"])) for r in _rows()]


def test_population_grows_to_capacity():
    traj = _trajectory()
    sizes = [c[0] for c in traj]
    assert sizes[0] == 1                        # a single founder cell
    assert sizes[-1] > sizes[0]                 # the lineage divides and grows
    assert sizes[-1] == CAPACITY                # reaches carrying capacity (default 12)
    assert max(sizes) == CAPACITY               # and NEVER exceeds it — death by selection caps it


def test_selection_optimum_drifts():
    traj = _trajectory()
    optimum = [c[2] for c in traj]
    assert optimum[0] == OPTIMUM0               # starts at the niche optimum (1.0), not 0
    assert optimum[-1] > optimum[0]             # a moving target over the run
    # gentle, monotone drift — the optimum only ever moves forward (a directional niche shift)
    assert all(b >= a for a, b in zip(optimum, optimum[1:]))
    assert optimum[-1] == round(OPTIMUM0 + 0.02 * (len(optimum) - 1), 2)  # drift 0.02/gen → 1.80


def test_mean_trait_tracks_the_drifting_optimum():
    traj = _trajectory()
    mean_trait = [c[1] for c in traj]
    optimum = [c[2] for c in traj]
    gap0 = abs(mean_trait[0] - optimum[0])
    gapN = abs(mean_trait[-1] - optimum[-1])
    assert mean_trait[0] == 0.0                  # founder sits at trait 0, far below the optimum
    assert gap0 > 0.5                            # starts far below the optimum (trait 0 vs ~1)
    assert gapN < gap0                           # the cloud closes on the moving optimum
    assert gapN < 0.4                            # ends sitting close to the drifting target
    # and the closing is real motion of the cloud, not the optimum coming to it:
    assert mean_trait[-1] > mean_trait[0] + 1.0  # the mean trait itself climbs by > 1.0


def test_division_is_binary_fission_place_graph_rewrite():
    """A dividing cell is REPLACED by two fresh daughters — the parent id is gone and
    two brand-new ids appear (net +1 cell). Growth is binary fission on the place
    graph, not in-place duplication or an id being reused."""
    sets = _cell_sets()
    assert sets[0] == frozenset({"cell_0"})     # the lone founder

    # First division: the founder cell_0 is consumed and replaced by exactly two daughters.
    first_growth = next(i for i in range(1, len(sets)) if len(sets[i]) > len(sets[i - 1]))
    parents_gone = sets[first_growth - 1] - sets[first_growth]
    daughters_new = sets[first_growth] - sets[first_growth - 1]
    assert "cell_0" not in sets[first_growth]   # the founder does not persist once it divides
    assert parents_gone == frozenset({"cell_0"})
    assert len(daughters_new) == 2              # replaced by TWO daughters

    # Below carrying capacity there are no deaths, so every topology change is fission:
    # each vanished parent is replaced by exactly two fresh daughters (appeared == 2·vanished).
    for prev, cur in zip(sets, sets[1:]):
        if len(prev) < CAPACITY and len(cur) <= CAPACITY:
            vanished = prev - cur
            appeared = cur - prev
            assert len(appeared) == 2 * len(vanished)

    # Ids are never reused: once a cell id leaves the population it never returns
    # (each daughter is a genuinely new node, a fresh place-graph vertex).
    seen: set[str] = set()
    retired: set[str] = set()
    for s in sets:
        assert not (s & retired)                # no retired id ever reappears
        retired |= (seen - s)
        seen |= s


def test_trajectory_is_deterministic():
    """seed=1 is pinned in the composite, so two independent builds emit an identical
    (size, mean_trait, optimum) trajectory — the pinned numbers are true regression pins."""
    assert _trajectory() == _trajectory()
