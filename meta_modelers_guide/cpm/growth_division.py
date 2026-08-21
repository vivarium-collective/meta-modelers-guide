"""CpmGrowthDivision — a single CPM cell that grows via per-cell dFBA on a shared
glucose field (the same growth body as ``CpmColonyField``'s competitor/secretor
role) and DIVIDES at a volume threshold using the native engine call
``world.divide_cells(threshold, reset_target)``, compounding into a lineage.

This is study-3's colony growth loop PLUS one extra engine call per tick PLUS the
daughter bookkeeping that call requires -- see
``docs/superpowers/api-maps/2026-08-21-growth-and-division-api-map.md``:

- ``divide_cells(vol_threshold, reset_target)`` splits EVERY live cell whose
  volume >= ``vol_threshold`` (not a chosen id) by a plane through its longest
  bounding-box axis: the parent keeps its id, a NEW id is created for the other
  daughter, pixels are re-owned (mass conserved on the lattice), and the engine
  itself sets BOTH daughters' physical ``target_volume`` to ``reset_target`` --
  no manual CPM-side reset needed. It returns the list of new ids created this
  call.
- The one bookkeeping duty left to this process: our own per-cell ``biomass``
  dict still drives ``set_target_volume`` every following tick via
  ``grow_per_biomass * biomass[cid]``, so after a division we must give each
  daughter its share of tracked ``biomass`` too. Per the paper (Fig 10b
  caption), division PARTITIONS state variables like biomass across the two
  daughters rather than discarding them -- so we split the PARENT's
  pre-division biomass between parent-id and new-id proportional to their
  post-division lattice volumes (mass-conserving), not reset both to a fixed
  ``reset_target``-derived value. See the ``update`` method for the exact
  parent<->daughter pairing (index-matched against the engine's internal
  ``dividing`` order, not a geometric guess) and the split formula, plus the
  ``lineage``/``generation`` bookkeeping that records genealogy.
- New daughter ids need their own cobra model copy (never share one model
  object across cells -- see the colony API map, bound-leakage risk #2):
  lazily ``load_model("textbook")`` for any id seen for the first time, with
  the same static O2 cap as every other cell here (there is only one role in
  this study: glucose uptake -> microaerobic acetate overflow, exactly the
  colony's competitor/secretor branch).
- ``live_ids`` is re-derived from ``np.unique(snapshot())`` every tick (never
  cached), so a zero-volume phantom daughter from dividing a too-small cell
  (API map Q6) is simply skipped that tick (its footprint is empty) rather than
  raising or growing on stale bookkeeping. ``vol_threshold`` should also be kept
  comfortably above the ~8px phantom-risk floor.
"""
from __future__ import annotations

import numpy as np
from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


_DEFAULT_CELL_TYPE = 1


class CpmGrowthDivision(Process):
    config_schema = {
        # No `_default` on container-typed leaves (`grid`, `cell`, `contact`) --
        # bigraph-schema's generic "list"/container apply *merges* a
        # schema-declared `_default` with an incoming config value on
        # composition rather than replacing it (the flagship's `seed_block`
        # comment, `cell_field.py`), so a caller-supplied dict/list would get
        # spuriously concatenated with any default here. Python-side defaulting
        # in `__init__` avoids that trap entirely.
        "grid": {"_type": "map[integer]"},
        "cell": {"_type": "schema"},
        "contact": {"_type": "list"},
        "mcs": {"_type": "integer", "_default": 3},
        "init_biomass": _f(1.25),
        "grow_per_biomass": _f(300.0),
        "box_volume_L": _f(1e-6),
        "glucose_km": _f(0.5),
        "glucose_vmax": _f(10.0),
        "oxygen_vmax": _f(15.0),
        "vol_threshold": _f(90.0),
        "reset_target": _f(45.0),
    }

    def inputs(self):
        return {"fields": "map[array]"}

    def outputs(self):
        # per-cell `volume`/`position`/`biomass`/`local_glucose` and the scalars
        # `n_cells`/`total_volume` are this tick's absolute readings, not
        # deltas -- same reasoning as `colony_field.py`'s `overwrite[...]`
        # outputs: plain float/list/map apply is additive/concatenating and
        # would silently corrupt a multi-tick run (population size summing
        # across ticks instead of reporting the current count, etc). `fields`
        # is a genuine spatial delta the engine sums into the shared grid.
        return {
            "fields": "map[array]",
            "volume": "overwrite[map[float]]",
            "position": "overwrite[map[list]]",
            "local_glucose": "overwrite[map[float]]",
            "biomass": "overwrite[map[float]]",
            "generation": "overwrite[map[float]]",
            "n_cells": "overwrite[float]",
            "total_volume": "overwrite[float]",
            "max_generation": "overwrite[float]",
        }

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        from cpm.schema import load_world
        try:
            from cobra.io import load_model
        except Exception as exc:  # pragma: no cover - exercised only without cobra
            raise RuntimeError(
                "CpmGrowthDivision requires the optional 'cobra' package "
                "(pip install -e .[simulators]).") from exc
        self._load_model = load_model

        c = self.config
        grid = dict(c.get("grid") or {})
        nx, ny = int(grid.get("nx", 40)), int(grid.get("ny", 40))
        self._nx, self._ny = nx, ny

        cell_cfg = dict(c.get("cell") or {})
        seed_block = list(cell_cfg.get("seed_block") or [17, 17, 0, 24, 24, 1])
        target_volume = float(cell_cfg.get("target_volume", 40.0))
        lambda_volume = float(cell_cfg.get("lambda_volume", 2.0))
        temperature = float(cell_cfg.get("temperature", 11.0))

        contact = list(c.get("contact") or [{"a": 0, "b": _DEFAULT_CELL_TYPE, "j": 14.0}])

        spec = {
            "potts": {"dims": [nx, ny, 1], "boundary": "noflux", "neighbor_order": 2,
                      "temperature": temperature, "seed": 1},
            "cells": [{"type": _DEFAULT_CELL_TYPE, "target_volume": target_volume,
                       "lambda_volume": lambda_volume, "target_surface": 0.0,
                       "lambda_surface": 0.0, "seed_block": seed_block}],
            "contact": contact,
        }
        self.world = load_world(spec)

        # cell id 1 is the sole founder (id 0 is reserved for medium) -- verified
        # in the study-3/colony API map.
        self._models: dict[int, object] = {}
        self.biomass: dict[int, float] = {}
        # Lineage: new daughter id -> parent id (founder id 1 has no entry).
        # Generation: cell id -> generation count (founder = 0, +1 per division
        # a cell's ancestry passed through). `max_generation` is tracked
        # incrementally so the observable stays correct even if a
        # highest-generation cell's footprint later disappears (phantom).
        self.lineage: dict[int, int] = {}
        self.generation: dict[int, int] = {1: 0}
        self.max_generation: int = 0
        self._new_model(1, float(c["init_biomass"]))

    def _new_model(self, cid, biomass0):
        """Lazily create id `cid`'s own cobra copy + tracked biomass -- one model
        per cell, never shared (bound-leakage risk, see module docstring)."""
        if cid in self._models:
            return
        model = self._load_model("textbook")
        # static: O2 capped microaerobic -> forces acetate overflow (the only
        # role in this study, mirrors colony's competitor/secretor branch).
        # Glucose exchange is left at cobra's default and overwritten every
        # tick in `_fba` with the MM-limited dynamic bound.
        model.reactions.EX_o2_e.lower_bound = -float(self.config["oxygen_vmax"])
        self._models[cid] = model
        self.biomass[cid] = biomass0

    def _fba(self, cid, local_glc, interval):
        """One dFBA step for cell `cid`: MM-limit glucose uptake on the
        footprint's mean local concentration, solve, and return the idealized
        (unclamped) (d_biomass, d_glucose, d_acetate_byproduct) -- mirrors
        `colony_field.py`'s `_fba` competitor/secretor branch exactly."""
        c = self.config
        m = self._models[cid]
        km = float(c["glucose_km"])
        vmax = float(c["glucose_vmax"])
        v = vmax * local_glc / (km + local_glc) if local_glc > 0 else 0.0
        m.reactions.EX_glc__D_e.lower_bound = -float(v)

        sol = m.optimize()
        if sol.status != "optimal":
            # Don't trust `sol.fluxes` on an infeasible solve (stale primal
            # values from the last feasible solve) -- growth and secretion both
            # cleanly stop instead.
            return 0.0, 0.0, 0.0

        mu = float(sol.objective_value or 0.0)
        biomass = self.biomass[cid]
        d_biomass = mu * biomass * interval
        box_volume_L = float(c["box_volume_L"])
        glc_flux = float(sol.fluxes.get("EX_glc__D_e", 0.0))  # negative = uptake
        ac_flux = float(sol.fluxes.get("EX_ac_e", 0.0))       # positive = secreted
        d_glc = glc_flux * biomass * interval / box_volume_L
        d_ac = ac_flux * biomass * interval / box_volume_L
        return d_biomass, d_glc, d_ac

    @staticmethod
    def _clamp_removal(field, fp, requested_delta):
        """Mass-conservative removal: clamp `requested_delta` (<=0) against what
        `field[fp]` actually holds, spread proportionally to each pixel's
        current value (never drives a pixel negative), and return
        (clamped_delta, per-pixel delta array, clamp ratio to scale correlated
        deltas by). Mirrors `colony_field.py`'s `_clamp_removal` verbatim."""
        if not fp.any():
            return 0.0, np.zeros(0), 1.0
        area = max(int(fp.sum()), 1)
        available = -float(field[fp].sum())  # <= 0
        clamped = max(requested_delta, available)
        ratio = (clamped / requested_delta) if requested_delta < 0 else 1.0
        vals = field[fp]
        total = float(vals.sum())
        weights = (vals / total) if total > 0 else np.full(area, 1.0 / area)
        per_pixel = clamped * weights
        return clamped, per_pixel, ratio

    def update(self, state, interval):
        fields = state.get("fields", {})
        glucose = np.asarray(fields.get("glucose"), dtype=float)
        acetate = np.asarray(fields.get("acetate"), dtype=float)
        lat = np.array(self.world.snapshot()).reshape(self._ny, self._nx)
        live_ids = sorted(set(int(i) for i in np.unique(lat)) - {0})

        dglc_total = np.zeros_like(glucose)
        dace_total = np.zeros_like(acetate)

        local_glc_obs = {}
        grow_per_biomass = float(self.config["grow_per_biomass"])

        for cid in live_ids:
            self._new_model(cid, float(self.config["init_biomass"]))  # daughter seen for first time
            fp = (lat == cid)
            key = str(cid)

            local_glc = float(glucose[fp].mean()) if fp.any() else 0.0
            local_glc_obs[key] = local_glc

            d_biomass, d_glc_request, d_byproduct = self._fba(cid, local_glc, interval)

            clamped, per_pixel, ratio = self._clamp_removal(glucose, fp, d_glc_request)
            d_biomass *= ratio
            d_byproduct *= ratio
            area = max(int(fp.sum()), 1)
            if fp.any():
                dglc_total[fp] += per_pixel
                dace_total[fp] += d_byproduct / area

            self.biomass[cid] = max(self.biomass[cid] + d_biomass, 1e-9)

            target = grow_per_biomass * self.biomass[cid]
            self.world.set_target_volume(cid, max(target, 0.0))

        self.world.step(int(self.config["mcs"]))

        # --- division ---------------------------------------------------
        vol_threshold = float(self.config["vol_threshold"])
        reset_target = float(self.config["reset_target"])
        vols_before = list(self.world.cell_volumes())
        new_ids = self.world.divide_cells(vol_threshold, reset_target)
        if new_ids:
            # Exact parent<->daughter pairing (not a geometric/nearest-COM
            # heuristic): viva-cpm's native `divide_cells`
            # (crates/cpm-core/src/mitosis.rs) builds its internal `dividing`
            # list by iterating `self.cells` -- a Vec indexed by cell id, id 0
            # reserved for medium -- filtering `c.volume >= threshold`, in
            # ascending-id order; it then creates exactly one new daughter per
            # entry of `dividing`, in that same order, appending each new id to
            # `new_ids`. The pyo3 binding's `cell_volumes()` returns
            # `cells.iter().map(|c| c.volume)` -- the identical per-id
            # ordering -- so replaying that same filter over our own
            # `vols_before` snapshot reconstructs the Rust side's `dividing`
            # list exactly, and `zip(dividing, new_ids)` gives the true
            # parent -> daughter pairing index-for-index.
            dividing = [cid for cid in range(1, len(vols_before)) if vols_before[cid] >= vol_threshold]
            assert len(dividing) == len(new_ids), (
                f"parent/daughter count mismatch: {len(dividing)} dividing vs {len(new_ids)} new_ids")
            vols_after = self.world.cell_volumes()
            for parent_id, daughter_id in zip(dividing, new_ids):
                # Partition the PARENT's pre-division biomass across the two
                # daughters proportional to their post-division lattice
                # volumes -- mass-conserving, per the paper (Fig 10b caption:
                # division "partitions state variables such as DNA and
                # biomass into two cells"), rather than resetting both to a
                # fixed value (which used to destroy accumulated biomass).
                total_bm = self.biomass.get(parent_id, reset_target / grow_per_biomass)
                vol_parent_after = float(vols_after[parent_id]) if parent_id < len(vols_after) else 0.0
                vol_daughter = float(vols_after[daughter_id]) if daughter_id < len(vols_after) else 0.0
                denom = vol_parent_after + vol_daughter
                if denom > 0:
                    parent_bm = total_bm * vol_parent_after / denom
                    daughter_bm = total_bm * vol_daughter / denom
                else:
                    # Zero-volume phantom split (API map Q6): fall back to an
                    # equal half-split so total biomass is still conserved.
                    parent_bm = daughter_bm = total_bm / 2.0
                self.biomass[parent_id] = max(parent_bm, 1e-9)
                self._new_model(daughter_id, max(daughter_bm, 1e-9))  # daughter's own cobra copy

                # Lineage + generation bookkeeping.
                self.lineage[daughter_id] = parent_id
                gen = self.generation.get(parent_id, 0) + 1
                self.generation[daughter_id] = gen
                self.max_generation = max(self.max_generation, gen)

        # re-derive live ids again post-division (new daughters + any phantom
        # zero-volume id from a too-small split, which we skip via `fp.any()`
        # in the observable loop below).
        lat = np.array(self.world.snapshot()).reshape(self._ny, self._nx)
        live_ids = sorted(set(int(i) for i in np.unique(lat)) - {0})

        vols = self.world.cell_volumes()
        coms = self.world.cell_coms()
        volume_obs, position_obs, biomass_obs, generation_obs = {}, {}, {}, {}
        total_volume = 0.0
        for cid in live_ids:
            key = str(cid)
            vol = float(vols[cid]) if cid < len(vols) else 0.0
            volume_obs[key] = vol
            position_obs[key] = list(coms[cid])[:2] if cid < len(coms) else [0.0, 0.0]
            biomass_obs[key] = self.biomass.get(cid, 0.0)
            generation_obs[key] = float(self.generation.get(cid, 0))
            total_volume += vol

        return {
            "fields": {"glucose": dglc_total, "acetate": dace_total},
            "volume": volume_obs,
            "position": position_obs,
            "local_glucose": local_glc_obs,
            "biomass": biomass_obs,
            "generation": generation_obs,
            "n_cells": float(len(live_ids)),
            "total_volume": total_volume,
            "max_generation": float(self.max_generation),
        }
