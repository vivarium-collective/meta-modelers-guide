#!/usr/bin/env python
"""Regenerate every composite's ``_figure`` glyph from the canonical icon
library (``meta_modelers_guide.icons``).

Each node that currently carries a ``_figure`` is re-resolved by its name to a
concept and re-drawn in the refined scientific style, coloured by role (teal
store / indigo process). Nodes whose name doesn't resolve keep their existing
glyph (and are reported so the resolver can be extended).

    python scripts/regen_icons.py            # dry run: report coverage
    python scripts/regen_icons.py --apply     # rewrite the composite JSONs
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
from pathlib import Path

from meta_modelers_guide.icons import figure, resolve

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "meta_modelers_guide" / "composites"

_META_KEYS = {"_type", "address", "config", "inputs", "outputs", "_inputs",
              "_outputs", "_contract", "_figure", "_draft", "_value", "_default"}


def process_node(node: dict) -> bool:
    return isinstance(node, dict) and node.get("_type") == "process"


def walk(node, name, stats, *, apply: bool):
    """Visit each dict node; rewrite its ``_figure`` when its name resolves."""
    if not isinstance(node, dict):
        return
    if isinstance(node.get("_figure"), str) and "<svg" in node["_figure"]:
        concept = resolve(name)
        if concept:
            new = figure(name, process_node(node))
            stats["by_concept"][concept] += 1
            if new and new != node["_figure"]:
                stats["changed"] += 1
                if apply:
                    node["_figure"] = new
            elif new:
                stats["same"] += 1
        else:
            stats["unresolved"][name] += 1
    for k, v in node.items():
        if k in _META_KEYS:
            continue
        if isinstance(v, dict):
            walk(v, k, stats, apply=apply)
        elif isinstance(v, list):
            for it in v:
                walk(it, k, stats, apply=apply)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = ap.parse_args()

    stats = {"changed": 0, "same": 0,
             "by_concept": collections.Counter(),
             "unresolved": collections.Counter()}
    files = sorted(glob.glob(str(COMPOSITES / "*.composite.json")))
    for f in files:
        d = json.load(open(f))
        # composites hold their nodes under "state"; some under top level
        root = d.get("state", d)
        for name, node in list(root.items()):
            walk(node, name, stats, apply=args.apply)
        if args.apply:
            json.dump(d, open(f, "w"), indent=2, ensure_ascii=False)

    print(f"composites: {len(files)}")
    print(f"glyphs changed: {stats['changed']}   already-current: {stats['same']}")
    print(f"distinct concepts used: {len(stats['by_concept'])}")
    if stats["unresolved"]:
        print("\nUNRESOLVED node names (kept their old glyph):")
        for name, c in stats["unresolved"].most_common():
            print(f"  {c:3d}  {name}")
    else:
        print("\nall glyph-bearing nodes resolved ✓")
    print("\n" + ("APPLIED" if args.apply else "DRY RUN — rerun with --apply to write"))


if __name__ == "__main__":
    main()
