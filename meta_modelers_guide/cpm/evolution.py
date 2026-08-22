"""CpmEvolution -- study 9's `CpmGrowthDivision` (study 8) subclass, ADDING a
per-cell heritable trait (glucose-uptake `vmax`) inherited-with-mutation on
division, plus radial development + population-trait evolution observables.

This is a MINIMAL subclass built on the base's two hooks
(`growth_division.py`: `_cell_glucose_vmax`, `_on_division`) -- NOT a
duplicated `update()`. The Task 1 spike (`tests/test_cpm_evolution_spike.py`)
proved the mechanism by duplicating `update()` verbatim (its own docstring
flags that as intentional-but-temporary); this module is the promotion the
spike's own "Concerns" section asked for: a small override hook for the
division-pairing step instead of copy-pasting the growth/division loop again.

- ``_cell_glucose_vmax(cid)`` overrides the base's population-wide constant
  with this cell's own heritable trait (``self.vmax[cid]``, falling back to
  ``vmax0`` for any id not yet tracked) -- UNLESS `selection` (a BOOLEAN
  config flag, default True, byte-identical to the pre-flag behavior) is
  False, in which case it returns the FIXED founder `vmax0` for every cell
  regardless of `self.vmax`. The trait still mutates and is recorded either
  way (`_on_division` doesn't consult `selection`); with `selection: false`
  it just confers no fitness, so any drift is undirected -- the no-selection
  control (study 9's dual control, alongside `mutate: false`'s no-mutation
  control).
- ``_on_division(parent_id, daughter_id)`` overrides the base's no-op hook:
  the daughter's trait is drawn from the parent's trait +/- Gaussian
  mutation (seeded RNG), clamped to ``[vmax_min, vmax_max]``; the parent
  keeps its own trait unchanged. `mutate` is a BOOLEAN config flag (never a
  `mut_sigma: 0.0` float override -- bigraph_schema silently drops a `0.0`
  float override, keeping the schema default, so a float-gated "no mutation"
  arm would secretly keep mutating; see the spike module docstring).
- ``__init__`` is NOT reached through the base's `__init__`/`super()` chain:
  the base hardcodes `potts.seed=1` when building the CPM world, which would
  make every "different seed" config replay the same Metropolis trajectory.
  So, like the spike, this constructor calls `Process.__init__` directly and
  replicates the base's (short) world-construction body itself, threading
  `seed` into BOTH the potts spec and the mutation RNG. This duplication is
  small and intentional -- only `__init__` is repeated, never `update()`.
- ``update()`` calls `super().update()` (the base's UNCHANGED growth +
  native-`divide_cells` + biomass/lineage loop, now using this subclass's
  hooks internally) and layers the dev/evo observables on top of its return
  value: `vmax` (per-cell), `mean_vmax`/`var_vmax` (population trait
  statistics -- evolution), and `rim_core_ratio` (radial core-vs-rim
  heterogeneity from `local_glucose` binned by distance from the colony
  centroid -- development, Fig 10c-d's "collective interface"; verified in
  ``docs/superpowers/api-maps/2026-08-22-development-and-evolution-api-map.md``
  Q1: rim/core glucose ratio grows 1.003 -> 1.096 as the colony develops).
"""
from __future__ import annotations

import numpy as np
from process_bigraph import Process

from .growth_division import CpmGrowthDivision, _DEFAULT_CELL_TYPE, _f


class CpmEvolution(CpmGrowthDivision):
    config_schema = {
        **CpmGrowthDivision.config_schema,
        "mutate": {"_type": "boolean", "_default": True},
        "selection": {"_type": "boolean", "_default": True},
        "mut_sigma": _f(0.3),
        "vmax0": _f(1.5),
        "vmax_min": _f(0.2),
        "vmax_max": _f(20.0),
        "seed": {"_type": "integer", "_default": 1},
    }

    def outputs(self):
        base = dict(super().outputs())
        base.update({
            "vmax": "overwrite[map[float]]",
            "mean_vmax": "overwrite[float]",
            "var_vmax": "overwrite[float]",
            "rim_core_ratio": "overwrite[float]",
        })
        return base

    def __init__(self, config=None, core=None):
        # Deliberately bypass `CpmGrowthDivision.__init__` -- it hardcodes
        # `potts.seed=1`. Go straight to the grandparent `Process.__init__`
        # (fills `self.config` from `config_schema`) and replicate the rest
        # of the base's (short) world-construction body ourselves so `seed`
        # reaches the potts spec too. `update()`/`_fba`/division logic are
        # NOT duplicated -- those are reused unchanged via the base's hooks.
        Process.__init__(self, config, core=core)
        from cpm.schema import load_world
        try:
            from cobra.io import load_model
        except Exception as exc:  # pragma: no cover - exercised only without cobra
            raise RuntimeError(
                "CpmEvolution requires the optional 'cobra' package "
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

        seed = int(c.get("seed", 1))
        spec = {
            "potts": {"dims": [nx, ny, 1], "boundary": "noflux", "neighbor_order": 2,
                      "temperature": temperature, "seed": seed},
            "cells": [{"type": _DEFAULT_CELL_TYPE, "target_volume": target_volume,
                       "lambda_volume": lambda_volume, "target_surface": 0.0,
                       "lambda_surface": 0.0, "seed_block": seed_block}],
            "contact": contact,
        }
        self.world = load_world(spec)

        # cell id 1 is the sole founder (id 0 reserved for medium).
        self._models: dict[int, object] = {}
        self.biomass: dict[int, float] = {}
        self.lineage: dict[int, int] = {}
        self.generation: dict[int, int] = {1: 0}
        self.max_generation: int = 0

        # --- evolution bookkeeping (the addition over study 8) ------------
        self._rng = np.random.default_rng(seed)  # `seed` also drives mutation draws
        self.vmax: dict[int, float] = {1: float(c["vmax0"])}

        self._new_model(1, float(c["init_biomass"]))

    def _cell_glucose_vmax(self, cid):
        """Per-cell heritable trait, not the population-wide constant --
        UNLESS `selection` is False, in which case the trait still mutates
        and is recorded (`self.vmax`), but confers NO fitness: every cell's
        dFBA uses the fixed founder `vmax0`, so any drift in the trait is
        undirected (the no-selection control). `selection` defaults True,
        keeping this path byte-identical to the pre-flag behavior."""
        vmax0 = float(self.config["vmax0"])
        if not bool(self.config.get("selection", True)):
            return vmax0
        return float(self.vmax.get(cid, vmax0))

    def _on_division(self, parent_id, daughter_id):
        """Daughter inherits the parent's trait +/- Gaussian mutation
        (seeded RNG), clamped to [vmax_min, vmax_max]; the parent keeps its
        own trait unchanged. `mutate` gates the draw as a BOOLEAN flag."""
        c = self.config
        mutate = bool(c.get("mutate", True))
        mut_sigma = float(c["mut_sigma"])
        vmax_min = float(c["vmax_min"])
        vmax_max = float(c["vmax_max"])
        parent_vmax = self.vmax.get(parent_id, float(c["vmax0"]))
        delta = float(self._rng.normal(0.0, mut_sigma)) if mutate else 0.0
        self.vmax[daughter_id] = float(np.clip(parent_vmax + delta, vmax_min, vmax_max))

    @staticmethod
    def _rim_core_ratio(position_obs, local_glucose_obs):
        """Radial core-vs-rim heterogeneity (development, Fig 10c-d): bin
        live cells by Euclidean distance from the colony centroid (median
        split into core <= median, rim > median), compare mean
        `local_glucose` between the two groups. rim/core > 1 means the core
        is more glucose-depleted than the rim -- an emergent "collective
        interface", not an imposed structure. Falls back to 1.0 (no readable
        gradient yet) when there are too few live cells to split, or the
        core group's mean glucose is non-positive."""
        ids = sorted(position_obs.keys())
        if len(ids) < 2:
            return 1.0
        positions = np.array([position_obs[cid] for cid in ids], dtype=float)
        centroid = positions.mean(axis=0)
        dist = np.linalg.norm(positions - centroid, axis=1)
        median = float(np.median(dist))
        core_mask = dist <= median
        rim_mask = ~core_mask
        if not core_mask.any() or not rim_mask.any():
            return 1.0
        glc = np.array([local_glucose_obs.get(cid, 0.0) for cid in ids], dtype=float)
        core_mean = float(glc[core_mask].mean())
        rim_mean = float(glc[rim_mask].mean())
        if core_mean <= 0.0:
            return 1.0
        return rim_mean / core_mean

    def update(self, state, interval):
        # Reuse the base's UNCHANGED growth + native-divide_cells + biomass/
        # lineage loop -- it already calls our `_cell_glucose_vmax` and
        # `_on_division` hooks internally.
        out = super().update(state, interval)

        vmax_obs = {key: float(self.vmax.get(int(key), self.config["vmax0"]))
                    for key in out["volume"].keys()}
        trait_values = list(vmax_obs.values())
        mean_vmax = float(np.mean(trait_values)) if trait_values else float(self.config["vmax0"])
        var_vmax = float(np.var(trait_values)) if trait_values else 0.0
        rim_core_ratio = self._rim_core_ratio(out["position"], out["local_glucose"])

        out = dict(out)
        out["vmax"] = vmax_obs
        out["mean_vmax"] = mean_vmax
        out["var_vmax"] = var_vmax
        out["rim_core_ratio"] = rim_core_ratio
        return out
