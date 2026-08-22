"""Law 1 (conformance) demonstrated NATIVELY at the Fig 4b cellular interface.

Previously the cellular-interface study proved Law 1 only by cross-referencing the
metabolism-signature impostor (`NonConformingMetabolism`, handlers_fig06_fba.py),
which breaks a *different* contract. This exercises the cellular interface's OWN
impostor (`NonConformingCellularInterface`): a handler that drops the required
`viability`/`objective` ports must be rejected by the compiler with a
`CompileError` naming exactly those missing ports.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from meta_modelers_guide.core import build_core
from meta_modelers_guide.compile import (
    CompileError,
    check_conformance,
    compile_composite,
)

COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"


def _semantic(stem):
    return json.loads((COMPOSITES / f"{stem}.composite.json").read_text())["state"]


def test_native_impostor_fails_conformance():
    core = build_core()
    rep = check_conformance(core, "CellularInterface", "NonConformingCellularInterface")
    assert not rep.ok, "impostor missing viability/objective should NOT conform"
    assert "viability" in str(rep) and "objective" in str(rep), str(rep)


def test_native_impostor_rejected_by_compiler():
    """The type judgment as a scene, native to Fig 4b: installing the impostor
    handler for the CellularInterface draft raises CompileError naming the
    dropped ports."""
    core = build_core()
    sem = _semantic("fig04b-cellular-interface")
    env = {
        "CellularInterface": {
            "handler": "NonConformingCellularInterface",
            "config": {},
            "init": {},
        }
    }
    with pytest.raises(CompileError) as ei:
        compile_composite(sem, env, core)
    msg = str(ei.value)
    assert "viability" in msg and "objective" in msg, msg


def test_conforming_handler_still_conforms():
    """Guardrail: the real handler must still conform (the impostor test above is
    only meaningful if the contract otherwise accepts a valid handler)."""
    core = build_core()
    rep = check_conformance(core, "CellularInterface", "CellularInterfaceHandler")
    assert rep.ok, str(rep)
