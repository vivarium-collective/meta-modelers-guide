#!/usr/bin/env python
"""Generate the fig08-mechanistic composite JSON.

A self-maintaining cell (SelfMaintainingCell) on a replenished medium
(NutrientReservoir): membrane-gated import feeds metabolism (needs enzymes) which
makes ATP + precursors that are spent (ATP-costed) to synthesise enzymes and
repair the membrane; everything degrades, so persistence requires continuous
replacement. A one-time membrane injury at tick 45 lets the cell show recovery.

    python scripts/gen_fig08_mechanistic.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "meta_modelers_guide" / "composites" / "fig08-mechanistic.composite.json"


def build():
    pools = {
        "nutrient_ext": ("concentration", 2.0), "nutrient_int": ("concentration", 0.5),
        "energy": ("energy", 0.6), "precursor": ("concentration", 0.5),
        "enzymes": ("concentration", 0.4), "membrane": ("area", 1.0),
        "viability": ("viability", 0.8),
    }
    cellstate = {k: {"_type": t, "_default": v} for k, (t, v) in pools.items()}
    readouts = {
        "import_flux": ("chemical_flux", 0.0), "metabolic_flux": ("chemical_flux", 0.0),
        "repair_flux": ("chemical_flux", 0.0), "energy_charge": ("float", 0.0),
        "imported_total": ("concentration", 0.0), "supplied_total": ("concentration", 0.0),
    }
    cellstate.update({k: {"_type": t, "_default": v} for k, (t, v) in readouts.items()})

    cell_ports = list(pools.keys())
    cell_inputs = {k: ["cell_state", k] for k in cell_ports}
    cell_outputs = {k: ["cell_state", k] for k in cell_ports}
    cell_outputs.update({k: ["cell_state", k] for k in
                         ["import_flux", "metabolic_flux", "repair_flux", "energy_charge", "imported_total"]})

    emit = {k: cellstate[k]["_type"] for k in
            ["membrane", "enzymes", "energy", "precursor", "nutrient_int", "nutrient_ext",
             "viability", "import_flux", "metabolic_flux", "repair_flux", "energy_charge",
             "imported_total", "supplied_total"]}
    emit["time"] = "float"
    emit_inputs = {k: ["cell_state", k] for k in emit if k != "time"}
    emit_inputs["time"] = ["global_time"]

    return {
        "name": "Self-Maintaining Cell — boundary, turnover, repair, viability",
        "description": (
            "Fig 8 (self-organized processes) mechanistic variant. A self-maintaining cell on a "
            "replenished medium: a membrane GATES nutrient import, metabolism (enzyme-catalysed) makes "
            "ATP + precursors, and precursor+ATP are spent to synthesise enzymes and REPAIR the membrane; "
            "every component degrades (turnover), so persistence requires continuous replacement. The cell "
            "grows to a far-from-equilibrium STEADY STATE, a one-time membrane injury at tick 45 is "
            "REPAIRED and viability RECOVERS. Operational closure: each component is produced by processes "
            "that depend on that component. Mechanism knockouts (k_transport/k_met/k_expr/k_repair→epsilon) "
            "and a non-replenished medium each collapse viability — dependence. This does NOT establish "
            "autopoiesis in the strong sense (the boundary is a scalar area, the viability target is scripted)."),
        "default_n_steps": 90,
        "requires": {"processes": ["NutrientReservoir", "SelfMaintainingCell"]},
        "provenance": {"figure": "fig08-self-organized", "environment": "fig08-mechanistic"},
        "state": {
            "reservoir": {
                "_type": "process", "address": "local:NutrientReservoir", "interval": 1.0,
                "config": {"replenish": 0.6, "cap": 5.0},
                "inputs": {"nutrient_ext": ["cell_state", "nutrient_ext"]},
                "outputs": {"nutrient_ext": ["cell_state", "nutrient_ext"],
                            "supplied_total": ["cell_state", "supplied_total"]},
            },
            "cell": {
                "_type": "process", "address": "local:SelfMaintainingCell", "interval": 1.0,
                "config": {"perturb_at": 45.0, "perturb_frac": 0.6},
                "inputs": cell_inputs, "outputs": cell_outputs,
            },
            "cell_state": cellstate,
            "emitter": {
                "_type": "step", "address": "local:RAMEmitter",
                "config": {"emit": emit}, "inputs": emit_inputs,
            },
        },
    }


if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), indent=2))
    print(f"wrote {OUT}")
