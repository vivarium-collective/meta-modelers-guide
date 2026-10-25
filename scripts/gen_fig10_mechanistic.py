#!/usr/bin/env python
"""Generate the fig10-mechanistic composite JSON (N cell positions are data, so
they are generated rather than hand-written).

Six motile cells start on a ring around the box centre. With local adhesion they
aggregate; once a quorum sits in proximity for several consecutive ticks the
biofilm forms (an emergent place-graph rewrite), then ECM binds the community.
Distances are in LATTICE units.

    python scripts/gen_fig10_mechanistic.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "meta_modelers_guide" / "composites" / "fig10-mechanistic.composite.json"

N = 6
CX = CY = 8.0
RING = 4.2


def build():
    xs = {"_type": "map", "_value": "float"}
    ys = {"_type": "map", "_value": "float"}
    colony = {"_type": "tree[node]"}
    for i in range(N):
        a = 2 * math.pi * i / N
        xs[str(i)] = round(CX + RING * math.cos(a), 4)
        ys[str(i)] = round(CY + RING * math.sin(a), 4)
        colony[f"cell_{i}"] = {"_control": "cell", "contents": {"biomass": 1.0}}

    return {
        "name": "Biofilm development — spatially-emergent aggregation, formation, and ECM persistence",
        "description": (
            "Fig 10 mechanistic variant. Six motile cells on a 2-D box (lattice units) aggregate by "
            "LOCAL adhesion toward neighbours; once a quorum sits within form_radius of the centroid "
            "for sustain_ticks consecutive ticks the biofilm FORMS — an emergent place-graph rewrite "
            "nesting the cells under a new biofilm node (identity + biomass preserved), after which the "
            "collective cohesion port becomes operative. Sessile cells secrete ECM that binds the "
            "community; without ECM they spread back apart. Formation is driven by cluster geometry, "
            "not a wall clock. Matched-null controls (adhesion off, ECM off — via epsilon) isolate each arm."),
        "default_n_steps": 24,
        "requires": {"processes": ["BiofilmColony"]},
        "provenance": {"figure": "fig10-development", "environment": "fig10-mechanistic"},
        "state": {
            "colony_dynamics": {
                "_type": "process", "address": "local:BiofilmColony", "interval": 1.0,
                "config": {"sense_radius": 6.0, "adhesion": 0.35, "repulsion": 0.45,
                           "rep_radius": 1.2, "form_radius": 2.2, "quorum": 4.0,
                           "sustain_ticks": 3.0, "ecm_rate": 0.6, "ecm_decay": 0.05,
                           "k_bind": 2.0, "spread_rate": 0.5, "max_step": 1.0},
                "inputs": {"xs": ["xs"], "ys": ["ys"], "ecm": ["ecm"], "colony": ["colony"]},
                "outputs": {"xs": ["xs"], "ys": ["ys"], "ecm": ["ecm"], "colony": ["colony"],
                            "cluster_radius": ["obs", "cluster_radius"],
                            "cohesion": ["obs", "cohesion"], "n_clustered": ["obs", "n_clustered"],
                            "formed": ["obs", "formed"], "ecm_total": ["obs", "ecm_total"]},
            },
            "xs": xs,
            "ys": ys,
            "ecm": {"_type": "concentration", "_default": 0.0},
            "colony": colony,
            "obs": {
                "cluster_radius": {"_type": "length", "_default": 0.0},
                "cohesion": {"_type": "fraction", "_default": 0.0},
                "n_clustered": {"_type": "cell_count", "_default": 0.0},
                "formed": {"_type": "fraction", "_default": 0.0},
                "ecm_total": {"_type": "concentration", "_default": 0.0},
            },
            "emitter": {
                "_type": "step", "address": "local:RAMEmitter",
                "config": {"emit": {"cluster_radius": "length", "cohesion": "fraction",
                                    "n_clustered": "cell_count", "formed": "fraction",
                                    "ecm_total": "concentration", "colony": "tree[node]",
                                    "time": "float"}},
                "inputs": {"cluster_radius": ["obs", "cluster_radius"],
                           "cohesion": ["obs", "cohesion"], "n_clustered": ["obs", "n_clustered"],
                           "formed": ["obs", "formed"], "ecm_total": ["obs", "ecm_total"],
                           "colony": ["colony"], "time": ["global_time"]},
            },
        },
    }


if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), indent=2))
    print(f"wrote {OUT}")
