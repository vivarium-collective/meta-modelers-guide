#!/usr/bin/env python
"""Run every EXECUTABLE composite + the whole cell and dump real observable
readouts (first/last/min/max per changing series) to a JSON the study authoring
step consumes. Reuses render_executable_dynamics._run/_series so the numbers
match the dynamics SVGs exactly.
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite, gather_emitter_results

from viva_meta_modelers_guide.core import build_core
from viva_meta_modelers_guide.wholecell import build_whole_cell

import render_study_evidence as R  # sibling script — single executable-evidence renderer

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "viva_meta_modelers_guide" / "composites"
OUT = ROOT / "scripts" / "_catalog" / "measured_readouts.json"


def summarize(stem):
    rows = R._run(stem)
    if not rows:
        return None
    times, series = R._series(rows)
    out = {}
    for lab, ys in series.items():
        out[lab] = {"first": round(ys[0], 4), "last": round(ys[-1], 4),
                    "min": round(min(ys), 4), "max": round(max(ys), 4)}
    return {"n_steps": len(times), "t_end": round(times[-1], 3), "series": out}


def whole_cell():
    core = build_core()
    sim = Composite(build_whole_cell(), core=core)
    sim.run(20.0)
    rows = gather_emitter_results(sim)[("emitter",)]
    t = [r["time"] for r in rows]
    keys = ("biomass", "viability", "temperature", "cell_count", "debris")
    series = {k: [float(r[k]) for r in rows] for k in keys}
    div_t = next((r["time"] for r in rows if r["cell_count"] >= 2), None)
    return {
        "t_end": t[-1], "n_steps": len(t),
        "peak_biomass": round(max(series["biomass"]), 3),
        "division_time": div_t,
        "min_viability": round(min(series["viability"]), 3),
        "final_debris": round(series["debris"][-1], 3),
        "peak_temperature": round(max(series["temperature"]), 3),
        "final_cell_count": series["cell_count"][-1],
        "series": {k: {"first": round(v[0], 4), "last": round(v[-1], 4),
                       "min": round(min(v), 4), "max": round(max(v), 4)}
                   for k, v in series.items()},
    }


def main():
    result = {}
    stems = sorted(p.name.replace(".composite.json", "")
                   for p in COMPOSITES.glob("*executable*.composite.json"))
    for stem in stems:
        try:
            s = summarize(stem)
        except Exception as exc:
            s = {"error": f"{type(exc).__name__}: {exc}"}
        result[stem] = s
        print(f"  {stem}: {'ok' if s and 'error' not in s else s}")
    try:
        result["wholecell"] = whole_cell()
        print(f"  wholecell: {result['wholecell']['peak_biomass']=} "
              f"{result['wholecell']['division_time']=} "
              f"{result['wholecell']['final_debris']=}")
    except Exception as exc:
        result["wholecell"] = {"error": f"{type(exc).__name__}: {exc}"}
        print(f"  wholecell: ERROR {exc}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
