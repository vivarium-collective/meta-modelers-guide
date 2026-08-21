"""sorting/CH viz — bake the sorting study's cell-type-colored GIF (two cell
colors demixing over ~600 MCS) + the condensate study's phi-field GIF (phase
separation), each with a synced Plotly metrics panel. Mirrors
``tests/test_cpm_viz.py``/``test_cpm_colony_viz.py``/
``test_disintegration_viz.py`` but for ``run_sorting_frames``/
``run_cahn_hilliard_frames`` and the corresponding branches of
``metrics_panel``.
"""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from meta_modelers_guide.core import build_core
from meta_modelers_guide.cpm import viz

# CpmSorting needs the `cpm` Rust/maturin build, absent from the base CI
# image; skip rather than fail when neither composite can be built.
pytest.importorskip("cpm")

SORTING_COMP = (Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
                / "cell-sorting-spatial.composite.json")
CH_COMP = (Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
           / "condensate-cahn-hilliard.composite.json")


def test_sorting_gif_and_metrics(tmp_path):
    core = build_core()
    state = json.loads(SORTING_COMP.read_text())["state"]
    # steps=60, cadence=5 -> 12 ticks * comp.run(5) = 60 update() calls total,
    # each running mcs=10 CPM steps -> 600 total MCS (matches the verified
    # test_cpm_sorting.py run that collapses hetero_frac below 0.2).
    frames, metrics = viz.run_sorting_frames(state, core, steps=60, cadence=5)

    assert len(frames) >= 6  # multiple frames captured

    for key in ("time", "hetero_frac", "cell_pixels"):
        assert key in metrics, f"missing metric {key}"
        assert len(metrics[key]) == len(frames), f"{key} length mismatch"

    # demixing: hetero_frac must end below where it started
    assert metrics["hetero_frac"][-1] < metrics["hetero_frac"][0]

    gif = tmp_path / "sorting.gif"
    viz.frames_to_gif(frames, gif)
    assert gif.exists() and gif.stat().st_size > 0

    panel = tmp_path / "sorting_metrics.html"
    viz.metrics_panel(metrics, panel, include_plotlyjs="inline")
    assert panel.exists()
    html = panel.read_text()
    assert "plotly" in html.lower() and "<div" in html.lower()


def test_cahn_hilliard_gif_and_metrics(tmp_path):
    core = build_core()
    state = json.loads(CH_COMP.read_text())["state"]
    # steps=35, cadence=5 -> 7 ticks * comp.run(5) = 35 update() calls total,
    # each running steps_per_tick=200 CH steps -> 7000 total CH steps, well
    # past the ~5000-step mark where phi_var is already clearly rising (see
    # condensate/cahn_hilliard.py's stability note: ~0.11 by 5000 steps).
    frames, metrics = viz.run_cahn_hilliard_frames(state, core, steps=35, cadence=5)

    assert len(frames) >= 6  # multiple frames captured

    for key in ("time", "phi_var"):
        assert key in metrics, f"missing metric {key}"
        assert len(metrics[key]) == len(frames), f"{key} length mismatch"

    # phase separation: phi_var must end above where it started
    assert metrics["phi_var"][-1] > metrics["phi_var"][0]

    gif = tmp_path / "condensate.gif"
    viz.frames_to_gif(frames, gif)
    assert gif.exists() and gif.stat().st_size > 0

    panel = tmp_path / "condensate_metrics.html"
    viz.metrics_panel(metrics, panel, include_plotlyjs="inline")
    assert panel.exists()
    html = panel.read_text()
    assert "plotly" in html.lower() and "<div" in html.lower()
