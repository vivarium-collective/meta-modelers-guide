"""CpmCellField — a CPM cell (viva-cpm) that metabolizes a shared spatio-flux nutrient
field at its footprint and grows from the biomass it makes.

Owns the CPM world (the lattice + growth are not process-bigraph stores, so a single
world-owning process is the clean coupling point). Composes over one shared ``fields``
grid with spatio-flux ``DiffusionAdvection``: the cell reads glucose at its footprint,
runs one dFBA step (e_coli_core), writes back the uptake (-glucose) and secretion
(+acetate) as a field delta, and grows its CPM target volume in proportion to biomass.
Toy-real: plausible constants, not a fitted organism.

Oxygen note: unconstrained e_coli_core FBA never secretes acetate — pure aerobic
respiration is the growth-optimal flux distribution whenever O2 uptake is unbounded, so
``EX_ac_e`` sits at 0 for any glucose bound. Real E. coli exhibits acetate overflow once
glycolytic flux outpaces respiratory (TCA/ETC) capacity, which FBA only reproduces if
respiration is capacity-limited. We therefore cap ``EX_o2_e`` uptake at a fixed
microaerobic bound (``oxygen_vmax``, default 15 mmol/gDW/hr — below the ~18-22 the model
wants at glucose saturation) so the optimizer is forced into mixed-acid overflow,
matching the biological mechanism the coupling is meant to demonstrate.
"""
from __future__ import annotations

import numpy as np
from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


class CpmCellField(Process):
    config_schema = {
        "nx": {"_type": "integer", "_default": 40},
        "ny": {"_type": "integer", "_default": 40},
        # NOTE: no `_default` here — bigraph-schema's generic "list" type
        # *concatenates* an incoming config value with a schema-declared
        # `_default` on merge (rather than replacing it), so a caller-supplied
        # 6-int seed_block becomes a spurious 12-int list. Fall back to the
        # sensible default in Python (see `__init__`) instead.
        "seed_block": {"_type": "list"},
        "mcs_per_update": {"_type": "integer", "_default": 8},
        "temperature": _f(10.0),
        "lambda_volume": _f(2.0),
        "contact_j": _f(14.0),
        "biomass0": _f(0.1),
        "grow_per_biomass": _f(300.0),   # target_volume = grow_per_biomass * biomass
        "box_volume_L": _f(1e-6),
        "glucose_km": _f(0.5), "glucose_vmax": _f(10.0),
        "oxygen_vmax": _f(15.0),  # microaerobic cap -> forces acetate overflow
    }

    def inputs(self):
        return {"fields": "map[array]"}

    def outputs(self):
        # process-bigraph's plain "float"/"list" apply is *additive* (a process's
        # returned value is treated as a delta to accumulate onto prior state) and
        # plain "list" apply *concatenates*. `volume`, `position`, `local_nutrient`,
        # and `biomass` are this process's current absolute readings each tick, not
        # deltas, so they must be declared `overwrite[...]` (replace-on-apply) or a
        # multi-tick run silently sums/concatenates them into nonsense (observed:
        # volume growing far past the lattice's pixel count, position turning into
        # a running concatenation of every tick's [x, y]). `acetate_secreted` is a
        # genuine per-tick delta (this tick's secretion), so plain "float" is
        # correct there — and `fields` is a real spatial delta the engine sums into
        # the shared grid, which is the whole point of the coupling.
        return {"fields": "map[array]", "volume": "overwrite[float]", "position": "overwrite[list]",
                "local_nutrient": "overwrite[float]", "biomass": "overwrite[float]",
                "acetate_secreted": "float"}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        from cpm.schema import load_world
        c = self.config
        nx, ny = int(c["nx"]), int(c["ny"])
        self._nx, self._ny = nx, ny
        seed_block = list(c["seed_block"]) or [17, 17, 0, 24, 24, 1]
        spec = {
            "potts": {"dims": [nx, ny, 1], "boundary": "noflux", "neighbor_order": 2,
                      "temperature": c["temperature"], "seed": 1},
            "cells": [{"type": 1, "target_volume": 60.0, "lambda_volume": c["lambda_volume"],
                       "target_surface": 0.0, "lambda_surface": 0.0,
                       "seed_block": seed_block}],
            "contact": [{"a": 0, "b": 1, "j": c["contact_j"]}],
        }
        self.world = load_world(spec)
        self.biomass = float(c["biomass0"])
        # one cobra e_coli_core, loaded once
        from cobra.io import load_model
        self._model = load_model("textbook")
        # cap respiratory capacity so glycolytic flux forces mixed-acid (acetate)
        # overflow rather than pure aerobic respiration (see module docstring)
        self._model.reactions.EX_o2_e.lower_bound = -float(c["oxygen_vmax"])

    def _footprint(self):
        lat = np.array(self.world.snapshot()).reshape(self._ny, self._nx)
        return lat == 1

    def _fba(self, glucose_conc, interval):
        """One dFBA step on e_coli_core: MM-limited glucose uptake -> growth + acetate."""
        c = self.config
        m = self._model
        v = c["glucose_vmax"] * glucose_conc / (c["glucose_km"] + glucose_conc) if glucose_conc > 0 else 0.0
        # budget-limit the uptake by available glucose over the footprint
        m.reactions.EX_glc__D_e.lower_bound = -float(v)
        sol = m.optimize()
        mu = float(sol.objective_value or 0.0)
        d_biomass = mu * self.biomass * interval
        glc_flux = float(sol.fluxes.get("EX_glc__D_e", 0.0))   # negative = uptake
        ac_flux = float(sol.fluxes.get("EX_ac_e", 0.0))        # positive = secretion
        d_glc = glc_flux * self.biomass * interval / c["box_volume_L"]
        d_ac = ac_flux * self.biomass * interval / c["box_volume_L"]
        return d_biomass, d_glc, d_ac

    def update(self, state, interval):
        fields = state.get("fields", {})
        glucose = np.asarray(fields.get("glucose"))
        acetate = np.asarray(fields.get("acetate"))
        fp = self._footprint()
        area = max(int(fp.sum()), 1)
        local_glc = float(glucose[fp].mean()) if fp.any() else 0.0

        d_biomass, d_glc, d_ac = self._fba(local_glc, interval)
        self.biomass = max(self.biomass + d_biomass, 1e-9)

        # write uptake/secretion back to the field, spread over the footprint pixels
        dglc = np.zeros_like(glucose)
        dace = np.zeros_like(acetate)
        # clamp glucose delta so a pixel never goes negative
        per_pixel_glc = max(d_glc, -float(glucose[fp].sum())) / area if fp.any() else 0.0
        per_pixel_ac = d_ac / area if fp.any() else 0.0
        dglc[fp] = per_pixel_glc
        dace[fp] = per_pixel_ac

        # grow the CPM cell from biomass, then step the world
        target = float(self.config["grow_per_biomass"]) * self.biomass
        self.world.set_target_volume(1, max(target, 4.0))
        self.world.step(int(self.config["mcs_per_update"]))

        vol = float(self.world.cell_volumes()[1])
        com = list(self.world.cell_coms()[1])[:2]
        return {"fields": {"glucose": dglc, "acetate": dace},
                "volume": vol, "position": com, "local_nutrient": local_glc,
                "biomass": self.biomass, "acetate_secreted": float(dace.sum())}
