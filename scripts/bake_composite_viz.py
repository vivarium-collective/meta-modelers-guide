#!/usr/bin/env python
"""Bake each composite's Visualization-step HTML for the READ-ONLY published loom.

A composite's Plotly viz + movie are rendered by an embedded Visualization step
*on run* (run_runner → render_results). A published static bundle has no run data,
so the read-only loom would show "run in a live dashboard". This script runs each
composite that carries a Visualization step through the workspace's own
``build_core`` and captures ``render_results`` into
``reports/composite-viz/<composite-id>.json`` ({viz_path: {html}}). ``publish.py``
copies those to ``api/composite-viz/`` and the loom fetches them in ``?static=1``
mode — so the read-only guide shows the interactive Plotly + movies with no run.

Commit the generated ``reports/composite-viz/*.json`` (they ARE the read-only
viz). Re-run whenever a composite's dynamics or viz change.
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite
from process_bigraph.visualization import render_results

from meta_modelers_guide.core import build_core

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "meta_modelers_guide" / "composites"
OUT = ROOT / "reports" / "composite-viz"
ID_PREFIX = "meta_modelers_guide.composites"

# Run length per composite (time units). Longer for the whole cell so its full
# grow→divide→die arc and the fig10 topology events are captured; 8 elsewhere,
# matching scripts/render_study_evidence.py's TOTAL_TIME.
DURATION = {"whole-cell": 20.0}
DEFAULT_DURATION = 8.0


def _has_viz_step(state: dict) -> bool:
    for v in state.values():
        if isinstance(v, dict) and v.get("_type") == "step":
            addr = str(v.get("address", ""))
            if "DynamicsPlot" in addr or "DynamicsMovie" in addr:
                return True
    return False


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for path in sorted(COMPOSITES.glob("*.composite.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        state = doc.get("state", {})
        if not _has_viz_step(state):
            continue
        stem = path.name.replace(".composite.json", "")
        try:
            core = build_core()
            sim = Composite({"state": state}, core=core)
            sim.run(DURATION.get(stem, DEFAULT_DURATION))
            rendered = render_results(sim)
        except Exception as exc:  # best-effort — a broken viz never breaks the bake
            print(f"  ✗ {stem}: {type(exc).__name__}: {exc}")
            continue
        out: dict[str, dict] = {}
        for vpath, payload in rendered.items():
            key = ".".join(str(p) for p in vpath)
            html = payload if isinstance(payload, str) else payload.get("html", "")
            if html:
                out[key] = {"html": html}
        if not out:
            print(f"  – {stem}: no viz HTML produced")
            continue
        (OUT / f"{ID_PREFIX}.{stem}.json").write_text(json.dumps(out))
        print(f"  ✓ {stem}: baked {len(out)} viz ({sum(len(v['html']) for v in out.values())//1024} KB)")
        n += 1
    print(f"\n{n} composites baked → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
