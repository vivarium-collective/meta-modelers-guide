"""cellular-interface-spatial viz — bake the spatial translation of the
cellular-interface study (the UNCHANGED ``CellularInterfaceHandler`` composed
with a real 2D spatio-flux ``DiffusionAdvection`` chemical field via the
``FieldPointCoupling`` field-point adapter) into a GIF (chemical field
heatmap + the cell's fixed footprint, with a running mini-panel of sensed
``chemical_ext`` and ``growth_rate``) plus a synced Plotly metrics panel.
Mirrors ``tests/test_gray_scott_viz.py``/``tests/test_protocell_viz.py`` but
for ``run_cellular_interface_spatial_frames``/the
``cellular_interface_spatial`` branch of ``metrics_panel``.

Run directly from the composite's JSON spec in
``meta_modelers_guide/composites/cellular-interface-spatial.composite.json``
(not hand-built state), matching ``tests/test_cellular_interface_spatial.py``'s
convention. Skipped when the optional ``spatio_flux`` dependency is absent
(no cobra here -- the handler's chemistry is a lumped Monod law, not an FBA
model), same guard as that regression test.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("spatio_flux")  # composes DiffusionAdvection; absent from base CI

from meta_modelers_guide.core import build_core  # noqa: E402
from meta_modelers_guide.cpm import viz  # noqa: E402

COMP = (
    Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
    / "cellular-interface-spatial.composite.json"
)


def _state() -> dict:
    return json.loads(COMP.read_text())["state"]


def test_cellular_interface_spatial_gif_and_metrics(tmp_path):
    core = build_core()
    state = _state()
    frames, metrics = viz.run_cellular_interface_spatial_frames(state, core, steps=24, cadence=1)

    # 20-30 ticks, per the composite's field-point-coupling demonstration.
    assert 20 <= len(frames) <= 30

    for key in ("time", "chemical_ext", "growth_rate", "field_total"):
        assert key in metrics, f"missing metric {key}"
        assert len(metrics[key]) == len(frames), f"{key} length mismatch"

    # niche construction: the field's total mass falls (net uptake removes
    # real chemical faster than diffusion resupplies the footprint).
    assert metrics["field_total"][-1] < metrics["field_total"][0]

    # the unchanged interface actually senses + grows on the spatial field.
    assert metrics["chemical_ext"][-1] > 0.0
    assert metrics["growth_rate"][-1] > 0.0

    gif = tmp_path / "cellular-interface-spatial.gif"
    viz.frames_to_gif(frames, gif)
    assert gif.exists() and gif.stat().st_size > 0

    panel = tmp_path / "cellular-interface-spatial-metrics.html"
    viz.metrics_panel(metrics, panel, include_plotlyjs="inline")
    assert panel.exists()
    html = panel.read_text()
    assert "plotly" in html.lower() and "<div" in html.lower()
