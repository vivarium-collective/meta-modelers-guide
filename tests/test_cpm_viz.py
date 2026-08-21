"""cpm_viz bakes a GIF of the CPM cell over its nutrient field + a synced metrics panel."""
from __future__ import annotations
import json, os
from pathlib import Path
import pytest
from process_bigraph import Composite
from meta_modelers_guide.core import build_core
from meta_modelers_guide.cpm import viz

# Optional frameworks absent from the base CI image (cpm needs a Rust/maturin build);
# skip rather than fail when the flagship composite can't be built.
pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")

COMP = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites" / "single-cell-in-a-field.composite.json"

def test_gif_and_metrics(tmp_path):
    core = build_core()
    state = json.loads(COMP.read_text())["state"]
    frames, metrics = viz.run_flagship_frames(state, core, steps=16, cadence=2)
    assert len(frames) >= 6                       # multiple frames captured
    assert set(("time","volume","local_nutrient","biomass")).issubset(metrics)
    assert len(metrics["biomass"]) == len(frames)
    gif = tmp_path / "run.gif"; viz.frames_to_gif(frames, gif)
    assert gif.exists() and gif.stat().st_size > 0
    panel = tmp_path / "metrics.html"; viz.metrics_panel(metrics, panel)
    assert panel.exists()
