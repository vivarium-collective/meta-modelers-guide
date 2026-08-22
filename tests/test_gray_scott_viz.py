"""molecular-interfaces (Gray-Scott) viz — bake the flagship Turing-pattern
composite into a GIF (near-uniform seed -> emergent reaction-diffusion
pattern) plus a synced Plotly metrics panel. Mirrors
``tests/test_protocell_viz.py``/``tests/test_cahn_hilliard`` conventions but
for ``run_gray_scott_frames``/the ``gray_scott`` branch of ``metrics_panel``.

Run directly from the composite's JSON spec in
``meta_modelers_guide/composites/molecular-turing-pattern.composite.json``
(not hand-built state), matching ``tests/test_molecular_regime.py``'s
convention -- ``steps=16, cadence=1`` (the module's default) matches that
regression test's already-validated ``N_TICKS=16`` * ``steps_per_tick=500`` =
8000 total internal steps, comfortably inside the window where the flagship
composite is known to pattern (``test_turing_pattern_forms``).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("process_bigraph")

from meta_modelers_guide.core import build_core  # noqa: E402
from meta_modelers_guide.cpm import viz  # noqa: E402
from meta_modelers_guide.molecular.gray_scott import PATTERN_FLOOR  # noqa: E402

COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"


def _state(name: str) -> dict:
    return json.loads((COMPOSITES / f"{name}.composite.json").read_text())["state"]


def test_turing_pattern_emerges(tmp_path):
    core = build_core()
    state = _state("molecular-turing-pattern")
    frames, metrics = viz.run_gray_scott_frames(state, core, steps=16, cadence=1)

    assert len(frames) >= 6

    for key in ("time", "v_var", "n_domains"):
        assert key in metrics, f"missing metric {key}"
        assert len(metrics[key]) == len(frames), f"{key} length mismatch"

    # the flagship differential-diffusion regime patterns: v_var ends well
    # above the near-uniform-seed pattern floor.
    assert metrics["v_var"][-1] > PATTERN_FLOOR
    assert metrics["v_var"][-1] > 0

    gif = tmp_path / "molecular-turing-pattern.gif"
    viz.frames_to_gif(frames, gif)
    assert gif.exists() and gif.stat().st_size > 0

    panel = tmp_path / "molecular-metrics.html"
    viz.metrics_panel(metrics, panel, include_plotlyjs="inline")
    assert panel.exists()
    html = panel.read_text()
    assert "plotly" in html.lower() and "<div" in html.lower()


def test_equal_diffusion_control_stays_flat(tmp_path):
    """Sanity check for the panel/frames shape on the causal control (no
    differential diffusion) -- not a re-probe of the metastability boundary,
    just confirming the renderer handles a run that never patterns."""
    core = build_core()
    state = _state("molecular-equal-diffusion-control")
    frames, metrics = viz.run_gray_scott_frames(state, core, steps=16, cadence=1)

    assert len(frames) >= 6
    assert len(metrics["v_var"]) == len(frames)
    assert metrics["v_var"][-1] == pytest.approx(0.0, abs=1e-6)
