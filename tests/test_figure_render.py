"""Every composite renders to a non-empty, well-formed paper-styled SVG."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pbg_meta_modelers_guide.core import build_core
from pbg_meta_modelers_guide.figure_render import render_composite

COMPOSITE_DIR = Path(__file__).resolve().parent.parent / "workspace" / "composites"
SPECS = sorted(COMPOSITE_DIR.glob("*.composite.json"))


@pytest.mark.parametrize("spec_path", SPECS, ids=[p.stem.replace(".composite", "") for p in SPECS])
def test_composite_renders(spec_path):
    spec = json.loads(spec_path.read_text())
    svg = render_composite(spec["state"], build_core(), title=spec["name"])
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    # each figure must draw at least one process box and one store node
    assert "DRAFT · mechanism unspecified" in svg, "no process rendered"
    assert svg.count("<rect") > 3, "too few nodes drawn"
