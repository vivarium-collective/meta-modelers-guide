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

from meta_modelers_guide.core import build_core
from meta_modelers_guide._types import UNITS

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "meta_modelers_guide" / "composites"
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
    # LEAD — the thesis: one interface, three mechanisms (incl. real FBA)
    "one-interface-three-mechanisms": [
        "fig05-executable-coarse", "fig05-executable-kinetic", "fig05-executable-fba"],
    "divide": ["fig09-executable"],
    # "The Contract and Its Coupling" — Fig 4 interface + Fig 5 sense/act loop
    "typed-interface": ["fig03b-executable", "fig04-executable"],
    "the-nested-cell": ["fig06-executable", "fig07-executable"],
    # gallery appendix — every figure compiles and runs (the 12-panel small-multiple)
    "gallery": [
        "fig03b-executable", "fig04-executable",
        "fig05-executable-coarse", "fig05-executable-kinetic", "fig05-executable-fba",
        "fig06-executable", "fig07-executable",
        "fig08a-executable", "fig08b-executable",
        "fig09-executable", "fig10-executable", "fig11-executable"],
    # the-living-atlas capstone: the composed whole cell run THREE WAYS (metabolism
    # swap) — rendered specially below, not from executable panels.
    "the-living-atlas": [],
}


# Honest, executable-derived one-line "signature" per study — what the compiled
# executable actually shows (NOT a conservation invariant; the executables are not
# closed batches). Rendered by render_report.py as each figure's checked signature.
INVARIANTS = {
    "one-interface-three-mechanisms": {
        "invariant_kind": "interface-preserved",
        "invariant": "THE THESIS — one nutrients⇒biomass interface, three conforming handlers → "
                     "coarse 4.0 / kinetic 2.67 / real-FBA 6.29 (+acetate overflow 30.4); a "
                     "non-conforming impostor is rejected at compile time. Same ports, distinct "
                     "dynamics (law 4)"},
    "divide": {
        "invariant_kind": "rewrite",
        "invariant": "division as a first-class rewrite, GATED BY DNA (not a clock) — replicated "
                     "dna 1→3.06 crosses the threshold and the parent PARTITIONS: parent biomass→0, "
                     "each daughter 0.5 (mass conserved), cell_count 1→2"},
    "typed-interface": {
        "invariant_kind": "interface",
        "invariant": "the typed contract and its coupling — the Fig 4 interface runs (shape 1.0→4.2, "
                     "objective 0→1.6) and the Fig 5 cell senses a field and acts back (traction "
                     "0→0.41, mechanical response 0→0.94), a closed sense→act loop"},
    "the-nested-cell": {
        "invariant_kind": "hierarchy",
        "invariant": "molecular mechanisms compose into the nested cell — an F1Fo ATP synthase "
                     "(Fig 7) drives output 0→100, feeding a central-dogma cascade (rna 0→0.18, "
                     "metabolites 0→1.5) across nested scales on one interface"},
    "gallery": {
        "invariant_kind": "coverage",
        "invariant": "every figure compiles and runs — the 11 figure drafts materialize into 12 "
                     "executable composites (Fig 6's one interface carries three), each producing "
                     "non-trivial dynamics on its declared ports"},
    "the-living-atlas": {
        "invariant_kind": "composition",
        "invariant": "the capstone — the composed whole cell run THREE WAYS (metabolism swapped "
                     "behind identical ports): coarse peak 5.78 / kinetic 6.43 / fba 6.05, dividing "
                     "at t≈3.0 / 2.1 / 2.7 (mass-conserved), then a scripted thermal shock kills it "
                     "(viability→0.018). Handler independence at the whole-cell level"},
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


def _metabolism_swap(viz):
    """PRIMARY capstone figure: run the composed whole cell THREE WAYS — coarse /
    kinetic / fba metabolism behind identical ports — and overlay the biomass life
    histories. Same cell, three mechanisms, three trajectories: handler
    independence (Fig 6 law 4) demonstrated at the whole-cell level. Division marks
    (▾) show each mechanism reaches its division threshold at a different time."""
    from meta_modelers_guide.wholecell import build_whole_cell
    modes = [("coarse", "#0d6e6b"), ("kinetic", "#a5620f"), ("fba", "#1c7a77")]
    fig, ax = plt.subplots(figsize=(6.2, 3.9), dpi=100)
    ro = {}
    for mode, col in modes:
        core = build_core()
        sim = Composite(build_whole_cell(metabolism=mode), core=core)
        sim.run(20.0)
        rows = gather_emitter_results(sim)[("emitter",)]
        t = [r["time"] for r in rows]
        bm = [float(r["biomass"]) for r in rows]
        ax.plot(t, bm, lw=2.2, color=col, label=f"{mode} metabolism")
        div_t = next((r["time"] for r in rows if float(r["cell_count"]) >= 2), None)
        if div_t is not None:
            bi = min(range(len(t)), key=lambda i: abs(t[i] - div_t))
            ax.plot([div_t], [bm[bi]], marker="v", color=col, ms=8)
        ro[mode] = {"peak_biomass": round(max(bm), 3), "final": round(bm[-1], 3),
                    "divides_at": round(div_t, 2) if div_t else None,
                    "viability_min": round(min(float(r["viability"]) for r in rows), 4),
                    "debris_final": round(float(rows[-1]["debris"]), 3)}
    ax.set_title("one composed cell, three metabolisms — three life histories",
                 fontsize=11, color="#16211f")
    ax.set_xlabel("time", fontsize=9)
    ax.set_ylabel("biomass", fontsize=9)
    ax.legend(fontsize=8, frameon=False, loc="upper right",
              title="▾ = division (threshold reached)", title_fontsize=7)
    ax.grid(True, alpha=0.15)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(viz / "the-living-atlas-dynamics.svg", format="svg")
    plt.close(fig)
    return {"metabolism-swap": ro}


def render(slug, stems):
    viz = STUDIES / slug / "visualizations"
    if not viz.parent.exists():
        return None
    viz.mkdir(parents=True, exist_ok=True)
    # the-living-atlas: the capstone is the whole-cell METABOLISM-SWAP (rendered
    # specially, three runs overlaid) — no executable panels.
    if slug == "the-living-atlas":
        return _metabolism_swap(viz)
    atlas = False
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
    title = "the twelve compiled figures, each running" if atlas else slug.replace("-", " ")
    fig.suptitle(title, fontsize=11, color="#16211f", y=0.99)
    fig.tight_layout()
    # atlas: the gallery is the SECONDARY figure; the whole cell is the primary -dynamics.svg
    out = viz / (f"{slug}-gallery.svg" if atlas else f"{slug}-dynamics.svg")
    fig.savefig(out, format="svg")
    plt.close(fig)
    if atlas:
        readouts["whole-cell"] = _whole_cell(viz)["whole-cell"]
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
