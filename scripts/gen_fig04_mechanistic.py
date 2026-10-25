#!/usr/bin/env python
"""Generate the fig04-mechanistic composite JSON (a 25-cell reaction–diffusion
lattice is data, so it is generated rather than hand-written).

The field is initialised with an explicit, IN-DOMAIN exponential gradient
c(x) = C0·exp(−x/λ) that the FieldSource at cell 0 then keeps replenished, so the
cell senses nutrient from t=0 (the source is inside the domain and labelled, per
the review — no unlabelled source-outside-domain condition). Distances are in
LATTICE units (dx = 1).

    python scripts/gen_fig04_mechanistic.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "meta_modelers_guide" / "composites" / "fig04-mechanistic.composite.json"

N = 25          # lattice cells
LAMBDA = 8.0    # gradient decay length (lattice units)
C0 = 2.0        # source-cell concentration
CELL_X0 = 16.0  # cell start (lattice units), down-gradient of the source at 0


def build():
    grid = {"_type": "map", "_value": "float"}
    for i in range(N):
        grid[str(i)] = round(C0 * math.exp(-i / LAMBDA), 6)

    return {
        "name": "Cell–Environment Coupling — Reaction–Diffusion Field with a Depleting, Chemotactic Cell",
        "description": (
            "Fig 4 (paper Fig 5) mechanistic variant. A 1-D reaction–diffusion nutrient field "
            "(25-cell lattice, dx = 1 lattice unit) carries an explicit in-domain exponential "
            "gradient kept replenished by a FieldSource at cell 0. A MotileCell takes up nutrient "
            "with saturating Michaelis–Menten kinetics, REMOVES that uptake from the field at its "
            "location (a real depletion well that diffuses), grows biomass out of it, and chemotaxes "
            "up the local gradient toward the source. Closes the sense/act loop the baseline left "
            "open. Mass ledger: Σfield change = Σsource − Σdecay − Σuptake; biomass change = "
            "yield·Σuptake. Distances in lattice units."),
        "default_n_steps": 24,
        "requires": {"processes": ["DiffusionField", "FieldSource", "MotileCell"]},
        "provenance": {"figure": "fig04-cell-environment", "environment": "fig04-mechanistic"},
        "state": {
            "diffusion": {
                "_type": "process", "address": "local:DiffusionField", "interval": 1.0,
                "config": {"diffusivity": 0.4},
                "inputs": {"chemical_field": ["environment", "chemical_field"]},
                "outputs": {"chemical_field": ["environment", "chemical_field"]},
            },
            "source": {
                "_type": "process", "address": "local:FieldSource", "interval": 1.0,
                "config": {"source_index": 0, "source_rate": 0.25, "decay_rate": 0.004},
                "inputs": {"chemical_field": ["environment", "chemical_field"]},
                "outputs": {"chemical_field": ["environment", "chemical_field"],
                            "source_total": ["ledger", "source_total"],
                            "decay_total": ["ledger", "decay_total"]},
            },
            "cell": {
                "_type": "process", "address": "local:MotileCell", "interval": 1.0,
                "config": {"vmax": 0.45, "km": 0.30, "yield_coef": 0.6, "chemotaxis": 9.0, "max_step": 1.0},
                "inputs": {"chemical_field": ["environment", "chemical_field"],
                           "position": ["cell_state", "position"], "biomass": ["cell_state", "biomass"]},
                "outputs": {"chemical_field": ["environment", "chemical_field"],
                            "position": ["cell_state", "position"], "biomass": ["cell_state", "biomass"],
                            "uptake": ["cell_state", "uptake"], "uptake_total": ["ledger", "uptake_total"],
                            "local_conc": ["cell_state", "local_conc"], "gradient": ["cell_state", "gradient"]},
            },
            "environment": {"chemical_field": grid},
            "cell_state": {
                "position": {"_type": "length", "_default": CELL_X0},
                "biomass": {"_type": "mass", "_default": 1.0},
                "uptake": {"_type": "chemical_flux", "_default": 0.0},
                "local_conc": {"_type": "concentration", "_default": 0.0},
                "gradient": {"_type": "concentration", "_default": 0.0},
            },
            "ledger": {
                "source_total": {"_type": "chemical_flux", "_default": 0.0},
                "decay_total": {"_type": "chemical_flux", "_default": 0.0},
                "uptake_total": {"_type": "chemical_flux", "_default": 0.0},
            },
            "emitter": {
                "_type": "step", "address": "local:RAMEmitter",
                "config": {"emit": {"position": "length", "biomass": "mass", "uptake": "chemical_flux",
                                    "local_conc": "concentration", "gradient": "concentration",
                                    "source_total": "chemical_flux", "decay_total": "chemical_flux",
                                    "uptake_total": "chemical_flux", "time": "float"}},
                "inputs": {"position": ["cell_state", "position"], "biomass": ["cell_state", "biomass"],
                           "uptake": ["cell_state", "uptake"], "local_conc": ["cell_state", "local_conc"],
                           "gradient": ["cell_state", "gradient"], "source_total": ["ledger", "source_total"],
                           "decay_total": ["ledger", "decay_total"], "uptake_total": ["ledger", "uptake_total"],
                           "time": ["global_time"]},
            },
        },
    }


if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), indent=2))
    print(f"wrote {OUT}")
