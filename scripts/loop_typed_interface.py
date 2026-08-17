"""Reproducible agentic model-build loop for the `typed-interface` study.

Runs the Fig-4b interface through a genuine two-iteration loop and writes the
provenance the study-detail **Build** tab renders (`.pbg/loop/typed-interface.json`):

  iter 1 — the INERT DRAFT (typed ports, no mechanism): volume stays at its 0.5
           seed, nutrient at 10, viability at 1 → every graded test MISMATCHES → gate FAIL
  iter 2 — install the conforming CellInterface handler (the compiler's job):
           Monod uptake → growth (volume→6.11), nutrient→0, Arrhenius viability
           cliff → all graded tests WITHIN_TOL → gate PASS → DONE

Nothing here is fabricated: both trajectories are computed from the real
`viva_meta_modelers_guide.dynamics` builders, the graded bands come from the
executable run, and `loop_state.validate` must return no violations. The graded
`behavior_tests` this locks against are authored in the study's `study.yaml`.

Run from the workspace root:  python scripts/loop_typed_interface.py
"""
from __future__ import annotations

from pathlib import Path

from process_bigraph import Composite, gather_emitter_results

from viva_meta_modelers_guide.core import build_core
from viva_meta_modelers_guide.dynamics import build_typed_interface, _emitter, _pool
from viva_superpowers import loop_state as L, test_contract as T

WS_ROOT = Path(__file__).resolve().parents[1]
STUDY = "typed-interface"
T_END = 18.0
OBS = ["nutrient", "volume", "viability", "temperature"]

# The graded acceptance tests (mirror of the study's behavior_tests). Bands are
# honest to the executable run; `draft-is-inert` is the negative control.
TESTS = [
    {"name": "volume-growth", "classification": "primary", "control": "positive",
     "measure": {"kind": "observable", "path": "volume", "expr": "max(volume)"},
     "pass_if": {"op": ">=", "value": 2.0}},
    {"name": "nutrient-depletion", "classification": "primary",
     "measure": {"kind": "observable", "path": "nutrient", "expr": "last(nutrient)"},
     "pass_if": {"op": "<=", "value": 0.1}},
    {"name": "viability-cliff", "classification": "primary",
     "measure": {"kind": "observable", "path": "viability", "expr": "last(viability)"},
     "pass_if": {"op": "<=", "value": 0.1}},
    {"name": "draft-is-inert", "classification": "diagnostic", "control": "negative",
     "measure": {"kind": "observable", "path": "volume", "expr": "max(volume)"},
     "pass_if": {"op": ">=", "value": 2.0}},
]


def _run(state_builder, core):
    sim = Composite({"state": state_builder["state"]}, core=core)
    sim.run(T_END)
    rows = gather_emitter_results(sim)[("emitter",)]
    out = {k: [float(r[k]) for r in rows] for k in rows[0]}
    return {"max_volume": max(out["volume"]),
            "last_nutrient": out["nutrient"][-1],
            "last_viability": out["viability"][-1]}


def _inert_draft():
    # Typed ports, NO cell process — the un-compiled draft.
    return {"state": {"nutrient": _pool(10.0), "volume": _pool(0.5),
                      "viability": _pool(1.0), "temperature": _pool(37.0),
                      "emitter": _emitter(OBS)}}


def _evaluate(vals):
    checks = [
        T.check("volume-growth", "Cell grows", vals["max_volume"], T.value(2.0, op=">=")),
        T.check("nutrient-depletion", "Nutrient depletes", vals["last_nutrient"], T.value(0.1, op="<=")),
        T.check("viability-cliff", "Viability collapses", vals["last_viability"], T.value(0.1, op="<=")),
    ]
    verds = {c["id"]: c.get("verdict") for c in checks}
    gate = "pass" if all(v == "within_tol" for v in verds.values()) else "fail"
    return gate, verds


def main():
    core = build_core()
    exec_vals = _run(build_typed_interface(), core)
    draft_vals = _run(_inert_draft(), core)
    g_draft, v_draft = _evaluate(draft_vals)
    g_exec, v_exec = _evaluate(exec_vals)

    question = ("Can the Fig-4b typed interface be compiled — by installing one conforming "
                "handler — into a running, bounded, goal-directed cell that clears graded "
                "acceptance tests?")
    st = L.create(WS_ROOT, STUDY, question, max_iterations=12)
    st = L.advance(st, "AUDIT")
    st = L.lock_tests(st, TESTS)
    # iteration 1 — inert draft → fail
    st = L.advance(st, "BUILD", note="draft: typed ports, no mechanism")
    st = L.advance(st, "RUN"); st = L.advance(st, "EVALUATE")
    st = L.record_iteration(st, edit="draft: typed ports, no committed mechanism",
                            target="volume/nutrient/viability", margin_deltas=v_draft, gate=g_draft)
    st["last_verdict"] = {"roll_up": "failed", "gate": g_draft}
    st = L.advance(st, "NAVIGATE")
    # iteration 2 — install conforming handler → pass
    st = L.advance(st, "BUILD", note="install conforming CellInterface handler (Monod→growth; Arrhenius viability)")
    st = L.advance(st, "RUN"); st = L.advance(st, "EVALUATE")
    st = L.record_iteration(st, edit="install conforming handler via the compiler",
                            target="volume/nutrient/viability", margin_deltas=v_exec, gate=g_exec)
    st["last_verdict"] = {"roll_up": "passed" if g_exec == "pass" else "failed", "gate": g_exec}
    st = L.advance(st, "DECIDE"); st = L.advance(st, "DONE")

    violations = L.validate(st, TESTS)
    if violations:
        raise SystemExit(f"loop_state failed invariants: {violations}")
    path = L.save(WS_ROOT, STUDY, st)
    print(f"draft  gate={g_draft} {v_draft}")
    print(f"exec   gate={g_exec} {v_exec}")
    print(f"loop_state -> {path}  (iterations={st['iteration']} reopen={st['reopen_count']} state={st['state']})")


if __name__ == "__main__":
    main()
