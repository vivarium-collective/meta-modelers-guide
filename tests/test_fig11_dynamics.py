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
      gap: adaptation to the drifting environment.

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


def _trajectory():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    rows = gather_emitter_results(sim)[("emitter",)]
    return [(len(_cells(r["population"])), _mean_trait(r["population"]), _optimum(r["environment"]))
            for r in rows]


def test_population_grows_to_capacity():
    traj = _trajectory()
    sizes = [c[0] for c in traj]
    assert sizes[0] == 1                       # a single founder cell
    assert sizes[-1] > sizes[0]                 # the lineage divides and grows
    assert sizes[-1] >= 12                      # reaches carrying capacity (default 12)


def test_selection_optimum_drifts():
    traj = _trajectory()
    optimum = [c[2] for c in traj]
    assert optimum[-1] > optimum[0]             # a moving target over the run


def test_mean_trait_tracks_the_drifting_optimum():
    traj = _trajectory()
    mean_trait = [c[1] for c in traj]
    optimum = [c[2] for c in traj]
    gap0 = abs(mean_trait[0] - optimum[0])
    gapN = abs(mean_trait[-1] - optimum[-1])
    assert gap0 > 0.5                            # starts far below the optimum (trait 0 vs ~1)
    assert gapN < gap0                           # the cloud closes on the moving optimum
    assert gapN < 0.4                            # ends sitting close to the drifting target
