"""disintegration viz — bake the disintegration-spatial run into a GIF (the CPM
cell dissolving over the stressor field, shedding a scattering debris cloud of
particles) plus a synced Plotly metrics panel. Mirrors ``tests/test_cpm_viz.py``
(flagship) and ``tests/test_cpm_colony_viz.py`` (colony) but for
``run_disintegration_frames``/the disintegration branch of ``metrics_panel``.
"""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from meta_modelers_guide.core import build_core
from meta_modelers_guide.cpm import viz

# Optional frameworks absent from the base CI image; skip rather than fail
# when the disintegration composite can't be built.
pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")

COMP = (Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
        / "disintegration-spatial.composite.json")


def test_disintegration_gif_and_metrics(tmp_path):
    core = build_core()
    state = json.loads(COMP.read_text())["state"]
    frames, metrics = viz.run_disintegration_frames(state, core, steps=18, cadence=1)

    assert len(frames) >= 6  # multiple frames captured

    for key in ("time", "area", "mean_stressor", "n_particles", "n_components"):
        assert key in metrics, f"missing metric {key}"
        assert len(metrics[key]) == len(frames), f"{key} length mismatch"

    # by the end of an 18-step run the cell has released and shed debris
    assert metrics["n_particles"][-1] > 0

    gif = tmp_path / "disintegration.gif"
    viz.frames_to_gif(frames, gif)
    assert gif.exists() and gif.stat().st_size > 0

    panel = tmp_path / "disintegration_metrics.html"
    viz.metrics_panel(metrics, panel, include_plotlyjs="inline")
    assert panel.exists()
    html = panel.read_text()
    assert "plotly" in html.lower() and "<div" in html.lower()
