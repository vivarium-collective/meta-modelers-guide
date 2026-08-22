"""CpmColonyField — N CPM cells sharing one nutrient field, each running its own
per-cell dFBA and growing independently. Generalizes the flagship
``CpmCellField``'s single-cell read-field -> dFBA -> writeback -> grow loop to a
colony, looped over cell ids on ONE shared CPM ``World`` (cells must share a
single lattice to compete for space / interact through diffusion).

Each cell has a ``role`` that fixes its cobra exchange bounds once at init:
- ``competitor`` / ``secretor``: glucose uptake on (dynamically MM-limited each
  tick, see below), ``EX_o2_e`` capped at the cell's ``oxygen_vmax`` (microaerobic,
  forces mixed-acid acetate overflow exactly as the flagship's single cell does),
  acetate exchange left at its cobra default (secrete-only, lower bound 0).
- ``consumer``: glucose exchange fixed OFF (``lower_bound=0``), acetate exchange
  dynamically MM-limited (flipped negative -> uptake) each tick, O2 left
  effectively uncapped (``lower_bound=-20``) since respiring acetate needs more
  O2 than the microaerobic secretor allows.

Each cell gets its OWN cobra model copy (``self._models[cid]``) — reusing one
model object across cells with different static bounds risks bound leakage
between cells (see the study-3 API map, risk #2). Only 2-4 cells are expected,
so the memory cost of per-cell copies is a non-issue.

Field deltas are read (glucose + acetate) ONCE per tick from the shared
``fields`` store, then each cell accumulates its own delta only on its own CPM
footprint pixels (``snapshot() == cid``). CPM guarantees footprints are disjoint
(every pixel belongs to exactly one cell id or medium), so per-cell clamped
writes summed into one combined array are mass-conservative — verified by
``tests/test_cpm_colony_two_writer.py``. Growth mirrors the flagship: biomass
and any depleting substrate (glucose for competitor/secretor, acetate for
consumer) are scaled down together by however much the substrate removal had to
be clamped against what that cell's own footprint pixels actually held, so a
cell can never manufacture biomass from substrate it didn't actually remove.

``live_ids`` is re-derived from the CPM snapshot every tick (never cached) so a
cell that has shrunk to zero target volume/area is simply skipped that tick
rather than raising or growing on stale bookkeeping.
"""
from __future__ import annotations

import numpy as np
from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


_ROLES = {"competitor", "secretor", "consumer"}
_DEFAULT_CELL_TYPE = 1


class CpmColonyField(Process):
    config_schema = {
        # NOTE: `grid`/`cells`/`contact` deliberately carry no `_default` — see
        # the flagship's `seed_block` comment (cell_field.py): a schema-declared
        # `_default` on a container type gets *merged* (concatenated for lists)
        # with the caller-supplied config rather than replaced by it. Python-side
        # defaulting in `__init__` avoids that trap entirely.
        # `tree[integer]` looked right for a flat {nx, ny} dict, but
        # process_bigraph's Composite config resolution collapses a
        # `tree[integer]`-typed process-config leaf to its scalar default (0)
        # instead of preserving the dict (verified directly: `map[integer]`/
        # `schema` round-trip {"nx": .., "ny": ..} correctly through the same
        # Composite path, `tree[integer]` does not) -- so any composite
        # requesting nx/ny != the Python-side fallback default (40, see
        # below) silently got a 40x40 lattice instead. `test_cpm_colony_field`
        # only ever passed because it happens to request nx=ny=40. `map[integer]`
        # is semantically identical here (colony_field.py just does
        # `dict(c.get("grid") or {})` either way) and isn't affected.
        "grid": {"_type": "map[integer]"},
        "cells": {"_type": "list"},
        "contact": {"_type": "list"},
        "temperature": _f(10.0),
        "mcs": {"_type": "integer", "_default": 3},
        # Chosen so `grow_per_biomass * init_biomass` starts close to a typical
        # `seed_block`'s actual pixel area (avoids an immediate CPM volume
        # collapse in the first few `mcs` before dFBA-driven growth catches up —
        # see the colony test's `target_volume: 50.0` / `grow_per_biomass: 40.0`).
        "init_biomass": _f(1.25),
        "grow_per_biomass": _f(300.0),
        "box_volume_L": _f(1e-6),
        "glucose_km": _f(0.5),
        "acetate_km": _f(0.5),
    }

    def inputs(self):
        return {"fields": "map[array]"}

    def outputs(self):
        # `volume`/`position`/`local_glucose`/`local_acetate`/`biomass` are this
        # tick's absolute per-cell readings (id-string-keyed maps), not deltas —
        # same reasoning as the flagship's `overwrite[...]` outputs, just wrapped
        # in a map so a multi-tick run doesn't sum/concatenate them into nonsense.
        # `acetate_secreted` is a genuine per-tick delta per cell, so plain
        # `map[float]` (additive) is correct there.
        return {
            "fields": "map[array]",
            "volume": "overwrite[map[float]]",
            "position": "overwrite[map[list]]",
            "local_glucose": "overwrite[map[float]]",
            "local_acetate": "overwrite[map[float]]",
            "biomass": "overwrite[map[float]]",
            "acetate_secreted": "map[float]",
        }

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        from cpm.schema import load_world
        try:
            from cobra.io import load_model
        except Exception as exc:  # pragma: no cover - exercised only without cobra
            raise RuntimeError(
                "CpmColonyField requires the optional 'cobra' package "
                "(pip install -e .[simulators]).") from exc

        c = self.config
        grid = dict(c.get("grid") or {})
        nx, ny = int(grid.get("nx", 40)), int(grid.get("ny", 40))
        self._nx, self._ny = nx, ny

        cell_cfgs = list(c.get("cells") or [])
        if not cell_cfgs:
            raise ValueError("CpmColonyField requires at least one entry in `cells`")
        contact = list(c.get("contact") or [{"a": 0, "b": _DEFAULT_CELL_TYPE, "j": 14.0}])

        spec_cells = [
            {
                "type": _DEFAULT_CELL_TYPE,
                "target_volume": float(cfg["target_volume"]),
                "lambda_volume": float(cfg["lambda_volume"]),
                "target_surface": 0.0,
                "lambda_surface": 0.0,
                "seed_block": list(cfg["seed_block"]),
            }
            for cfg in cell_cfgs
        ]
        # CPM Metropolis seed: defaults to 1 (every composite stays deterministic
        # and reproduces its headline single-seed number), but is config-overridable
        # so a multi-seed robustness sweep can vary it without touching the composite
        # (see tests/test_cellcell_multiseed.py). This is the seed-sweep convention
        # studies 5/7/9 copy.
        seed = int(c.get("seed", 1))
        spec = {
            "potts": {"dims": [nx, ny, 1], "boundary": "noflux", "neighbor_order": 2,
                      "temperature": float(c["temperature"]), "seed": seed},
            "cells": spec_cells,
            "contact": contact,
        }
        self.world = load_world(spec)

        # cell ids are assigned sequentially in `cells`-list order, starting at 1
        # (id 0 is reserved for medium) — verified in the study-3 API map.
        init_biomass = float(c["init_biomass"])
        self._roles: dict[int, str] = {}
        self._cell_cfgs: dict[int, dict] = {}
        self._models: dict[int, object] = {}
        self.biomass: dict[int, float] = {}
        for i, cfg in enumerate(cell_cfgs):
            cid = i + 1
            role = cfg.get("role", "competitor")
            if role not in _ROLES:
                raise ValueError(f"cell {cid}: unknown role {role!r} (must be one of {_ROLES})")
            self._roles[cid] = role
            self._cell_cfgs[cid] = cfg
            self.biomass[cid] = init_biomass

            model = load_model("textbook")
            if role in ("competitor", "secretor"):
                # static: O2 capped microaerobic -> forces acetate overflow, exactly
                # as the flagship. Acetate exchange stays at cobra's default
                # secrete-only lower bound (0). Glucose exchange is left as-is here
                # (cobra default -10) and is overwritten every tick in `_fba` with
                # the MM-limited dynamic bound — never trust the default at runtime.
                model.reactions.EX_o2_e.lower_bound = -float(cfg.get("oxygen_vmax", 15.0))
            else:  # consumer
                # static: glucose exchange off; O2 uncapped-ish (respiring acetate
                # needs more O2 than the microaerobic secretor cap allows). Acetate
                # exchange is left as-is here and overwritten every tick in `_fba`
                # with the MM-limited dynamic (negative -> uptake) bound.
                model.reactions.EX_glc__D_e.lower_bound = 0.0
                model.reactions.EX_o2_e.lower_bound = -20.0
            self._models[cid] = model

    def _fba(self, cid, local_conc, interval):
        """One dFBA step for cell `cid`: MM-limit its dynamic substrate uptake
        (glucose for competitor/secretor, acetate for consumer) on the footprint's
        mean local concentration, solve, and return the idealized (unclamped)
        (d_biomass, d_substrate, d_acetate_byproduct). `update()` clamps the
        substrate removal against what the field's footprint pixels actually hold
        and scales both growth and the byproduct by the same ratio — mirrors the
        flagship's `_fba`/`update()` mass-conservation split exactly."""
        role = self._roles[cid]
        cfg = self._cell_cfgs[cid]
        m = self._models[cid]
        c = self.config
        km = float(c["acetate_km"]) if role == "consumer" else float(c["glucose_km"])
        vmax_key = "acetate_vmax" if role == "consumer" else "glucose_vmax"
        vmax = float(cfg.get(vmax_key, 10.0))
        v = vmax * local_conc / (km + local_conc) if local_conc > 0 else 0.0
        if role == "consumer":
            m.reactions.EX_ac_e.lower_bound = -float(v)
        else:
            m.reactions.EX_glc__D_e.lower_bound = -float(v)

        sol = m.optimize()
        if sol.status != "optimal":
            # See flagship `_fba`: don't trust `sol.fluxes` on an infeasible solve
            # (stale primal values from the last feasible solve) — growth and
            # secretion both cleanly stop instead.
            return 0.0, 0.0, 0.0

        mu = float(sol.objective_value or 0.0)
        biomass = self.biomass[cid]
        d_biomass = mu * biomass * interval
        box_volume_L = float(c["box_volume_L"])
        ac_flux = float(sol.fluxes.get("EX_ac_e", 0.0))  # >0 secreted, <0 consumed
        d_ac = ac_flux * biomass * interval / box_volume_L
        if role == "consumer":
            d_sub = d_ac  # the dynamic substrate IS EX_ac_e for a consumer
        else:
            glc_flux = float(sol.fluxes.get("EX_glc__D_e", 0.0))  # negative = uptake
            d_sub = glc_flux * biomass * interval / box_volume_L
        return d_biomass, d_sub, d_ac

    @staticmethod
    def _clamp_removal(field, fp, requested_delta):
        """Mass-conservative removal: clamp `requested_delta` (<=0) against what
        `field[fp]` actually holds, spread proportionally to each pixel's current
        value (never drives a pixel negative), and return (clamped_delta,
        per-pixel delta array, clamp ratio to scale correlated deltas by)."""
        area = max(int(fp.sum()), 1)
        per_pixel = np.zeros(int(fp.sum()) if fp.any() else 0)
        if not fp.any():
            return 0.0, per_pixel, 1.0
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

        volume_obs, position_obs = {}, {}
        local_glc_obs, local_ac_obs = {}, {}
        biomass_obs, ac_secreted_obs = {}, {}

        grow_per_biomass = float(self.config["grow_per_biomass"])

        for cid in live_ids:
            if cid not in self._roles:
                continue  # id outside the configured colony (defensive)
            role = self._roles[cid]
            fp = (lat == cid)
            key = str(cid)

            local_glc = float(glucose[fp].mean()) if fp.any() else 0.0
            local_ac = float(acetate[fp].mean()) if fp.any() else 0.0
            local_glc_obs[key] = local_glc
            local_ac_obs[key] = local_ac

            d_biomass, d_sub_request, d_byproduct = self._fba(
                cid, local_ac if role == "consumer" else local_glc, interval)

            if role == "consumer":
                # acetate IS this cell's dynamic substrate: clamp its removal
                # against this cell's own footprint pixels, scale biomass by the
                # same ratio, no separate byproduct writeback.
                clamped, per_pixel, ratio = self._clamp_removal(acetate, fp, d_sub_request)
                d_biomass *= ratio
                if fp.any():
                    dace_total[fp] += per_pixel
                ac_secreted_obs[key] = float(clamped)  # negative: this tick's net uptake
            else:
                # glucose is the dynamic substrate; acetate is a pure byproduct
                # (competitor/secretor's EX_ac_e stays secrete-only, so d_byproduct
                # is always >= 0 — no clamping needed, spread evenly like the
                # flagship spreads its acetate secretion).
                clamped, per_pixel, ratio = self._clamp_removal(glucose, fp, d_sub_request)
                d_biomass *= ratio
                d_byproduct *= ratio
                area = max(int(fp.sum()), 1)
                if fp.any():
                    dglc_total[fp] += per_pixel
                    dace_total[fp] += d_byproduct / area
                ac_secreted_obs[key] = float(d_byproduct)

            self.biomass[cid] = max(self.biomass[cid] + d_biomass, 1e-9)
            biomass_obs[key] = self.biomass[cid]

            target = grow_per_biomass * self.biomass[cid]
            self.world.set_target_volume(cid, max(target, 0.0))

        self.world.step(int(self.config["mcs"]))

        vols = self.world.cell_volumes()
        coms = self.world.cell_coms()
        for cid in live_ids:
            if cid not in self._roles:
                continue
            key = str(cid)
            volume_obs[key] = float(vols[cid])
            position_obs[key] = list(coms[cid])[:2]

        return {
            "fields": {"glucose": dglc_total, "acetate": dace_total},
            "volume": volume_obs,
            "position": position_obs,
            "local_glucose": local_glc_obs,
            "local_acetate": local_ac_obs,
            "biomass": biomass_obs,
            "acetate_secreted": ac_secreted_obs,
        }
