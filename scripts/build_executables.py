#!/usr/bin/env python
"""Materialize each figure's EXECUTABLE composite by running the semantic→executable
compiler (compile.py) over the semantic composite + its handler environment, and
writing the result to composites/<output>.composite.json — discoverable by the
workbench and runnable via /viva-run. compile.py is the single source of truth.

Re-run after editing handlers / envs / semantic composites.
"""
from __future__ import annotations

import json
from pathlib import Path

from meta_modelers_guide.core import build_core
from meta_modelers_guide.compile import compile_composite
from meta_modelers_guide.handler_envs import ENVS

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "meta_modelers_guide" / "composites"

# (env name, semantic composite stem, executable output stem)
BUILD: list[tuple[str, str, str]] = [
    ("fig06-coarse",  "fig06-disintegration",     "fig06-executable-coarse"),
    ("fig06-kinetic", "fig06-disintegration",     "fig06-executable-kinetic"),
    ("fig06-fba",     "fig06-disintegration",     "fig06-executable-fba"),
    ("fig04b",        "fig04b-cellular-interface", "fig04b-executable"),
    ("fig05",         "fig05-cell-environment",    "fig05-executable"),
    ("fig07",         "fig07-molecular-mechanism", "fig07-executable"),
    ("fig08",         "fig08-nested-hierarchy",    "fig08-executable"),
    ("fig09a",        "fig09a-coarse-graining",    "fig09a-executable"),
    ("fig09b",        "fig09b-minimal-cell",       "fig09b-executable"),
    ("fig10-1",       "fig10-1-division",          "fig10-1-executable"),
    ("fig10-2",       "fig10-2-development",       "fig10-2-executable"),
    ("fig10-3",       "fig10-3-evolution",         "fig10-3-executable"),
    ("cellcell-compete",   "cellcell-coupling", "cellcell-executable-compete"),
    ("cellcell-crossfeed", "cellcell-coupling", "cellcell-executable-crossfeed"),
]


def build_one(core, env_name, semantic_stem, output_stem) -> Path | None:
    if env_name not in ENVS:
        print(f"skip {output_stem}: env {env_name!r} not defined yet")
        return None
    sem = json.loads((COMPOSITES / f"{semantic_stem}.composite.json").read_text())
    ex_state = compile_composite(sem["state"], ENVS[env_name], core)
    from meta_modelers_guide.ontology import figure_provenance
    doc = {
        "name": output_stem,
        "description": (f"Executable compilation of {semantic_stem} under handler "
                        f"environment '{env_name}' — draft signatures replaced by "
                        f"conforming Process handlers (see compile.py). Runnable."),
        "requires": {"processes": sorted({s["handler"] for s in ENVS[env_name].values()})},
        # Phase 5 provenance: each handled draft's biological-process ontology term.
        "provenance": {"figure": semantic_stem, "environment": env_name,
                       "handlers": figure_provenance(ENVS[env_name])},
        "state": ex_state,
    }
    out = COMPOSITES / f"{output_stem}.composite.json"
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    return out


def main() -> None:
    core = build_core()
    n = 0
    for env_name, sem_stem, out_stem in BUILD:
        p = build_one(core, env_name, sem_stem, out_stem)
        if p:
            print("built", p.relative_to(ROOT)); n += 1
    print(f"\n{n} executable composites materialized")


if __name__ == "__main__":
    main()
