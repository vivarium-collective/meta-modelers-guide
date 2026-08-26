#!/usr/bin/env python
"""Generate the biofilm-emergence live composite + three snapshots from the run.

Fig 10b's development is modelled as biofilm emergence from FREE MOTILE BACTERIA,
as a genuine runtime place-graph rewrite (meta_modelers_guide.fig10_topology.
build_fig10_biofilm_emergence): the environment starts with a surface and several
free, motile bacteria; on running, they ATTACH and AGGREGATE into a nested
microcolony (losing motility), then the sessile community MATURES by secreting
ECM matrix nodes.

This writes:
  fig10-emergence               the live, steppable rewrite composite (study baseline)
  fig10-biofilm-1-planktonic    t=0            surface + free motile bacteria
  fig10-biofilm-2-microcolony   t=attach       surface + biofilm[cells] (sessile)
  fig10-biofilm-3-mature        t=mature       surface + biofilm[cells + ecm...]

The three snapshots are the emitted frames of the run — not hand-authored — so
the three-panel figure is a faithful time series of biofilm emergence.

    python scripts/build_biofilm_snapshots.py
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.fig10_topology import build_fig10_biofilm_emergence

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "meta_modelers_guide" / "composites"

ATTACH_AT, MATURE_AT, ECM_COUNT, N = 2.0, 4.0, 3.0, 4

# stage stem -> (emitted frame index, panel title, description tail)
STAGES = {
    "fig10-biofilm-1-planktonic": (
        0, "Free motile bacteria",
        "t=0 — dispersed, free-swimming bacteria (motile) as top-level siblings in "
        "the environment, alongside a surface. Nothing is attached yet."),
    "fig10-biofilm-2-microcolony": (
        3, "Attached microcolony",
        "t=attach — the motile bacteria have attached to the surface and aggregated: "
        "they are now children of a single biofilm node (sessile). A genuine "
        "place-graph reorganization — dispersed siblings become a nested community."),
    "fig10-biofilm-3-mature": (
        6, "Mature biofilm",
        "t=mature — the sessile community has secreted extracellular matrix: ecm "
        "(matrix) nodes now sit inside the biofilm, a structured matrix-encased "
        "multicellular community."),
}


def _emergence_state():
    return build_fig10_biofilm_emergence(
        n_bacteria=N, attach_at=ATTACH_AT, mature_at=MATURE_AT,
        ecm_count=ECM_COUNT, interval=1.0)["state"]


def _topology_only(node: dict) -> dict:
    """Keep only the place-graph NODES (those carrying a _control) and drop the
    scalar-value leaves (biomass / motile / matrix), so a snapshot renders as a
    compact topology tree instead of a wide row of value stores — much more
    readable in the composed figure."""
    out = {"_control": node["_control"]}
    contents = node.get("contents")
    if isinstance(contents, dict):
        kids = {k: _topology_only(v) for k, v in contents.items()
                if isinstance(v, dict) and v.get("_control")}
        if kids:
            out["contents"] = kids
    return out


def main() -> None:
    # 1. the live, steppable rewrite composite (study baseline)
    live = {
        "name": "Biofilm Emergence — Live Topology",
        "description": (
            "Fig 10b as a genuine place-graph rewrite: biofilm emergence from free "
            "motile bacteria. The environment starts with a surface and free motile "
            "bacteria; running it makes them attach + aggregate into a nested "
            "microcolony, then mature by secreting ECM. Steppable topology for the "
            "loom run/animate feature."),
        "default_n_steps": 8,
        "requires": {"processes": ["BiofilmEmergence"]},
        "state": _emergence_state(),
    }
    (COMPOSITES / "fig10-emergence.composite.json").write_text(json.dumps(live, indent=2) + "\n")
    print("wrote fig10-emergence.composite.json  (live rewrite)")

    # 2. run it and capture the three stages it actually passes through
    core = build_core()
    sim = Composite({"state": _emergence_state()}, core=core)
    sim.run(7)
    frames = [r["env"] for r in gather_emitter_results(sim)[("emitter",)]]

    for stem, (idx, title, tail) in STAGES.items():
        env = frames[idx]
        colony = {"_type": "tree[node]"}
        for k, v in env.items():
            if not k.startswith("_"):
                colony[k] = _topology_only(v)
        spec = {
            "name": f"Fig 10b biofilm — {title}",
            "description": (
                f"Fig 10b, biofilm-emergence snapshot: {tail} Auto-generated from the "
                f"fig10-emergence simulation (scripts/build_biofilm_snapshots.py); one "
                f"of three sequential frames of the running place-graph rewrite."),
            "state": {"env": colony},
        }
        (COMPOSITES / f"{stem}.composite.json").write_text(json.dumps(spec, indent=2) + "\n")
        top = [k for k in colony if not k.startswith("_")]
        print(f"wrote {stem}.composite.json  (top-level: {', '.join(top)})")


if __name__ == "__main__":
    main()
