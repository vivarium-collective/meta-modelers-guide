#!/usr/bin/env python
"""Stamp a biological `_figure` (inline-SVG icon) onto every node of every
figure composite, so loom renders an illustration on each store and process.

Idempotent: re-running overwrites the `_figure` values. Run after editing the
icon library (figures.py) or the composites, then re-render with
scripts/render_loom_svgs.mjs.
"""
from __future__ import annotations

import json
from pathlib import Path

from meta_modelers_guide.figures import figure_for_process, figure_for_store
from meta_modelers_guide._types import STRING_TYPES

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "meta_modelers_guide" / "composites"


def stamp(node: dict) -> None:
    """Recursively add `_figure` to a store branch / leaf / process node."""
    for key, val in list(node.items()):
        if key.startswith("_") or key == "config":
            continue
        if not isinstance(val, dict):
            continue
        if val.get("_type") == "process":
            cls = str(val.get("address", "")).split(":")[-1]
            val["_figure"] = figure_for_process(cls)
        elif "_type" in val:                       # typed leaf store
            # A `_figure` on a STRING-typed leaf (sequence/identity/structure)
            # makes process-bigraph's realize try to parse the SVG as a type and
            # fail; float-typed leaves, groups, and processes are unaffected.
            if val["_type"] not in STRING_TYPES:
                val["_figure"] = figure_for_store(key, val["_type"])
            else:
                val.pop("_figure", None)
        else:                                       # store group / compartment
            val["_figure"] = figure_for_store(key, "")
            stamp(val)                              # recurse into children


def main() -> None:
    for spec_path in sorted(COMPOSITES.glob("*.composite.json")):
        spec = json.loads(spec_path.read_text())
        stamp(spec["state"])
        spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
        print("stamped", spec_path.name)


if __name__ == "__main__":
    main()
