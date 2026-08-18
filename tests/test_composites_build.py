"""Every figure composite must build against the workspace core.

The meta-modeler's-guide figures are *conceptual* (draft processes, no update
dynamics), so the real acceptance gate is structural: each ``*.composite.json``
resolves — every ``local:<Draft>`` address is registered and every typed store
leaf resolves — when built into a ``process_bigraph.Composite``.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from process_bigraph import Composite

from meta_modelers_guide.core import build_core

COMPOSITE_DIR = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
SPECS = sorted(COMPOSITE_DIR.glob("*.composite.json"))


def _ids(paths):
    return [p.name.replace(".composite.json", "") for p in paths]


def test_composites_present():
    assert SPECS, f"no composite specs found in {COMPOSITE_DIR}"


@pytest.mark.parametrize("spec_path", SPECS, ids=_ids(SPECS))
def test_composite_builds(spec_path):
    spec = json.loads(spec_path.read_text())
    assert spec.get("name"), f"{spec_path.name}: missing 'name'"
    assert spec.get("state"), f"{spec_path.name}: missing 'state'"
    core = build_core()
    # A build failure raises; that is the assertion.
    Composite({"state": spec["state"]}, core=core)
