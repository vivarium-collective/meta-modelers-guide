"""growth-division viz — bake the growth-and-division-spatial run into a GIF
(one CPM cell growing and dividing into a lineage, colored by cell id, over
the glucose field) plus a synced Plotly metrics panel (n_cells staircase +
total_volume). Mirrors ``tests/test_cpm_viz.py`` (flagship) and
``tests/test_cpm_colony_viz.py`` (colony) but for
``run_growth_division_frames``/the growth-division branch of ``metrics_panel``.
"""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from meta_modelers_guide.core import build_core
from meta_modelers_guide.cpm import viz

# Optional frameworks absent from the base CI image; skip rather than fail
# when the growth-division composite can't be built.
pytest.importorskip("cobra")
pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")

COMP = (Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
        / "growth-division-spatial.composite.json")


def test_growth_division_gif_and_metrics(tmp_path):
    core = build_core()
    state = json.loads(COMP.read_text())["state"]
    frames, metrics = viz.run_growth_division_frames(state, core, steps=36, cadence=3)

    assert len(frames) >= 6  # multiple frames captured

    assert "time" in metrics
    assert len(metrics["time"]) == len(frames)

    # population staircase: n_cells present, same length, ends >= it started
    # (the run may not divide on every seed, but the population never shrinks)
    assert "n_cells" in metrics
    assert len(metrics["n_cells"]) == len(frames)
    assert metrics["n_cells"][-1] >= metrics["n_cells"][0]

    assert "total_volume" in metrics
    assert len(metrics["total_volume"]) == len(frames)

    # per-cell volume arrays (optional but present here) are robust to cells
    # appearing mid-run: every series is padded to the shared time length.
    if "volume" in metrics and metrics["volume"]:
        for cid, series in metrics["volume"].items():
            assert len(series) == len(frames), f"volume[{cid}] length mismatch"

    gif = tmp_path / "growth_division.gif"
    viz.frames_to_gif(frames, gif)
    assert gif.exists() and gif.stat().st_size > 0

    panel = tmp_path / "growth_division_metrics.html"
    viz.metrics_panel(metrics, panel, include_plotlyjs="inline")
    assert panel.exists()
    html = panel.read_text()
    assert "plotly" in html.lower() and "<div" in html.lower()
