#!/usr/bin/env python
"""Run the Phase-4 whole cell and record the paper's full arc as a trajectory.

interface → cell–environment coupling → metabolism → viability → division /
disintegration, all in one composite (see viva_meta_modelers_guide/wholecell.py).
Writes workspace/reports/wholecell-trajectory.json and, if plotly is available, an
interactive figure beside it.
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite, gather_emitter_results

from viva_meta_modelers_guide.core import build_core
from viva_meta_modelers_guide.wholecell import build_whole_cell

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "workspace" / "reports"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    core = build_core()
    sim = Composite(build_whole_cell(), core=core)
    sim.run(20.0)
    rows = gather_emitter_results(sim)[("emitter",)]

    t = [r["time"] for r in rows]
    series = {k: [r[k] for r in rows]
              for k in ("biomass", "viability", "temperature", "cell_count", "debris")}
    (OUT / "wholecell-trajectory.json").write_text(
        json.dumps({"time": t, **series}, indent=2))

    div_t = next((r["time"] for r in rows if r["cell_count"] >= 2), None)
    print(f"whole cell run: peak biomass {max(series['biomass']):.2f}, "
          f"divided at t={div_t}, final debris {series['debris'][-1]:.2f}")

    try:
        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t, y=series["biomass"], name="biomass", line=dict(width=3, color="#0d6e6b")))
        fig.add_trace(go.Scatter(x=t, y=series["debris"], name="molecular debris", line=dict(width=2, color="#a5620f")))
        fig.add_trace(go.Scatter(x=t, y=series["viability"], name="viability", yaxis="y2", line=dict(width=2, dash="dot", color="#3f9e99")))
        fig.add_trace(go.Scatter(x=t, y=[c for c in series["cell_count"]], name="cell count", yaxis="y2", line=dict(width=2, dash="dash", color="#657572")))
        fig.update_layout(
            title="Whole cell: grow → divide → thermal shock → viability loss → disintegrate",
            xaxis_title="time", yaxis_title="biomass / debris",
            yaxis2=dict(title="viability · cell count", overlaying="y", side="right"),
            template="plotly_white")
        fig.write_html(str(OUT / "wholecell-trajectory.html"), include_plotlyjs="cdn")
        print(f"wrote {OUT/'wholecell-trajectory.html'}")
    except ImportError:
        pass
    print(f"wrote {OUT/'wholecell-trajectory.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
