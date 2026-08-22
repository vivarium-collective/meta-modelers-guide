"""CpmCompeteDivision -- the cell-cell COMPETITION study lifted from two static
cells (``CpmColonyField`` ``cellcell-compete``) to two DIVIDING founder
LINEAGES racing for one depleting glucose pool, with a viability floor that can
remove a starved cell from the lattice. This is what "competitive exclusion" in
its ecological sense requires: not just asymmetric growth of two fixed cells, but
population-level extinction/dominance -- one lineage driven out.

It is a MINIMAL subclass of study-8's ``CpmGrowthDivision`` (``growth_division.py``),
reusing the base's growth + native-``divide_cells`` + biomass-partitioning loop
UNCHANGED via its two hooks, and adding exactly three things:

- **Multiple founders with per-lineage uptake.** ``cells`` (a list, like the
  colony) seeds N founders; each founder cell id ``i+1`` gets its own
  ``glucose_vmax`` and is tagged with a ``founder`` id (== its own id at seeding)
  that is inherited by every descendant. ``_cell_glucose_vmax(cid)`` returns that
  cell's own lineage vmax (the base returns a population-wide constant); the fast
  lineage (founder 1, vmax 10) vs the slow lineage (founder 2, vmax 4) is the same
  10-vs-4 asymmetry as ``cellcell-compete``, now heritable through division.
- **A maintenance cost.** ``maintenance`` decays every live cell's tracked biomass
  by ``maintenance * biomass * dt`` each tick (a non-growth upkeep). With growth
  from dFBA always >= 0, biomass in the base can only rise or be partitioned on
  division -- it can never FALL, so a pure biomass floor would never bite. The
  maintenance term is what lets a cell that can no longer get glucose (its share
  of the shared pool preempted by the faster lineage) run a net-negative biomass
  balance -- Tilman R* competition: the lineage whose break-even resource level is
  higher loses once the shared resource is drawn below it.
- **A viability floor with removal.** Any live cell whose (post-maintenance)
  biomass falls below ``viability_floor`` is removed from the CPM lattice via the
  native ``world.remove_cells`` and dropped from all bookkeeping -- a genuine
  death, not just spatial displacement. ``viability_floor`` == 0 disables removal
  (backward-compatible: then this is just a two-lineage dividing colony).

``update`` calls ``super().update()`` (the base's unchanged loop, now driving this
subclass's ``_cell_glucose_vmax``/``_on_division`` hooks), then applies the
maintenance decay, does the floor removal, and layers the population-level
observables competitive exclusion is measured on: ``founder`` (per-cell lineage
tag) plus the per-lineage cell counts (``n_fast``/``n_slow``) and summed biomass
(``biomass_fast``/``biomass_slow``). Extinction of a lineage == its count and
biomass going to 0 while the other persists.
"""
from __future__ import annotations

from process_bigraph import Process

from .growth_division import CpmGrowthDivision, _DEFAULT_CELL_TYPE, _f


class CpmCompeteDivision(CpmGrowthDivision):
    config_schema = {
        **CpmGrowthDivision.config_schema,
        # `cells` (multi-founder colony) REPLACES the base's single `cell`. No
        # `_default` on the container leaf -- same bigraph-schema merge trap the
        # base documents; Python-side defaulting in __init__ instead.
        "cells": {"_type": "list"},
        "temperature": _f(11.0),
        "maintenance": _f(0.0),      # per-tick biomass upkeep: d_biomass -= maintenance*biomass*dt
        "viability_floor": _f(0.0),  # biomass below this -> cell removed from lattice (0 disables)
        "seed": {"_type": "integer", "_default": 1},
    }

    def outputs(self):
        base = dict(super().outputs())
        base.update({
            "founder": "overwrite[map[float]]",
            "n_fast": "overwrite[float]",
            "n_slow": "overwrite[float]",
            "biomass_fast": "overwrite[float]",
            "biomass_slow": "overwrite[float]",
        })
        return base

    def __init__(self, config=None, core=None):
        # Bypass CpmGrowthDivision.__init__ (it seeds a single `cell` and
        # hardcodes potts.seed=1). Go straight to Process.__init__ and replicate
        # the base's short world-construction body for N founders, threading
        # `seed` into the potts spec. update()/_fba/division are NOT duplicated.
        Process.__init__(self, config, core=core)
        from cpm.schema import load_world
        try:
            from cobra.io import load_model
        except Exception as exc:  # pragma: no cover - exercised only without cobra
            raise RuntimeError(
                "CpmCompeteDivision requires the optional 'cobra' package "
                "(pip install -e .[simulators]).") from exc
        self._load_model = load_model

        c = self.config
        grid = dict(c.get("grid") or {})
        nx, ny = int(grid.get("nx", 40)), int(grid.get("ny", 40))
        self._nx, self._ny = nx, ny

        cell_cfgs = list(c.get("cells") or [])
        if not cell_cfgs:
            raise ValueError("CpmCompeteDivision requires at least one entry in `cells`")
        contact = list(c.get("contact") or [{"a": 0, "b": _DEFAULT_CELL_TYPE, "j": 14.0}])

        seed = int(c.get("seed", 1))
        spec_cells = [
            {
                "type": _DEFAULT_CELL_TYPE,
                "target_volume": float(cfg.get("target_volume", 40.0)),
                "lambda_volume": float(cfg.get("lambda_volume", 2.0)),
                "target_surface": 0.0,
                "lambda_surface": 0.0,
                "seed_block": list(cfg["seed_block"]),
            }
            for cfg in cell_cfgs
        ]
        spec = {
            "potts": {"dims": [nx, ny, 1], "boundary": "noflux", "neighbor_order": 2,
                      "temperature": float(c["temperature"]), "seed": seed},
            "cells": spec_cells,
            "contact": contact,
        }
        self.world = load_world(spec)

        # cell ids assigned sequentially from 1 (id 0 == medium). Each founder is
        # its own lineage tag; descendants inherit it in `_on_division`.
        self._models: dict[int, object] = {}
        self.biomass: dict[int, float] = {}
        self.lineage: dict[int, int] = {}
        self.generation: dict[int, int] = {}
        self.max_generation: int = 0
        self._founder: dict[int, int] = {}
        self._cell_vmax: dict[int, float] = {}
        self._removed: set[int] = set()

        init_biomass = float(c["init_biomass"])
        for i, cfg in enumerate(cell_cfgs):
            cid = i + 1
            self._founder[cid] = cid
            self._cell_vmax[cid] = float(cfg.get("glucose_vmax", c["glucose_vmax"]))
            self.generation[cid] = 0
            self._new_model(cid, init_biomass)

    def _cell_glucose_vmax(self, cid):
        """This cell's own lineage vmax (the base returns a population-wide
        constant). Falls back to the config default for any untracked id."""
        return float(self._cell_vmax.get(cid, self.config["glucose_vmax"]))

    def _on_division(self, parent_id, daughter_id):
        """Daughter inherits the parent's lineage tag AND its uptake vmax (the
        trait is fixed per lineage here -- no mutation; that is study 9's job)."""
        self._founder[daughter_id] = self._founder.get(parent_id, parent_id)
        self._cell_vmax[daughter_id] = self._cell_vmax.get(
            parent_id, float(self.config["glucose_vmax"]))

    def update(self, state, interval):
        # Base loop UNCHANGED: growth (via our per-lineage `_cell_glucose_vmax`),
        # CPM step, native divide_cells, biomass partitioning (via our
        # `_on_division` for lineage/vmax inheritance).
        out = super().update(state, interval)

        maintenance = float(self.config["maintenance"])
        floor = float(self.config["viability_floor"])
        live = [int(k) for k in out["biomass"].keys()]

        # maintenance upkeep: the only way tracked biomass can FALL (dFBA growth
        # is always >= 0), so the floor below can actually bite for a starved cell.
        if maintenance > 0.0:
            for cid in live:
                self.biomass[cid] = max(self.biomass[cid] * (1.0 - maintenance * interval), 1e-9)

        # viability floor: remove any cell that has decayed below the floor.
        dead = [cid for cid in live if floor > 0.0 and self.biomass.get(cid, 0.0) < floor]
        if dead:
            self.world.remove_cells(list(dead))
            for cid in dead:
                self._removed.add(cid)
                for d in (self.biomass, self._founder, self._cell_vmax,
                          self._models, self.generation, self.lineage):
                    d.pop(cid, None)

        # rebuild the per-cell observables dropping the just-removed cells and
        # patching biomass with the post-maintenance values, then add the
        # population-level lineage aggregates competitive exclusion is read on.
        dead_set = set(dead)
        vol = out["volume"]; pos = out["position"]; bm = out["biomass"]
        lg = out["local_glucose"]; gen = out.get("generation", {})
        new_vol, new_pos, new_bm, new_lg, new_gen, founder_obs = {}, {}, {}, {}, {}, {}
        n_fast = n_slow = 0
        biomass_fast = biomass_slow = 0.0
        total_volume = 0.0
        for k in bm.keys():
            cid = int(k)
            if cid in dead_set:
                continue
            new_vol[k] = vol[k]
            new_pos[k] = pos[k]
            new_lg[k] = lg.get(k, 0.0)
            new_bm[k] = self.biomass.get(cid, bm[k])
            new_gen[k] = gen.get(k, 0.0)
            f = self._founder.get(cid, 0)
            founder_obs[k] = float(f)
            total_volume += vol[k]
            if f == 1:
                n_fast += 1
                biomass_fast += new_bm[k]
            elif f == 2:
                n_slow += 1
                biomass_slow += new_bm[k]

        out = dict(out)
        out["volume"] = new_vol
        out["position"] = new_pos
        out["biomass"] = new_bm
        out["local_glucose"] = new_lg
        out["generation"] = new_gen
        out["n_cells"] = float(len(new_bm))
        out["total_volume"] = total_volume
        out["founder"] = founder_obs
        out["n_fast"] = float(n_fast)
        out["n_slow"] = float(n_slow)
        out["biomass_fast"] = float(biomass_fast)
        out["biomass_slow"] = float(biomass_slow)
        return out
