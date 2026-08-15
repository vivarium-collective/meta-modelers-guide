#!/usr/bin/env python
"""Render every figure composite to a paper-styled SVG (and optional PNG).

Usage:
    python scripts/render_figures.py [--out DIR] [--png]

Writes ``<name>.svg`` for each ``workspace/composites/*.composite.json`` into
``--out`` (default ``workspace/figures``). With ``--png`` it also rasterizes via
``rsvg-convert`` when that binary is available.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from viva_meta_modelers_guide.core import build_core
from viva_meta_modelers_guide.figure_render import render_composite

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "workspace" / "composites"

# concise figure caption per composite (falls back to the spec description)
CAPTIONS = {
    "fig04a-interaction-modalities": "Fig 4a · interaction-modality cards of the cellular interface",
    "fig04b-cellular-interface": "Fig 4b · the minimal cellular interface (physical + cellular ports)",
    "fig05-cell-environment": "Fig 5b · cell–environment coupling (sense/act loop)",
    "fig06-disintegration": "Fig 6b · disintegration — the metabolism ⇄ reactions grain swap",
    "fig07-molecular-mechanism": "Fig 7b/c · a molecular mechanism and its typed channels",
    "fig08-nested-hierarchy": "Fig 8b · molecular compositions as a nested hierarchy",
    "fig09a-coarse-graining": "Fig 9a · coarse-graining ladder → autopoietic closure",
    "fig09b-minimal-cell": "Fig 9b · minimal-cell composition",
    "fig10-1-division": "Fig 10.1 · division as a compositional rewrite",
    "fig10-2-development": "Fig 10.2 · development — biofilm reorganization",
    "fig10-3-evolution": "Fig 10.3 · evolution — variation, selection, new ports",
}


def render_all(out_dir: Path, png: bool = False) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    core = build_core()
    written = []
    have_rsvg = png and _have("rsvg-convert")
    for spec_path in sorted(COMPOSITES.glob("*.composite.json")):
        spec = json.loads(spec_path.read_text())
        name = spec["name"]
        svg = render_composite(
            spec["state"], core,
            title=name,
            subtitle=CAPTIONS.get(name, spec.get("description", "").split(".")[0]),
        )
        svg_path = out_dir / f"{name}.svg"
        svg_path.write_text(svg)
        written.append(svg_path)
        if have_rsvg:
            subprocess.run(
                ["rsvg-convert", "-o", str(out_dir / f"{name}.png"), str(svg_path)],
                check=False,
            )
        print("rendered", svg_path.relative_to(ROOT))
    return written


def _have(binary: str) -> bool:
    from shutil import which
    return which(binary) is not None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "workspace" / "figures"))
    ap.add_argument("--png", action="store_true")
    args = ap.parse_args()
    paths = render_all(Path(args.out), png=args.png)
    print(f"\n{len(paths)} figures rendered to {args.out}")
