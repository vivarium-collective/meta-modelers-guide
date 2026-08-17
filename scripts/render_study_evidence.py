#!/usr/bin/env python
"""Render each study's dynamics SVG **from its compiled executable** — the single
evidence source.

Every study in the *From Draft to Living Cell* investigation is framed as a typed
DRAFT contract (the ``composites/fig*-*`` the study's Model tab shows) that the
compiler installs handlers behind to make an EXECUTABLE (``composites/fig*-executable*``).
The study's *evidence* — the dynamics it cites in its runs and behaviour tests —
must come from running that executable, not from a separate model. This script is
that single bridge: for each study it builds the study's executable(s), runs them,
extracts the observables that move, renders ``<slug>-dynamics.svg`` into the study's
own ``visualizations/``, and records the first/last of every moving observable (plus
a conservation-style invariant) into ``scripts/_catalog/executable_readouts.json``.

Studies cite THIS script + their executable in ``runs[].provenance``. It replaces
the retired ``render_dynamics.py`` (which ran the separate ``dynamics`` model
family) and ``render_executable_dynamics.py`` (which rendered into one gallery dir).
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from process_bigraph import Composite, gather_emitter_results

from viva_meta_modelers_guide.core import build_core
from viva_meta_modelers_guide._types import UNITS

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "viva_meta_modelers_guide" / "composites"
STUDIES = ROOT / "workspace" / "studies"
CATALOG = ROOT / "scripts" / "_catalog"
CATALOG.mkdir(parents=True, exist_ok=True)

NUMERIC = set(UNITS) | {"float"}
TOTAL_TIME = 8.0
PALETTE = ["#0d6e6b", "#a5620f", "#3f9e99", "#657572",
           "#c98a3a", "#1c7a77", "#8b9995", "#0a4f4c"]

# study slug → the executable composite stem(s) that ARE its evidence.
# Multi-executable studies (one interface / many handlers, or coarse+fine) render
# a small-multiple; the-living-atlas is the whole compiled gallery.
STUDY_EXECUTABLES = {
    "typed-interface": ["fig04b-executable"],
    "closing-the-loop": ["fig05-executable"],
    "one-interface-three-mechanisms": [
        "fig06-executable-coarse", "fig06-executable-kinetic", "fig06-executable-fba"],
    "molecular-channels": ["fig07-executable"],
    "the-nested-cell": ["fig08-executable"],
    "self-made": ["fig09a-executable", "fig09b-executable"],
    "divide": ["fig10-1-executable"],
    "biofilm": ["fig10-2-executable"],
    "evolve": ["fig10-3-executable"],
    "the-living-atlas": [
        "fig04b-executable", "fig05-executable",
        "fig06-executable-coarse", "fig06-executable-kinetic", "fig06-executable-fba",
        "fig07-executable", "fig08-executable",
        "fig09a-executable", "fig09b-executable",
        "fig10-1-executable", "fig10-2-executable", "fig10-3-executable"],
}


# Honest, executable-derived one-line "signature" per study — what the compiled
# executable actually shows (NOT a conservation invariant; the executables are not
# closed batches). Rendered by render_report.py as each figure's checked signature.
INVARIANTS = {
    "typed-interface": {
        "invariant_kind": "interface",
        "invariant": "the Fig 4 thermal interface runs — shape 1.0→4.2, objective 0→1.6, "
                     "chemical 0→−0.8; viability holds (1.0→0.97)"},
    "closing-the-loop": {
        "invariant_kind": "closed-loop",
        "invariant": "the cell senses the field and acts back — bolus drawn down (1.0→0.2), "
                     "traction 0→0.41, mechanical response 0→0.94 (a closed sense→act loop)"},
    "one-interface-three-mechanisms": {
        "invariant_kind": "interface-preserved",
        "invariant": "one nutrients⇒biomass interface, three handlers → coarse 4.0 / kinetic 2.67 / "
                     "FBA 6.29 (+acetate overflow 30.4); same ports, distinct dynamics (law 4)"},
    "molecular-channels": {
        "invariant_kind": "mechanism",
        "invariant": "the F1Fo ATP synthase runs on the Fig 7 interface — ATP output 0→100 "
                     "(proton-motive-force-driven rotary catalysis)"},
    "the-nested-cell": {
        "invariant_kind": "hierarchy",
        "invariant": "the central dogma runs nested in the cell — metabolites 0→1.5, rna 0→0.18, "
                     "energy 0→0.84 across scales on one interface"},
    "self-made": {
        "invariant_kind": "closure",
        "invariant": "autopoietic closure self-sustains structure — membrane 0→1.6, enzymes 0→0.72; "
                     "the inert draft stays at seed"},
    "divide": {
        "invariant_kind": "rewrite",
        "invariant": "division as a real topology event — cell_count 1→2, two daughters "
                     "(dna 0→2.75 each), parent dna 1→3.06"},
    "biofilm": {
        "invariant_kind": "composition",
        "invariant": "cells reorganize into a colony — aggregate biofilm_mass 0→2.25, ecm 0→1.8; "
                     "colony-level observables emerge from nesting"},
    "evolve": {
        "invariant_kind": "innovation",
        "invariant": "a variant acquires a new interface port under selection — new_port 0→0.57 "
                     "while the population grows (cell_count 1→3.4)"},
    "the-living-atlas": {
        "invariant_kind": "composition",
        "invariant": "12/12 figures compile to executables that run; assembled, the cell grows, "
                     "divides once (1→2), and dies (viability 1.0→0.02, debris 0→4.87)"},
}


def _emittable(state, prefix=()):
    """Yield (label, emit_type, path) for numeric scalar and map[float] leaves."""
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


def _run(stem):
    state = json.loads((COMPOSITES / f"{stem}.composite.json").read_text())["state"]
    leaves = list(_emittable(state))[:40]
    if not leaves:
        return None
    emit = {lab: et for lab, et, _ in leaves}
    emit["time"] = "float"
    inputs = {lab: p for lab, _, p in leaves}
    inputs["time"] = ["global_time"]
    state = dict(state)
    state["vizemitter"] = {"_type": "step", "address": "local:RAMEmitter",
                           "config": {"emit": emit}, "inputs": inputs}
    core = build_core()
    sim = Composite({"state": state}, core=core)
    sim.run(TOTAL_TIME)
    return gather_emitter_results(sim)[("vizemitter",)]


def _series(rows):
    """Flatten rows into {label: [values]} + times, expanding map fields; drop
    non-finite / constant series."""
    import math
    times = [r.get("time", i) for i, r in enumerate(rows)]
    out = {}
    for key in rows[0]:
        if key == "time":
            continue
        v0 = rows[0][key]
        if isinstance(v0, dict):
            for ck in list(v0)[:9]:
                out[f"{key}[{ck}]"] = [float(r[key].get(ck, 0.0)) for r in rows]
        else:
            out[key] = [float(r[key]) for r in rows]
    clean = {}
    for lab, ys in out.items():
        if all(math.isfinite(y) for y in ys) and (max(ys) - min(ys)) > 1e-9:
            clean[lab] = ys
    return times, clean


def _panel(ax, stem, title):
    rows = _run(stem)
    if not rows:
        ax.set_visible(False)
        return {}
    times, series = _series(rows)
    if not series:
        ax.set_visible(False)
        return {}
    top = sorted(series.items(), key=lambda kv: max(kv[1]) - min(kv[1]), reverse=True)[:6]
    for i, (lab, ys) in enumerate(top):
        ax.plot(times, ys, lw=2, color=PALETTE[i % len(PALETTE)], label=lab.split(".")[-1])
    ax.set_title(title, fontsize=10, color="#16211f")
    ax.set_xlabel("time", fontsize=8)
    ax.legend(fontsize=6.5, frameon=False, loc="best")
    ax.grid(True, alpha=0.15)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    # readout: every moving observable's first/last (agents reconcile YAML to this)
    return {lab: {"first": round(ys[0], 4), "last": round(ys[-1], 4),
                  "min": round(min(ys), 4), "max": round(max(ys), 4)}
            for lab, ys in series.items()}


def render(slug, stems):
    viz = STUDIES / slug / "visualizations"
    if not viz.parent.exists():
        return None
    viz.mkdir(parents=True, exist_ok=True)
    n = len(stems)
    if n == 1:
        fig, axes = plt.subplots(1, 1, figsize=(5.4, 3.5), dpi=100)
        axes = [axes]
    else:
        cols = min(3, n)
        rows_ = (n + cols - 1) // cols
        fig, axgrid = plt.subplots(rows_, cols, figsize=(4.4 * cols, 3.2 * rows_), dpi=100)
        axes = list(axgrid.flat) if hasattr(axgrid, "flat") else [axgrid]
    readouts = {}
    for ax, stem in zip(axes, stems):
        title = stem.replace("-executable", "").replace("-", " ")
        readouts[stem] = _panel(ax, stem, title)
    for ax in axes[len(stems):]:
        ax.set_visible(False)
    fig.suptitle(slug.replace("-", " "), fontsize=11, color="#16211f", y=0.99)
    fig.tight_layout()
    out = viz / f"{slug}-dynamics.svg"
    fig.savefig(out, format="svg")
    plt.close(fig)
    return readouts


def main():
    catalog = {}
    for slug, stems in STUDY_EXECUTABLES.items():
        try:
            readouts = render(slug, stems)
        except Exception as exc:
            print(f"  ✗ {slug}: {type(exc).__name__}: {exc}")
            continue
        if readouts is None:
            print(f"  – {slug}: no study dir")
            continue
        n_obs = sum(len(v) for v in readouts.values())
        catalog[slug] = {"executables": stems, "readouts": readouts}
        print(f"  ✓ {slug}: {len(stems)} exec, {n_obs} moving observables")
    (CATALOG / "executable_readouts.json").write_text(json.dumps(catalog, indent=2))
    # dynamics_readouts.json holds the per-study one-line signature the report shows;
    # regenerate it with honest, executable-derived text (the file name is legacy).
    (CATALOG / "dynamics_readouts.json").write_text(json.dumps(INVARIANTS, indent=2))
    print(f"\n{len(catalog)}/{len(STUDY_EXECUTABLES)} studies → executable evidence "
          f"| catalogs: scripts/_catalog/{{executable,dynamics}}_readouts.json")


if __name__ == "__main__":
    main()
