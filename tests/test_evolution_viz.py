"""development-and-evolution viz — bake the `development-evolution-spatial`
run into a GIF (the growing CPM colony, each cell's footprint FILLED by a
continuous colormap of its heritable trait `vmax` on a FIXED scale, so the
audience watches the trait distribution SHIFT under selection while the
colony develops core-vs-rim structure) plus a synced Plotly metrics panel
(`mean_vmax` rising + `rim_core_ratio`). Mirrors
``tests/test_growth_division_viz.py`` but for `run_evolution_frames`/the
`"evolution"` branch of `metrics_panel`.
"""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from meta_modelers_guide.core import build_core
from meta_modelers_guide.cpm import viz

# Optional frameworks absent from the base CI image; skip rather than fail
# when the development-evolution composite can't be built.
pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")
pytest.importorskip("cobra")

COMP = (Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
        / "development-evolution-spatial.composite.json")


def test_evolution_gif_and_metrics(tmp_path):
    core = build_core()
    state = json.loads(COMP.read_text())["state"]
    frames, metrics = viz.run_evolution_frames(state, core, steps=45, cadence=5)

    assert len(frames) >= 6  # multiple frames captured

    assert "time" in metrics
    assert len(metrics["time"]) == len(frames)

    # evolution: population mean trait present, ends above where it started
    # (selection ON — the whole point of the flagship composite).
    assert "mean_vmax" in metrics
    assert len(metrics["mean_vmax"]) == len(frames)
    assert metrics["mean_vmax"][-1] > metrics["mean_vmax"][0]

    # development: radial core-vs-rim heterogeneity present, same length.
    assert "rim_core_ratio" in metrics
    assert len(metrics["rim_core_ratio"]) == len(frames)

    assert "var_vmax" in metrics
    assert "n_cells" in metrics
    assert len(metrics["n_cells"]) == len(frames)

    gif = tmp_path / "evolution.gif"
    viz.frames_to_gif(frames, gif)
    assert gif.exists() and gif.stat().st_size > 0

    panel = tmp_path / "evolution_metrics.html"
    viz.metrics_panel(metrics, panel, include_plotlyjs="inline")
    assert panel.exists()
    html = panel.read_text()
    assert "plotly" in html.lower() and "<div" in html.lower()
