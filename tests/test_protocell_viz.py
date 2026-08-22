"""protocell/autopoiesis viz — bake the closed-loop and control composites
into GIFs (the membrane holding its ring vs. dissolving) plus a synced
Plotly metrics panel. Mirrors ``tests/test_disintegration_viz.py`` and
``tests/test_cpm_viz.py`` but for ``run_protocell_frames``/the ``protocell``
branch of ``metrics_panel``.

Both composites are run directly from their JSON specs in
``meta_modelers_guide/composites/`` (not hand-built state), matching
``tests/test_autopoiesis_regime.py``'s convention. ``steps=36, cadence=6``
(the module's default) matches that regression test's already-validated
closed-loop margin -- 1800 internal RD steps, comfortably inside the
~2000-step homeostatic-plateau window -- so this stays a viz-shape test, not
a re-probe of the metastability boundary.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("process_bigraph")

from meta_modelers_guide.core import build_core  # noqa: E402
from meta_modelers_guide.cpm import viz  # noqa: E402

COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"


def _state(name: str) -> dict:
    return json.loads((COMPOSITES / f"{name}.composite.json").read_text())["state"]


def test_autopoietic_membrane_holds(tmp_path):
    core = build_core()
    state = _state("protocell-autopoietic")
    frames, metrics = viz.run_protocell_frames(state, core, steps=36, cadence=6)

    assert len(frames) >= 6

    for key in ("time", "enclosed_area", "membrane_mass"):
        assert key in metrics, f"missing metric {key}"
        assert len(metrics[key]) == len(frames), f"{key} length mismatch"

    # the closed autopoietic loop self-maintains within the metastable
    # window: the enclosed interior never vanishes.
    assert metrics["enclosed_area"][-1] > 0

    gif = tmp_path / "protocell-autopoietic.gif"
    viz.frames_to_gif(frames, gif)
    assert gif.exists() and gif.stat().st_size > 0

    panel = tmp_path / "autopoiesis-metrics.html"
    viz.metrics_panel(metrics, panel, include_plotlyjs="inline")
    assert panel.exists()
    html = panel.read_text()
    assert "plotly" in html.lower() and "<div" in html.lower()


def test_vesicle_control_dissolves(tmp_path):
    core = build_core()
    state = _state("protocell-vesicle-control")
    frames, metrics = viz.run_protocell_frames(state, core, steps=36, cadence=6)

    assert len(frames) >= 6
    assert len(metrics["enclosed_area"]) == len(frames)

    # no production feedback holding the boundary together: the ring
    # dissipates via plain decay+diffusion and the interior stops being
    # topologically enclosed.
    assert metrics["enclosed_area"][-1] == 0

    gif = tmp_path / "protocell-vesicle-control.gif"
    viz.frames_to_gif(frames, gif)
    assert gif.exists() and gif.stat().st_size > 0
