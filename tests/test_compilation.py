"""The semantic→executable compiler obeys its four laws for every figure env.

1. conformance — each env's handlers satisfy their signatures;
2. interface preservation — compile keeps ports + wired store paths identical;
3. executability — the compiled composite builds AND runs with non-trivial dynamics;
4. handler independence — Fig 6's two envs share one interface (different handlers).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from process_bigraph import Composite

from viva_meta_modelers_guide.core import build_core
from viva_meta_modelers_guide.compile import (
    compile_composite, check_conformance, interface_of, _refined_ports, _is_rewrite,
)
from viva_meta_modelers_guide.handler_envs import ENVS

# scripts/ is not a package; load the BUILD table directly.
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "build_executables",
    Path(__file__).resolve().parent.parent / "scripts" / "build_executables.py")
_be = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_be)

COMPOSITES = Path(__file__).resolve().parent.parent / "viva_meta_modelers_guide" / "composites"
CASES = [(e, s, o) for (e, s, o) in _be.BUILD if e in ENVS]


def _semantic(stem):
    return json.loads((COMPOSITES / f"{stem}.composite.json").read_text())["state"]


@pytest.mark.parametrize("env_name,sem_stem,out_stem", CASES,
                         ids=[c[2] for c in CASES])
def test_env_conforms_compiles_and_runs(env_name, sem_stem, out_stem):
    core = build_core()
    sem = _semantic(sem_stem)

    # 1. conformance — every handled draft's handler satisfies its signature,
    #    allowing the env's declared store refinements (e.g. scalar→grid, Fig 5).
    refined = _refined_ports(sem, ENVS[env_name])
    for draft, spec in ENVS[env_name].items():
        # Rewrite handlers (Fig 10) conform against the node's WIRING, not the
        # draft's placeholder signature (law 2′); compile_composite below enforces
        # that. Signature conformance applies to the ordinary handlers.
        if _is_rewrite(core, spec["handler"]):
            continue
        rep = check_conformance(core, draft, spec["handler"],
                                allow_refine=refined.get(draft, set()))
        assert rep.ok, str(rep)

    ex = compile_composite(sem, ENVS[env_name], core)

    # 2. interface preservation.
    assert interface_of(sem) == interface_of(ex), f"{out_stem}: interface changed"

    # 3. executability — builds and produces non-trivial dynamics.
    comp = Composite({"state": ex}, core=core)
    before = _observables(comp)
    comp.run(10)
    after = _observables(comp)
    assert any(abs(after[k] - before[k]) > 1e-9 for k in before), \
        f"{out_stem}: no observable changed over the run"


def test_fig6_handler_independence():
    """Law #4: two conforming handler sets, one interface, different dynamics."""
    if "fig06-coarse" not in ENVS or "fig06-kinetic" not in ENVS:
        pytest.skip("fig06 envs not present")
    core = build_core()
    sem = _semantic("fig06-disintegration")
    coarse = compile_composite(sem, ENVS["fig06-coarse"], core)
    kinetic = compile_composite(sem, ENVS["fig06-kinetic"], core)
    assert interface_of(coarse) == interface_of(kinetic) == interface_of(sem)

    def run(state):
        c = Composite({"state": state}, core=core)
        c.run(10)
        return c.state["coarse"]["biomass"]
    assert abs(run(coarse) - run(kinetic)) > 1e-6, "handlers gave identical dynamics"


def test_fig10_division_is_event_driven():
    """Fig 10-1: division is a discrete event. Before the cell-cycle time nothing
    partitions; after it, the parent biomass splits into the two daughters and the
    cell count increments (a rewrite realised over the run). Interface preserved."""
    if "fig10-1" not in ENVS:
        pytest.skip("fig10-1 env not present")
    core = build_core()
    sem = _semantic("fig10-1-division")
    ex = compile_composite(sem, ENVS["fig10-1"], core)
    assert interface_of(ex) == interface_of(sem)          # law 2 still holds

    # division_time defaults to 5.0; run short (< event) then long (> event).
    early = Composite({"state": compile_composite(sem, ENVS["fig10-1"], core)}, core=core)
    early.run(3)
    assert early.state["environ"]["cell_count"] == 1.0     # not yet divided
    assert early.state["environ"]["daughter_1"]["biomass"] == 0.0

    late = Composite({"state": compile_composite(sem, ENVS["fig10-1"], core)}, core=core)
    late.run(10)
    assert late.state["environ"]["cell_count"] == 2.0       # divided once
    d1 = late.state["environ"]["daughter_1"]["biomass"]
    d2 = late.state["environ"]["daughter_2"]["biomass"]
    assert d1 > 0 and abs(d1 - d2) < 1e-9                   # partitioned equally


def test_rewrite_conformance_against_wiring():
    """A rewrite handler (Divide) whose draft signature is a placeholder still
    compiles, because conformance is checked against the node's wiring."""
    if "fig10-1" not in ENVS:
        pytest.skip("fig10-1 env not present")
    core = build_core()
    assert _is_rewrite(core, "DivisionRewrite")
    # compile_composite raises CompileError on non-conformance; reaching a built
    # Composite proves the wiring-conformance path accepted the rewrite handler.
    sem = _semantic("fig10-1-division")
    Composite({"state": compile_composite(sem, ENVS["fig10-1"], core)}, core=core)


def _observables(comp):
    """Flatten the composite's numeric store leaves into a {path: value} dict."""
    out = {}

    def walk(node, path=()):
        if isinstance(node, dict):
            for k, v in node.items():
                if k.startswith("_") or (isinstance(v, dict) and v.get("_type") == "process"):
                    continue
                walk(v, path + (k,))
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            out[".".join(path)] = float(node)

    walk(comp.state)
    return out
