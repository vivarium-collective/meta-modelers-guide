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
    ("fig05-coarse",  "fig05-disintegration",     "fig05-executable-coarse"),
    ("fig05-kinetic", "fig05-disintegration",     "fig05-executable-kinetic"),
    ("fig05-fba",     "fig05-disintegration",     "fig05-executable-fba"),
    ("fig03b",        "fig03b-cellular-interface", "fig03b-executable"),
    ("fig04",         "fig04-cell-environment",    "fig04-executable"),
    ("fig06",         "fig06-molecular-mechanism", "fig06-executable"),
    ("fig07",         "fig07-nested-hierarchy",    "fig07-executable"),
    ("fig08a",        "fig08a-coarse-graining",    "fig08a-executable"),
    ("fig08b",        "fig08b-minimal-cell",       "fig08b-executable"),
    ("fig09",       "fig09-division",          "fig09-executable"),
    ("fig10",       "fig10-development",       "fig10-executable"),
    ("fig11",       "fig11-evolution",         "fig11-executable"),
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
