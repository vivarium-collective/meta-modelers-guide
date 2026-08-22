"""CpmDisintegration — a coherent CPM cell that dissolves once a shared spatio-flux
stressor field crosses its viability threshold, shedding its vacated pixels as
particles into a shared ``map[particle]`` store.

Owns the CPM world exactly like the flagship ``CpmCellField`` (the lattice + growth
are not process-bigraph stores, so a single world-owning process is the clean
coupling point), but with NO metabolism/cobra path at all: this study is about the
viability-collapse *trigger*, not nutrient uptake. Each tick it reads a shared
``stressor`` field at the cell's own footprint (`snapshot()==cid`), and once
``mean(stressor[footprint]) >= viability_threshold`` it LATCHES a `released` flag
(never un-crosses, even once the footprint empties and reads 0.0 -- see API map
Q6) and ramps `set_target_volume(cid) -> 0` via `resorb_per_tick`. Connectivity
(E1) and `lambda_volume`/`temperature` are NOT usable as runtime fragmentation
levers (verified no-op / init-only in the API map) -- the only real driver of
"dissolution" is target-volume resorption; particle emission is a separate,
verified-working bridge (see below), not a CPM-native shatter.

Particle bridge (verified shape, docs/superpowers/api-maps/2026-08-21-disintegration-
api-map.md §5): after release, each tick diffs the previous vs current footprint
mask (`vacated = prev_fp & ~curr_fp`), and for up to `max_particles_per_tick`
vacated pixels emits ONE new particle apiece at its mapped pixel-center via the
map `_add` sentinel, with ids from a monotonic counter (never random/uuid/time).
A separate process (stock `BrownianMovement`, wired in a later task) is what
actually scatters the emitted particles -- this process never moves them itself.

Mask-timing order (documented per the brief): snapshot the footprint BEFORE
`world.step(mcs)` (this is `self._prev_fp`, carried from the end of the previous
tick / the initial post-init footprint), run the CPM step, then snapshot AGAIN
to get the post-step footprint (`curr_fp`). `vacated = prev_fp & ~curr_fp` is
therefore "pixels this cell held before the step that it no longer holds after
the step" -- exactly the pixels the resorption ramp just gave up. `self._prev_fp`
is then updated to `curr_fp` for next tick's diff.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage
from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


class CpmDisintegration(Process):
    config_schema = {
        # NOTE: no `_default` on container-typed leaves (`grid`, `bounds`, `cell`,
        # `contact`) -- bigraph-schema's generic "list"/container apply *merges*
        # a schema-declared `_default` with an incoming config value on
        # composition rather than replacing it (the flagship's `seed_block`
        # comment, `cell_field.py`), so a caller-supplied dict/list would get
        # spuriously concatenated with any default here. Python-side defaulting
        # in `__init__` avoids that trap entirely.
        "grid": {"_type": "map[integer]"},
        "bounds": {"_type": "map[float]"},
        "cell": {"_type": "schema"},
        "contact": {"_type": "list"},
        "viability_threshold": _f(0.5),
        "resorb_per_tick": _f(6.0),
        "max_particles_per_tick": {"_type": "integer", "_default": 8},
        "mcs": {"_type": "integer", "_default": 3},
        # Which species in the shared `fields` store carries the viability
        # stressor. Default `"stressor"` for backward compatibility (the
        # process/regime tests that build their own state with a `"stressor"`
        # field stay green); the disintegration-spatial composite sets this to
        # `"acetate"` so the stressor IS the cross-feeding byproduct molecule --
        # waste/food in cell-cell-coupling-spatial, toxin here (the paper's
        # relational-molecule claim). The observable stays named `mean_stressor`
        # (it is the mean stressor reading; the stressor is now acetate).
        "stressor_field": {"_type": "string", "_default": "stressor"},
    }

    def inputs(self):
        return {"fields": "map[array]"}

    def outputs(self):
        # `volume`/`area`/`position`/`mean_stressor`/`n_components`/
        # `largest_fragment_fraction`/`released`/`released_tick` are this tick's
        # absolute readings, not deltas -- same reasoning as the flagship's
        # `overwrite[...]` outputs (`cell_field.py` docstring): plain float/list
        # apply is additive/concatenating and would silently corrupt a multi-tick
        # run. `particles` is a genuine incremental `map[particle]` store (grows
        # via the `_add` sentinel), so it stays plain `map[particle]`.
        return {
            "particles": "map[particle]",
            "volume": "overwrite[float]",
            "area": "overwrite[float]",
            "position": "overwrite[list]",
            "mean_stressor": "overwrite[float]",
            "n_components": "overwrite[float]",
            "largest_fragment_fraction": "overwrite[float]",
            "released": "overwrite[boolean]",
            "released_tick": "overwrite[float]",
        }

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        from cpm.schema import load_world
        c = self.config

        grid = dict(c.get("grid") or {})
        nx, ny = int(grid.get("nx", 40)), int(grid.get("ny", 40))
        self._nx, self._ny = nx, ny

        bounds = dict(c.get("bounds") or {})
        self._bx = float(bounds.get("x", nx))
        self._by = float(bounds.get("y", ny))

        cell_cfg = dict(c.get("cell") or {})
        seed_block = list(cell_cfg.get("seed_block") or [16, 16, 0, 24, 24, 1])
        target_volume = float(cell_cfg.get("target_volume", 64.0))
        lambda_volume = float(cell_cfg.get("lambda_volume", 2.0))
        # moderate temperature (10-12) for a clean coherent baseline -- higher
        # temperatures fragment the cell on their own even at cohesive contact J
        # (API map Q6), and temperature cannot be lowered again after init.
        temperature = float(cell_cfg.get("temperature", 11.0))

        contact = list(c.get("contact") or [{"a": 0, "b": 1, "j": 14.0}])

        spec = {
            "potts": {"dims": [nx, ny, 1], "boundary": "noflux", "neighbor_order": 2,
                      "temperature": temperature, "seed": 1},
            "cells": [{"type": 1, "target_volume": target_volume, "lambda_volume": lambda_volume,
                       "target_surface": 0.0, "lambda_surface": 0.0,
                       "seed_block": seed_block}],
            "contact": contact,
        }
        self.world = load_world(spec)

        self._viability_threshold = float(c["viability_threshold"])
        self._resorb_per_tick = float(c["resorb_per_tick"])
        self._max_particles_per_tick = int(c["max_particles_per_tick"])
        self._mcs = int(c["mcs"])
        self._stressor_field = str(c.get("stressor_field", "stressor"))

        self._target = target_volume
        self._released = False
        self._released_tick = 0.0
        self._tick = 0
        self._pid = 0  # monotonic particle-id counter -- never random/uuid/time

        # seed `_prev_fp` from the just-constructed world's initial footprint so
        # the very first tick's vacated-pixel diff is well-defined (see the
        # module docstring's mask-timing order).
        self._prev_fp = self._footprint()

    def _footprint(self):
        lat = np.array(self.world.snapshot()).reshape(self._ny, self._nx)
        live_ids = sorted(set(int(i) for i in np.unique(lat)) - {0})
        if not live_ids:
            return np.zeros((self._ny, self._nx), dtype=bool)
        cid = live_ids[0]
        return lat == cid

    def _live_id(self):
        lat = np.array(self.world.snapshot()).reshape(self._ny, self._nx)
        live_ids = sorted(set(int(i) for i in np.unique(lat)) - {0})
        return live_ids[0] if live_ids else None

    def _pixel_center(self, row, col):
        x = (col + 0.5) * self._bx / self._nx
        y = (row + 0.5) * self._by / self._ny
        return (float(x), float(y))

    def update(self, state, interval):
        self._tick += 1
        fields = state.get("fields", {})
        stressor = np.asarray(fields.get(self._stressor_field), dtype=float)

        # re-derive the live id every tick (never cached) -- after resorption the
        # id lingers as a zeroed slot in cell_volumes()/cell_coms() (API map Q6).
        cid = self._live_id()

        fp = self._footprint()
        area = max(int(fp.sum()), 1)
        mean_stressor = float(stressor[fp].mean()) if fp.any() else 0.0

        # LATCH: once released, stays released -- an empty footprint reads 0.0
        # for mean_stressor and would otherwise un-cross the threshold.
        if not self._released and mean_stressor >= self._viability_threshold:
            self._released = True
            self._released_tick = float(self._tick)

        if self._released and cid is not None and area > 0:
            new_target = max(self._target - self._resorb_per_tick, 0.0)
            self._target = new_target
            self.world.set_target_volume(cid, new_target)

        self.world.step(self._mcs)

        curr_fp = self._footprint()

        # vacated = pixels held before this step's world.step() that are no
        # longer held after it -- exactly the pixels the resorption ramp just
        # gave up (see module docstring for the mask-timing order). Only shed
        # particles once released: a settling/live CPM footprint naturally
        # fluctuates pixel-to-pixel from ordinary Metropolis energetics even
        # with no resorption underway (the shape wobbles as it equilibrates),
        # which would otherwise emit spurious debris before threshold-cross.
        particles_delta = {}
        if self._released:
            vacated = self._prev_fp & ~curr_fp
            rows, cols = np.nonzero(vacated)
            n_shed = min(len(rows), self._max_particles_per_tick)
            for k in range(n_shed):
                self._pid += 1
                pid = f"debris_{self._pid:06d}"
                pos = self._pixel_center(int(rows[k]), int(cols[k]))
                particles_delta[pid] = {"id": pid, "position": pos, "mass": 1.0}

        self._prev_fp = curr_fp

        # post-step observables, from the post-step footprint/world state.
        area_out = float(curr_fp.sum())
        if curr_fp.any():
            position = list(self.world.cell_coms()[cid])[:2] if cid is not None else [0.0, 0.0]
            volume = float(self.world.cell_volumes()[cid]) if cid is not None else 0.0
        else:
            position = [0.0, 0.0]
            volume = 0.0

        labeled, n_components = ndimage.label(curr_fp)
        if n_components > 0:
            sizes = ndimage.sum(curr_fp, labeled, index=range(1, n_components + 1))
            largest_fragment_fraction = float(np.max(sizes) / area_out) if area_out > 0 else 0.0
        else:
            largest_fragment_fraction = 0.0

        out = {
            "volume": volume,
            "area": area_out,
            "position": position,
            "mean_stressor": mean_stressor,
            "n_components": float(n_components),
            "largest_fragment_fraction": largest_fragment_fraction,
            "released": self._released,
            "released_tick": self._released_tick,
        }
        if particles_delta:
            out["particles"] = {"_add": particles_delta}
        return out
