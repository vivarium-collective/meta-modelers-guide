#!/usr/bin/env python
"""Generate the evolution live composite's three snapshots from the run.

Fig 11b's evolution is modelled as natural selection under a SHIFTING environment,
a genuine runtime place-graph rewrite (meta_modelers_guide.fig11_topology.
build_fig11_population_evolution): a `population` starts with a single founder
`cell`; on running, the environment's `selection_optimum` drifts, selection
re-scores each cell's replication rate by trait↔optimum fit, and the fitter cells
reproduce — daughter cells are ADDED with the parent's trait ± Gaussian mutation.
The population grows to capacity, then turns over (Moran birth–death) so the trait
cloud keeps tracking the moving optimum.

This writes three snapshots — the emitted frames of the run, not hand-authored:
  fig11-evo-1-founder      t=0     a single founder cell; optimum at 0
  fig11-evo-2-growing      t=mid   the population has grown; trait cloud forming
  fig11-evo-3-adapted      t=end   full population; the trait cloud has tracked
                                   the drifted optimum (adaptation to a moving target)

The live, steppable composite itself is meta_modelers_guide/composites/
fig11-evolution.composite.json (play it forward in the loom run/animate feature).

    python scripts/build_fig11_evolution_snapshots.py
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.fig11_topology import build_fig11_population_evolution

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "meta_modelers_guide" / "composites"

N = 18  # run length (matches the live composite's default_n_steps)

# Keep these scalar leaves in the snapshots (the trait cloud + the moving target);
# drop the rest (replication_rate / resource) so the frames read cleanly.
KEEP_LEAVES = {"trait", "selection_optimum"}

# stage stem -> (emitted frame index, panel title, description tail)
# Two compact snapshots — t=0 and a few instances later — so the pair packs
# tightly beside the Fig 11a illustration.
STAGES = {
    "fig11-evo-1-founder": (
        0, "A single founder",
        "t=0 — one founder cell in the population; the environment's selection "
        "optimum sits at the founder's trait. No variation yet."),
    "fig11-evo-2-growing": (
        2, "A few generations later",
        "t=later — the founder's fitter descendants have reproduced (daughter cells "
        "added to the population) with mutated traits; a trait cloud has formed and "
        "the environment's optimum has begun to drift — selection, mutation and "
        "reproduction, a few generations in."),
}


def _evo_snapshot(node: dict) -> dict:
    """Keep the place-graph NODES (those carrying a _control) plus only the
    KEEP_LEAVES scalars (trait / selection_optimum), so a snapshot renders as a
    compact topology tree with just the evolving quantity, not every store."""
    out = {"_control": node["_control"]}
    contents = node.get("contents")
    if isinstance(contents, dict):
        kept: dict = {}
        for k, v in contents.items():
            if isinstance(v, dict) and v.get("_control"):
                kept[k] = _evo_snapshot(v)
            elif k in KEEP_LEAVES:
                kept[k] = v
        if kept:
            out["contents"] = kept
    return out


def _tree(frame: dict) -> dict:
    tree = {"_type": "tree[node]"}
    for k, v in frame.items():
        if not k.startswith("_") and isinstance(v, dict) and v.get("_control"):
            tree[k] = _evo_snapshot(v)
    return tree


def main() -> None:
    core = build_core()
    sim = Composite({"state": build_fig11_population_evolution(interval=1.0)["state"]}, core=core)
    sim.run(N)
    results = gather_emitter_results(sim)[("emitter",)]
    pops = [r["population"] for r in results]
    envs = [r["environment"] for r in results]

    for stem, (idx, title, tail) in STAGES.items():
        spec = {
            "name": f"Fig 11b evolution — {title}",
            "description": (
                f"Fig 11b, evolution snapshot: {tail} Auto-generated from the "
                f"fig11-evolution simulation (scripts/build_fig11_evolution_snapshots.py); "
                f"one of three sequential frames of the running place-graph rewrite."),
            "state": {
                "population": _tree(pops[idx]),
                "environment": _tree(envs[idx]),
            },
        }
        (COMPOSITES / f"{stem}.composite.json").write_text(json.dumps(spec, indent=2) + "\n")
        n_cells = sum(1 for k, v in spec["state"]["population"].items()
                      if not k.startswith("_") and isinstance(v, dict) and v.get("_control") == "cell")
        print(f"wrote {stem}.composite.json  (cells: {n_cells})")


if __name__ == "__main__":
    main()
