#!/usr/bin/env python
"""Render a dynamics figure (SVG) for each EXECUTABLE composite.

The fig-compilation study shows that the paper's semantic figures compile to
executables that *run*. The most fitting visualization is therefore the dynamics
each executable produces. For every ``composites/*-executable*.composite.json`` this
builds the composite, runs it, and plots the observables that change most — a clean,
uniform gallery of "each compiled figure, actually running" — into
``workspace/studies/fig-compilation/visualizations/<stem>.svg``.

Robust and workbench-free (matplotlib native SVG). Complements the per-figure
studies' loom renders of the *semantic* composites.
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
VIZ = ROOT / "workspace" / "studies" / "fig-compilation" / "visualizations"
VIZ.mkdir(parents=True, exist_ok=True)

NUMERIC = set(UNITS) | {"float"}
TOTAL_TIME = 8.0
TEAL, PALETTE = "#0d6e6b", ["#0d6e6b", "#a5620f", "#3f9e99", "#657572",
                            "#c98a3a", "#1c7a77", "#8b9995", "#0a4f4c"]


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
    leaves = list(_emittable(state))[:40]                 # cap breadth
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
    non-finite / constant-zero series."""
    import math
    times = [r.get("time", i) for i, r in enumerate(rows)]
    out = {}
    for key in rows[0]:
        if key == "time":
            continue
        v0 = rows[0][key]
        if isinstance(v0, dict):                          # map field → per-cell series
            for ck in list(v0)[:9]:
                out[f"{key}[{ck}]"] = [float(r[key].get(ck, 0.0)) for r in rows]
        else:
            out[key] = [float(r[key]) for r in rows]
    clean = {}
    for lab, ys in out.items():
        if all(math.isfinite(y) for y in ys) and (max(ys) - min(ys)) > 1e-9:
            clean[lab] = ys
    return times, clean


def render(stem):
    rows = _run(stem)
    if not rows:
        return False
    times, series = _series(rows)
    if not series:
        return False
    top = sorted(series.items(), key=lambda kv: max(kv[1]) - min(kv[1]), reverse=True)[:6]
    fig, ax = plt.subplots(figsize=(5.2, 3.4), dpi=100)
    for i, (lab, ys) in enumerate(top):
        ax.plot(times, ys, lw=2, color=PALETTE[i % len(PALETTE)], label=lab.split(".")[-1])
    ax.set_title(stem.replace("-executable", "").replace("-", " "), fontsize=11, color="#16211f")
    ax.set_xlabel("time", fontsize=9)
    ax.set_ylabel("observable", fontsize=9)
    ax.legend(fontsize=7, frameon=False, loc="best")
    ax.grid(True, alpha=0.15)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(VIZ / f"{stem}.svg", format="svg")
    plt.close(fig)
    return True


def main():
    stems = sorted(p.name.replace(".composite.json", "")
                   for p in COMPOSITES.glob("*executable*.composite.json"))
    done = []
    for stem in stems:
        try:
            ok = render(stem)
        except Exception as exc:
            print(f"  {stem}: ERROR {type(exc).__name__}: {exc}")
            ok = False
        print(("  ✓ " if ok else "  – ") + stem)
        if ok:
            done.append(stem)
    print(f"\n{len(done)}/{len(stems)} dynamics figures rendered into {VIZ}")
    return done


if __name__ == "__main__":
    main()
