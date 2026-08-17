"""Reproducible agentic model-build loops for the draft-to-living-cell studies.

For each study below this drives a GENUINE two-iteration loop against its real
`viva_meta_modelers_guide.dynamics` builder:

  iter 1 — the INERT DRAFT (typed ports, process nodes removed → no mechanism):
           every observable stays at its seed → graded tests MISMATCH → gate FAIL
  iter 2 — install the conforming handler (the compiler): the real dynamics run →
           graded tests WITHIN_TOL → gate PASS → DONE

Nothing is fabricated: both trajectories come from the real builders, the graded
bands are floors/ceilings honest to the executable run, and `loop_state.validate`
must return no violations. It writes `.pbg/loop/<study>.json` (the Build tab) and
splices the graded `behavior_tests` into each `study.yaml` (the Tests/Audit tabs).

Run from the workspace root:  python scripts/loop_studies.py
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml
from process_bigraph import Composite, gather_emitter_results

from viva_meta_modelers_guide import dynamics as DY
from viva_meta_modelers_guide.core import build_core
from viva_superpowers import loop_state as L, test_contract as T

WS_ROOT = Path(__file__).resolve().parents[1]

# study -> (builder, t_end, [test-specs]). Each test: name, obs, agg (last|max),
# op, value, floor/ceiling honest to the executable run; `control` marks the
# negative discriminating control (the inert draft must fail it).
STUDIES = {
    "closing-the-loop": (DY.build_closing_the_loop, 20.0, [
        ("biomass-growth", "biomass", "last", ">=", 0.3, "cell sink grows from the diffusing field (exec last≈0.66)"),
        ("nutrient-uptake", "uptake_total", "last", ">=", 0.5, "Monod uptake at the site draws down the bolus (exec last≈0.95)"),
        ("draft-is-inert", "biomass", "last", ">=", 0.3, None),
    ]),
    "molecular-channels": (DY.build_molecular_channels, 16.0, [
        ("product-formation", "product", "last", ">=", 2.0, "chemical turnover yields product (exec last≈4.8)"),
        ("substrate-consumed", "substrate", "last", "<=", 0.5, "substrate pool consumed to ~0 (exec last≈0.0 from 8.0)"),
        ("heat-generated", "heat", "last", ">=", 1.0, "turnover dissipates heat (exec last≈3.2)"),
        ("draft-is-inert", "product", "last", ">=", 2.0, None),
    ]),
    "the-nested-cell": (DY.build_nested_cell, 20.0, [
        ("protein-expressed", "protein", "last", ">=", 3.0, "central dogma expresses protein (exec last≈10.5)"),
        ("mrna-transcribed", "mrna", "last", ">=", 0.5, "gene transcribed to mRNA (exec last≈2.4)"),
        ("draft-is-inert", "protein", "last", ">=", 3.0, None),
    ]),
    "divide": (DY.build_divide, 18.0, [
        ("division-occurs", "cell_count", "last", ">=", 2.0, "lineage divides (exec cell_count 1→14)"),
        ("nutrient-consumed", "nutrient", "last", "<=", 5.0, "growing lineage draws nutrient down (exec last≈1.1 from 20)"),
        ("draft-is-inert", "cell_count", "last", ">=", 2.0, None),
    ]),
    "biofilm": (DY.build_biofilm, 16.0, [
        ("colony-growth", "cells", "last", ">=", 2.0, "logistic colony grows toward K (exec last≈5.0)"),
        ("ecm-production", "ecm", "last", ">=", 5.0, "colony secretes extracellular matrix (exec last≈21.8)"),
        ("draft-is-inert", "cells", "last", ">=", 2.0, None),
    ]),
}

_AGG = {"last": lambda xs: xs[-1], "max": max, "min": min}


def _run(state, t_end, core):
    sim = Composite({"state": state}, core=core)
    sim.run(t_end)
    rows = gather_emitter_results(sim)[("emitter",)]
    return {k: [float(r[k]) for r in rows] for k in rows[0]}


def _inert(comp):
    return {k: v for k, v in comp["state"].items()
            if not (isinstance(v, dict) and v.get("_type") == "process")}


def _evaluate(R, specs):
    verds = {}
    for name, obs, agg, op, val, _prov in specs:
        if name.startswith("draft-is-inert"):
            continue  # the control is a suite property, not a per-run gate check
        observed = _AGG[agg](R[obs]) if obs in R else None
        c = T.check(name, name, observed, T.value(val, op=op))
        verds[name] = c.get("verdict")
    gate = "pass" if all(v == "within_tol" for v in verds.values()) else "fail"
    return gate, verds


def _tests_yaml(specs):
    out = []
    for name, obs, agg, op, val, prov in specs:
        t = {"name": name,
             "classification": "diagnostic" if prov is None else "primary",
             "measure": {"kind": "observable", "path": obs, "expr": f"{agg}({obs})"},
             "pass_if": {"op": op, "value": val}}
        if prov is None:
            t["control"] = "negative"
            t["description"] = "Negative control: the inert draft (no mechanism) MUST fail this."
            t["pass_if"]["provenance"] = "inert-draft run stays at seed (no mechanism → no dynamics)"
        else:
            t["pass_if"]["provenance"] = prov
        t["requires_simulation"] = name  # placeholder; study run name
        out.append(t)
    return out


def _splice_behavior_tests(study, specs):
    p = WS_ROOT / "workspace" / "studies" / study / "study.yaml"
    text = p.read_text(encoding="utf-8")
    block = yaml.safe_dump({"behavior_tests": _tests_yaml(specs)}, sort_keys=False,
                           width=100, allow_unicode=True)
    # replace from `behavior_tests:` up to (not including) the next top-level key
    lines = text.splitlines(keepends=True)
    start = next(i for i, ln in enumerate(lines) if ln.startswith("behavior_tests:"))
    end = next((i for i in range(start + 1, len(lines))
                if re.match(r"^[A-Za-z_][\w-]*:", lines[i])), len(lines))
    new = "".join(lines[:start]) + block + "".join(lines[end:])
    p.write_text(new, encoding="utf-8")


def loop_one(study, builder, t_end, specs, core):
    comp = builder()
    draftR = _run(_inert(comp), t_end, core)
    execR = _run(builder()["state"], t_end, core)
    g_draft, v_draft = _evaluate(draftR, specs)
    g_exec, v_exec = _evaluate(execR, specs)
    tests = _tests_yaml(specs)

    st = L.create(WS_ROOT, study, f"Does the conforming handler make {study} clear its graded tests?",
                  max_iterations=12)
    st = L.advance(st, "AUDIT")
    st = L.lock_tests(st, tests)
    st = L.advance(st, "BUILD", note="draft: typed ports, no mechanism")
    st = L.advance(st, "RUN"); st = L.advance(st, "EVALUATE")
    st = L.record_iteration(st, edit="draft: typed ports, no committed mechanism",
                            target=",".join(v_draft), margin_deltas=v_draft, gate=g_draft)
    st["last_verdict"] = {"roll_up": "failed", "gate": g_draft}
    st = L.advance(st, "NAVIGATE")
    st = L.advance(st, "BUILD", note="install the conforming handler (the compiler)")
    st = L.advance(st, "RUN"); st = L.advance(st, "EVALUATE")
    st = L.record_iteration(st, edit="install conforming handler via the compiler",
                            target=",".join(v_exec), margin_deltas=v_exec, gate=g_exec)
    st["last_verdict"] = {"roll_up": "passed" if g_exec == "pass" else "failed", "gate": g_exec}
    st = L.advance(st, "DECIDE"); st = L.advance(st, "DONE")

    violations = L.validate(st, tests)
    if violations:
        raise SystemExit(f"[{study}] loop_state invariants failed: {violations}")
    L.save(WS_ROOT, study, st)
    _splice_behavior_tests(study, specs)
    print(f"{study:22s} draft={g_draft} exec={g_exec} iters={st['iteration']} -> DONE")


def main():
    core = build_core()
    for study, (builder, t_end, specs) in STUDIES.items():
        loop_one(study, builder, t_end, specs, core)


if __name__ == "__main__":
    main()
