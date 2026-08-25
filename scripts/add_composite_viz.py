#!/usr/bin/env python
"""Embed an interactive Plotly Visualization step in every EXECUTABLE composite.

Each ``composites/<stem>.composite.json`` that RUNS (executables, the fig10 live
rewrites, and the composed whole cell) gets a ``dynamics_viz`` step wired to the
observables that move — a :class:`meta_modelers_guide.visualization.DynamicsPlot`.
Arc-worthy figures (the whole cell's grow→divide→die, division / biofilm /
evolution, the central-dogma cascade, autopoietic closure) additionally get a
``dynamics_movie`` (:class:`DynamicsMovie`) — a Play-button animation of the same
data. On ▶ Run in the loom these surface in the Visualizations panel.

Idempotent: re-running replaces the ``dynamics_viz`` / ``dynamics_movie`` entries.
The observable set is discovered exactly as ``render_study_evidence`` extracts it,
so the plot matches the study evidence.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from meta_modelers_guide._types import UNITS

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "meta_modelers_guide" / "composites"
NUMERIC = set(UNITS) | {"float"}

# Every composite that actually runs → gets DynamicsPlot.
TARGETS = [
    "fig03b-executable", "fig04-executable",
    "fig05-executable-coarse", "fig05-executable-kinetic", "fig05-executable-fba",
    "fig05-disintegration-dynamics",
    "cellcell-executable-compete", "cellcell-executable-crossfeed",
    "fig06-executable", "fig07-executable",
    "fig08a-executable", "fig08b-executable",
    "fig09-executable", "fig10-executable", "fig11-executable",
    "fig09-rewrite", "fig10-rewrite", "fig11-rewrite",
    "whole-cell",
]

# Narrative overrides (Task: flagship disintegration figure) — a composite listed
# here gets a curated, story-driven DynamicsPlot instead of the generic "every
# numeric leaf, dynamic-range order" wiring: ``keep`` restricts which leaves are
# wired at all (by their leaf/port name), and the remaining keys become extra
# DynamicsPlot config (subtitle/phases/events/secondary_y/area — see
# visualization.py's narrative-config docstring). Composites absent from this
# dict keep the plain behaviour unchanged.
STORY = {
    "fig05-disintegration-dynamics": {
        "keep": ["viability", "biomass", "debris", "temperature"],
        "subtitle": "Fig 6 — a thermal shock pushes the cell past its viability bound",
        "secondary_y": ["temperature"],
        "area": ["debris"],
        "phases": [
            {"x0": 0, "x1": 8, "label": "viable", "color": "#1c7a77"},
            {"x0": 8, "x1": 20, "label": "disintegrating", "color": "#b4531f"},
        ],
        "events": [{"x": 8, "label": "thermal shock (37→50 °C)"}],
    },
    "fig03b-executable": {
        "keep": ["viability", "shape", "objective", "chemical", "growth_rate"],
        "subtitle": "Fig 4 — a typed contract compiled to a bounded cell",
        "phases": [{"x0": 0, "x1": 8, "label": "viable", "color": "#1c7a77"}],
    },
    "fig04-executable": {
        "keep": ["uptake_flux", "mechanical_field", "shape", "mass"],
        "subtitle": "Fig 5 — cell ↔ environment over a real diffusing field",
    },
    "cellcell-executable-compete": {
        "keep": ["viability", "nutrient"],
        "subtitle": "Cell–cell coupling — one shared nutrient pool, asymmetric handlers",
        "events": [{"x": 2, "label": "cell_b viability < 0.5 — competitive exclusion"}],
    },
    "cellcell-executable-crossfeed": {
        "keep": ["viability", "nutrient"],
        "subtitle": "Cell–cell coupling — symmetric handlers, byproduct returned to the pool",
    },
    "fig06-executable": {
        "keep": ["chemical_out", "electrical_out", "mechanical_out", "thermal_out"],
        "subtitle": "Fig 7 — one proton flux drives four coupled channels",
        "secondary_y": ["electrical_out", "mechanical_out", "thermal_out"],
    },
    "fig07-executable": {
        "keep": ["rna", "ribosome", "proteins"],
        "subtitle": "Fig 8 — transcription → translation → assembly, six levels deep",
    },
    "fig08a-executable": {
        "keep": ["boundary", "membrane", "aggregate", "metabolites", "products", "copies"],
        "subtitle": "Fig 9a — one function (containment), three conforming grains",
    },
    "fig08b-executable": {
        "subtitle": "Fig 9b — the minimal cell: metabolism, containment, replication holding each other up",
    },
    "fig09-executable": {
        "keep": ["dna", "biomass", "cell_count"],
        "subtitle": "Fig 10a,b — growth reaches threshold, the place graph splits",
        "events": [{"x": 6, "label": "division fires — mass conserved"}],
    },
    "fig10-executable": {
        "keep": ["biofilm_mass", "ecm", "cells", "attached"],
        "subtitle": "Fig 10c,d — a continuous, pre-declared biofilm store (not a place-graph rewrite)",
    },
    "fig11-executable": {
        "keep": ["cell_count", "new_port"],
        "subtitle": "Fig 10e,f — a config-driven port-onset ramp, not emergent selection",
        "events": [{"x": 7, "label": "new_port crosses 0.5 — port switching on"}],
    },
}
# Figures where watching the arc over time matters → also get DynamicsMovie.
MOVIE = {
    "fig07-executable", "fig08a-executable", "fig08b-executable",
    "fig09-executable", "fig10-executable", "fig11-executable",
    "fig09-rewrite", "fig10-rewrite", "fig11-rewrite",
    "whole-cell",
}

TITLES = {
    "fig03b-executable": "The cellular interface, made to run",
    "fig04-executable": "A closed sense/act loop",
    "fig05-executable-coarse": "Coarse metabolism (lumped yield)",
    "fig05-executable-kinetic": "Kinetic metabolism (Michaelis–Menten)",
    "fig05-executable-fba": "FBA metabolism (e_coli_core, with acetate overflow)",
    "fig05-disintegration-dynamics": "Disintegration — the cell → molecular level shift",
    "cellcell-executable-compete": "Competition — the weaker cell starves",
    "cellcell-executable-crossfeed": "Cross-feeding — both persist",
    "fig06-executable": "ATP synthase — a proton-motive-force-driven rotary motor",
    "fig07-executable": "The central-dogma cascade across six nested levels",
    "fig08a-executable": "Closure sustains the interface — three conforming grains",
    "fig08b-executable": "Closure sustains the interface — the minimal cell",
    "fig09-executable": "Growth to division — one cell becomes two",
    "fig10-executable": "A biofilm assembles",
    "fig11-executable": "A variant gains a new port",
    "fig09-rewrite": "Division rewrite — the place graph splits",
    "fig10-rewrite": "Biofilm rewrite — the colony assembles",
    "fig11-rewrite": "Evolution rewrite — variation & selection",
    "whole-cell": "The composed whole cell — grow · divide · die",
}


def _emittable(state, prefix=()):
    """Yield (label, emit_type, path) for numeric scalar and map[float] leaves —
    identical to scripts/render_study_evidence.py so the viz matches the evidence."""
    if not isinstance(state, dict):
        return
    if state.get("_type") == "process":
        return
    t = state.get("_type")
    if isinstance(t, str) and (t in NUMERIC or t.startswith("map")):
        label = ".".join(prefix)
        emit_t = "map[string,float]" if t.startswith("map") else "float"
        yield label, emit_t, list(prefix)
        return
    for k, v in state.items():
        if not k.startswith("_") and isinstance(v, dict):
            yield from _emittable(v, prefix + (k,))


def _viz_entry(address: str, title: str, leaves, extra_config: dict | None = None) -> dict:
    """Build a Visualization step entry wired to the discovered leaves. Port names
    are the leaf name (last path segment), de-duplicated so collisions stay wired
    to distinct stores. ``extra_config`` (e.g. subtitle/phases/events/secondary_y/
    area — see visualization.py's narrative-config docstring) is merged into the
    step's config verbatim, on top of title/observables."""
    observables: dict[str, str] = {}
    inputs: dict[str, list] = {}
    used: set[str] = set()
    for label, emit_t, path in leaves:
        base = re.sub(r"[^0-9A-Za-z_]", "_", path[-1]) or "obs"
        name = base
        i = 2
        while name in used:
            name = f"{base}_{i}"
            i += 1
        used.add(name)
        observables[name] = emit_t
        inputs[name] = path
    inputs["time"] = ["global_time"]
    config = {"title": title, "observables": observables, **(extra_config or {})}
    return {
        "_type": "step",
        "address": f"local:{address}",
        "config": config,
        "inputs": inputs,
        "outputs": {"html": ["_viz", re.sub(r"[^0-9a-z]", "_", address.lower())]},
    }


def main():
    n = 0
    for stem in TARGETS:
        p = COMPOSITES / f"{stem}.composite.json"
        if not p.exists():
            print(f"  – {stem}: missing")
            continue
        doc = json.loads(p.read_text())
        state = doc["state"]
        leaves = [lp for lp in _emittable(state) if lp[2]][:40]
        story = dict(STORY.get(stem, {}))
        keep = story.pop("keep", None)
        if keep:
            keep_set = set(keep)
            leaves = [lp for lp in leaves if lp[2][-1] in keep_set]
        title = TITLES.get(stem, stem)
        state.pop("dynamics_viz", None)
        state.pop("dynamics_movie", None)
        if not leaves:
            # No fixed numeric leaves in the initial state — these are the fig10
            # live-rewrite composites whose nodes are ADDED during the run. A
            # time-series has nothing to wire to; the workbench's automatic
            # topology filmstrip (render_topology_viz) is their "movie" instead.
            p.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
            print(f"  – {stem}: no fixed observables → relies on the auto topology filmstrip")
            continue
        state["dynamics_viz"] = _viz_entry("DynamicsPlot", title, leaves, story)
        extras = ["dynamics_viz"]
        if stem in MOVIE:
            state["dynamics_movie"] = _viz_entry("DynamicsMovie", title + " (movie)", leaves)
            extras.append("dynamics_movie")
        p.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        print(f"  ✓ {stem}: {len(leaves)} observables → {', '.join(extras)}")
        n += 1
    print(f"\n{n}/{len(TARGETS)} composites given an embedded Plotly visualization.")


if __name__ == "__main__":
    main()
