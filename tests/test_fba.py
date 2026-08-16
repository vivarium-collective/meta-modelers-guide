"""Phase 2 · the real FBA handler (COBRApy) conforms to the Fig 6 metabolism
signature and gives a third, real mechanism over the same interface (law 4).

Skipped when the optional ``cobra`` dependency is absent.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("cobra")  # entire module skips without COBRApy

from process_bigraph import Composite

from viva_meta_modelers_guide.core import build_core
from viva_meta_modelers_guide.compile import (
    compile_composite, check_conformance, interface_of,
)
from viva_meta_modelers_guide.handler_envs import ENVS

COMPOSITES = Path(__file__).resolve().parent.parent / "viva_meta_modelers_guide" / "composites"


def _sem():
    return json.loads((COMPOSITES / "fig06-disintegration.composite.json").read_text())["state"]


def test_fba_conforms_to_metabolism_signature():
    core = build_core()
    rep = check_conformance(core, "CoarseGrainedMetabolism", "FBAMetabolism")
    assert rep.ok, str(rep)


def test_fba_runs_and_tracks_nutrient():
    core = build_core()
    ex = compile_composite(_sem(), ENVS["fig06-fba"], core)
    assert interface_of(ex) == interface_of(_sem())      # law 2
    comp = Composite({"state": ex}, core=core)
    comp.run(10)
    # real FBA converts the nutrient supply into biomass flux → biomass accumulates.
    assert comp.state["coarse"]["biomass"] > 0


def test_law4_three_handlers_one_interface():
    """Coarse (linear), kinetic (saturating), and FBA (LP) — three mechanisms, one
    interface, all conforming; at least two give distinct biomass."""
    core = build_core()
    sem = _sem()
    outs = {}
    for env in ("fig06-coarse", "fig06-kinetic", "fig06-fba"):
        ex = compile_composite(sem, ENVS[env], core)
        assert interface_of(ex) == interface_of(sem)
        c = Composite({"state": ex}, core=core)
        c.run(10)
        outs[env] = c.state["coarse"]["biomass"]
    assert len({round(v, 6) for v in outs.values()}) >= 2, outs
