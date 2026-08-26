#!/usr/bin/env python
"""Generate the three division snapshot composites from the ACTUAL fig09-rewrite run.

Fig 9b's division is a genuine runtime place-graph rewrite (meta_modelers_guide.
fig10_rewrite.build_fig10_division): it starts as one cell and, on running,
rewrites its own topology — the chromosome replicates (1->2), then the cell
divides (1->2 daughters). This script RUNS that simulation and captures the
colony `tree[node]` at the three stages it actually passes through, writing each
as a static snapshot composite so the loom can render the sequence:

  fig09b-division-1-onecell     t=0   colony > cell > chromosome
  fig09b-division-2-replicated  t=3   colony > cell > {chromosome_0, chromosome_1}
  fig09b-division-3-divided     t=6   colony > {cell_0, cell_1} each > chromosome

These are NOT hand-authored: they are the emitted frames of the rewrite, so the
three-panel figure is a faithful time series of the running simulation. Re-run
whenever the rewrite mechanism changes.

    python scripts/build_division_snapshots.py
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.fig10_rewrite import build_fig10_division

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "meta_modelers_guide" / "composites"

# stage stem -> (emitted frame index, panel title, description tail)
STAGES = {
    "fig09b-division-1-onecell": (
        0, "One cell",
        "t=0 — the initial place graph: a single cell containing one chromosome. "
        "Running the rewrite changes this topology; it is not pre-declared."),
    "fig09b-division-2-replicated": (
        3, "Chromosome replicated",
        "t=1 cycle — the chromosome has replicated: one cell now holds two sister "
        "chromosomes (chromosome_0, chromosome_1). A genuine runtime node addition."),
    "fig09b-division-3-divided": (
        6, "Cell divided",
        "t=2 cycles — the cell has divided: the place graph now holds two daughter "
        "cells (cell_0, cell_1), each partitioned exactly one sister chromosome."),
}


def _normalize(chrom: dict) -> dict:
    """Canonical chromosome node: dna under `contents` (segregation leaves it flat)."""
    if "contents" in chrom and isinstance(chrom["contents"], dict):
        return chrom
    dna = chrom.get("dna", 1.0)
    return {"_control": "chromosome", "contents": {"dna": dna}}


def _normalize_colony(colony: dict) -> dict:
    out = {"_type": "tree[node]"}
    for ck, cell in colony.items():
        if ck.startswith("_"):
            continue
        contents = cell.get("contents", cell)
        chroms = {k: _normalize(v) for k, v in contents.items()
                  if not k.startswith("_") and isinstance(v, dict)}
        out[ck] = {"_control": "cell", "contents": chroms}
    return out


def main() -> None:
    core = build_core()
    sim = Composite(build_fig10_division(cycle=3.0, interval=1.0), core=core)
    sim.run(9)
    frames = [r["colony"] for r in gather_emitter_results(sim)[("emitter",)]]

    for stem, (idx, title, tail) in STAGES.items():
        colony = _normalize_colony(frames[idx])
        spec = {
            "name": f"Fig 9b division — {title}",
            "description": (
                f"Fig 9b, division snapshot: {tail} Auto-generated from the "
                f"fig09-rewrite simulation (scripts/build_division_snapshots.py); "
                f"one of three sequential frames of the running place-graph rewrite."),
            "state": {"colony": colony},
        }
        path = COMPOSITES / f"{stem}.composite.json"
        path.write_text(json.dumps(spec, indent=2) + "\n")
        n_cells = sum(1 for k in colony if not k.startswith("_"))
        print(f"wrote {path.name}  ({n_cells} cell(s))")

    # Times manifest so the stitcher labels each panel with its REAL sim step
    # (frame index, interval=1) — labels can never drift out of sync.
    viz = ROOT / "workspace" / "studies" / "fig-09" / "visualizations"
    viz.mkdir(parents=True, exist_ok=True)
    (viz / "snapshot-times.json").write_text(
        json.dumps({f"{stem}.png": idx for stem, (idx, *_) in STAGES.items()}, indent=2) + "\n")
    print("wrote fig-09 snapshot-times.json")


if __name__ == "__main__":
    main()
