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
    "fig04b-executable", "fig05-executable",
    "fig06-executable-coarse", "fig06-executable-kinetic", "fig06-executable-fba",
    "fig07-executable", "fig08-executable",
    "fig09a-executable", "fig09b-executable",
    "fig10-1-executable", "fig10-2-executable", "fig10-3-executable",
    "fig10-1-rewrite", "fig10-2-rewrite", "fig10-3-rewrite",
    "whole-cell",
]
# Figures where watching the arc over time matters → also get DynamicsMovie.
MOVIE = {
    "fig08-executable", "fig09a-executable", "fig09b-executable",
    "fig10-1-executable", "fig10-2-executable", "fig10-3-executable",
    "fig10-1-rewrite", "fig10-2-rewrite", "fig10-3-rewrite",
    "whole-cell",
}

TITLES = {
    "fig04b-executable": "Thermal interface — shape, objective, chemical",
    "fig05-executable": "Cell ↔ environment — a closed sense/act loop",
    "fig06-executable-coarse": "Coarse metabolism (lumped yield)",
    "fig06-executable-kinetic": "Kinetic metabolism (Michaelis–Menten)",
    "fig06-executable-fba": "FBA metabolism (e_coli_core, with acetate overflow)",
    "fig07-executable": "F1Fo ATP synthase — proton-motive-force-driven output",
    "fig08-executable": "Central dogma — nested transcription/translation cascade",
    "fig09a-executable": "Autopoiesis (coarse) — closure sustains the membrane",
    "fig09b-executable": "Autopoiesis (minimal cell) — enzymes & membrane held up",
    "fig10-1-executable": "Division — one cell becomes two",
    "fig10-2-executable": "Development — cells reorganize into a colony",
    "fig10-3-executable": "Evolution — a variant sweeps and gains a new port",
    "fig10-1-rewrite": "Division rewrite — the place graph splits",
    "fig10-2-rewrite": "Biofilm rewrite — the colony assembles",
    "fig10-3-rewrite": "Evolution rewrite — variation & selection",
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


def _viz_entry(address: str, title: str, leaves) -> dict:
    """Build a Visualization step entry wired to the discovered leaves. Port names
    are the leaf name (last path segment), de-duplicated so collisions stay wired
    to distinct stores."""
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
    return {
        "_type": "step",
        "address": f"local:{address}",
        "config": {"title": title, "observables": observables},
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
        state["dynamics_viz"] = _viz_entry("DynamicsPlot", title, leaves)
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
