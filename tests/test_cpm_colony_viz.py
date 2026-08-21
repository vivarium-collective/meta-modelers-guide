"""cpm colony viz — bake a colony (N-cell) CPM run into a GIF (cells over the
shared nutrient field(s), colored by cell id) plus a synced per-cell Plotly
metrics panel. Mirrors ``tests/test_cpm_viz.py`` (flagship) but for
``run_colony_frames``/the per-cell branch of ``metrics_panel``.
"""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from meta_modelers_guide.core import build_core
from meta_modelers_guide.cpm import viz

# Optional frameworks absent from the base CI image; skip rather than fail
# when the colony composite can't be built.
pytest.importorskip("cobra")
pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")

COMP = (Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
        / "cellcell-crossfeed.composite.json")


def test_colony_gif_and_percell_metrics(tmp_path):
    core = build_core()
    state = json.loads(COMP.read_text())["state"]
    frames, metrics = viz.run_colony_frames(state, core, steps=16, cadence=2)

    assert len(frames) >= 6  # multiple frames captured

    assert "time" in metrics
    assert len(metrics["time"]) == len(frames)

    # per-cell arrays present for both ids (secretor=1, consumer=2), equal length
    for key in ("biomass", "volume", "local_glucose", "local_acetate"):
        assert key in metrics
        assert set(metrics[key]) == {"1", "2"}
        for cid, series in metrics[key].items():
            assert len(series) == len(frames), f"{key}[{cid}] length mismatch"

    gif = tmp_path / "colony.gif"
    viz.frames_to_gif(frames, gif)
    assert gif.exists() and gif.stat().st_size > 0

    panel = tmp_path / "colony_metrics.html"
    viz.metrics_panel(metrics, panel, include_plotlyjs="inline")
    assert panel.exists()
    html = panel.read_text()
    assert "plotly" in html.lower() or "<div" in html.lower()
