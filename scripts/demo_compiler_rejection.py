#!/usr/bin/env python
"""Demo ④ · "The compiler says no" — the type judgment as a scene.

Fig 6 exposes ONE metabolism signature (``CoarseGrainedMetabolism``:
``nutrients ⇒ biomass, energy, entropy, secretions``). Three genuinely different
mechanisms conform to it — a lumped-yield coarse grain, a saturating kinetic law,
and real flux-balance analysis over ``e_coli_core`` — and the compiler ⟦C⟧_H
accepts each: it compiles the semantic composite AND the result installs (builds
as a runnable process-bigraph Composite).

A fourth handler is an impostor: ``NonConformingMetabolism`` renames the biomass
output to ``growth`` (wrong type) and drops the rest. The SAME compiler rejects it
with a ``CompileError`` naming every port it fails to supply. One interface, three
mechanisms accepted, one impostor rejected — the conformance law (law 1) made
visible.

Run:  PYTHONPATH=<repo> python scripts/demo_compiler_rejection.py
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite

from meta_modelers_guide.core import build_core
from meta_modelers_guide.compile import (
    CompileError, compile_composite, signature_of,
)

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "meta_modelers_guide" / "composites"
SEMANTIC = COMPOSITES / "fig05-disintegration.composite.json"

DRAFT = "CoarseGrainedMetabolism"

# Every case keeps the molecular sub-network on its kinetic handler; only the
# metabolism handler varies. That isolates the judgment to the metabolism port set.
_MOLECULAR = {
    "CatalyzedReactionNetwork": {
        "handler": "KineticReactionNetwork",
        "config": {"k": 0.2},
        "init": {"molecular.substrates": 1.0, "molecular.catalysts": 1.0},
    },
}

# (label, handler class name, config) — three conformers + one impostor.
CASES = [
    ("coarse",   "CoarseMetabolism",       {}),
    ("kinetic",  "KineticMetabolism",      {"vmax": 1.0, "km": 0.5}),
    ("fba",      "FBAMetabolism",          {"uptake_scale": 10.0, "o2_bound": 18.0}),
    ("impostor", "NonConformingMetabolism", {}),
]


def _env(handler, config):
    return {DRAFT: {"handler": handler, "config": config,
                    "init": {"coarse.nutrients": 1.0}}, **_MOLECULAR}


def main() -> None:
    core = build_core()
    sem = json.loads(SEMANTIC.read_text())["state"]

    sig = signature_of(core, DRAFT)
    print(f"Fig 6 interface  {DRAFT}")
    print(f"  in : {sig.inputs}")
    print(f"  out: {sig.outputs}\n")

    print(f"{'handler':>22}  {'compile':>8}  {'install':>8}  result")
    print("  " + "-" * 74)
    rows = []
    for label, handler, config in CASES:
        env = _env(handler, config)
        try:
            ex_state = compile_composite(sem, env, core)
            # "install" = the compiled composite builds as a runnable Composite.
            Composite({"state": ex_state}, core=core)
            print(f"{handler:>22}  {'✓':>8}  {'✓':>8}  accepted ({label})")
            rows.append((label, True, None))
        except CompileError as exc:
            print(f"{handler:>22}  {'✗':>8}  {'—':>8}  REJECTED ({label})")
            rows.append((label, False, str(exc)))

    # print the actual rejection message the compiler raised
    for label, ok, msg in rows:
        if not ok:
            print("\nCompileError raised for the impostor:")
            print("  " + msg.replace("\n", "\n  "))

    n_ok = sum(1 for _, ok, _ in rows if ok)
    n_bad = len(rows) - n_ok
    print(f"\n{n_ok} conforming handlers accepted, {n_bad} impostor rejected "
          f"— one interface, one compiler.")


if __name__ == "__main__":
    main()
