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


# Pure DRAFT figure signatures (the published a/b figure b-panels) are typed
# INTERFACES, not runnable composites: they use placeholder / unregistered types
# (e.g. `grain`, BigraphLink no-ops) and are not expected to build as a Composite.
# Their runnable models are the figNN-runnable composites (runnable-figures rollout,
# spec docs/superpowers/specs/2026-08-26-runnable-figures-deep-pass-design.md), which
# DO build + run and carry the dynamics/viz/tests. xfail the drafts rather than
# assert they build as executables.
DRAFT_SIGNATURES = {
    "fig01a-process", "fig01b-store-hierarchy", "fig01c-bio-bigraph", "fig01d-process",
    "fig05b-grain-swap", "fig07-nested-hierarchy",
    # legacy conceptual drafts (used by the `overview` study) that main's figure
    # restructure superseded; unbuildable under the merged type system — the
    # runnable models are fig01-runnable / fig02-runnable.
    "fig01-process-bigraph", "overview-multiscale-composite",
}


@pytest.mark.parametrize("spec_path", SPECS, ids=_ids(SPECS))
def test_composite_builds(spec_path):
    if spec_path.name.split(".")[0] in DRAFT_SIGNATURES:
        pytest.xfail(f"{spec_path.name.split('.')[0]}: pure draft signature — runnable model is its figNN-runnable")
    raw = spec_path.read_text()
    # Composites that compose the spatial frameworks (cpm, spatio_flux) can only be
    # built where those optional deps are installed; skip elsewhere (e.g. base CI).
    if "spatio_flux" in raw:
        pytest.importorskip("spatio_flux")
    if "CpmCellField" in raw or "CpmColonyField" in raw:
        pytest.importorskip("cpm")
        # CpmCellField loads a cobra model at construction ONLY for its default
        # dFBA mechanism; the Michaelis-Menten mechanism ("mechanism": "mm") is
        # cobra-free (the interface-substitutability twin), so require cobra only
        # when this composite does not select the mm mechanism.
        if '"mechanism": "mm"' not in raw and '"mechanism":"mm"' not in raw:
            pytest.importorskip("cobra")
    if "CpmDisintegration" in raw:
        pytest.importorskip("cpm")           # no cobra — disintegration is metabolism-free
    if "CpmGrowthDivision" in raw:
        pytest.importorskip("cpm")
        pytest.importorskip("cobra")  # dFBA-driven growth
    if "CpmEvolution" in raw:
        pytest.importorskip("cpm")
        pytest.importorskip("cobra")  # dFBA-driven growth
    if "CpmSorting" in raw:
        pytest.importorskip("cpm")           # no cobra — sorting is metabolism-free too
    spec = json.loads(raw)
    assert spec.get("name"), f"{spec_path.name}: missing 'name'"
    assert spec.get("state"), f"{spec_path.name}: missing 'state'"
    core = build_core()
    # A build failure raises; that is the assertion.
    Composite({"state": spec["state"]}, core=core)
