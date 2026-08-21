"""CpmSorting — differential-adhesion cell sorting (Steinberg): a mixed 2-type
checkerboard demixes under CPM contact energetics alone. Owns the CPM world
exactly like the flagship ``CpmCellField``/``CpmDisintegration`` (the lattice is
not a process-bigraph store, so a single world-owning process is the clean
coupling point), but with NO field input and NO metabolism/cobra path at all:
this study is purely about the sorting *primitive* -- contact-energy-driven
demixing -- not nutrient uptake or growth.

Each tick: ``world.step(mcs)``, then read the lattice + per-cell state back out.
``hetero_frac`` is the fraction of 4-neighbor (right/down) lattice edges between
two DIFFERENT live cells (excluding same-id ``b==a`` pairs -- interior same-id
pixel pairs, which dominate a seed block, are intracell, not intercell, and must
be excluded or the metric never drops below ~0.9 even for a fully sorted clump).
``cell_pixels`` is the total live-pixel count, used as a cohesion guard: a
dissolving/fragmenting clump must not be misread as "sorted" just because its
heterotypic interface shrank along with everything else. Both are factored out
of ``tests/test_cpm_sorting_spike.py`` (the corrected, merged version -- the
same-id-inclusion bug from an earlier draft is NOT reintroduced here) so the
process and any test can share one verified implementation.
"""
from __future__ import annotations

import numpy as np
from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


def hetero_frac(lattice, cell_types):
    """Fraction of 4-neighbor (right/down) lattice edges between two DIFFERENT
    live cells, over the total count of such intercell edges. Same-id (``b==a``)
    neighbor pairs are intracell and excluded. ``lattice`` is a (ny, nx) array of
    cell ids (0 = medium); ``cell_types`` maps cell id -> type (e.g. the CPM
    world's ``cell_types()``). Returns 0.0 if there are no intercell edges at all
    (e.g. a single cell, or an empty lattice)."""
    ny, nx = lattice.shape
    hetero = total = 0
    for i in range(ny):
        for j in range(nx):
            a = lattice[i, j]
            if a == 0:
                continue
            for di, dj in ((0, 1), (1, 0)):
                ii, jj = i + di, j + dj
                if ii < ny and jj < nx and lattice[ii, jj] > 0:
                    b = lattice[ii, jj]
                    if b == a:
                        continue
                    total += 1
                    if cell_types[a] != cell_types[b]:
                        hetero += 1
    return hetero / total if total else 0.0


def cell_pixels(lattice):
    """Total pixel count occupied by any live cell (id > 0) -- the cohesion
    guard: compared tick-to-tick, a large drop means the clump dissolved rather
    than sorted."""
    return int((lattice > 0).sum())


def checkerboard_cells(n, size, x0, y0, target_volume, lambda_volume):
    """Build a checkerboard of ``n x n`` alternating-type ``size x size`` seed
    blocks starting at ``(x0, y0)`` -- the mixed initial condition that
    demixes under sorting. Type alternates 1/2 by ``(row + col) % 2``, giving an
    exact ``n*n // 2`` / ``n*n // 2`` split for even ``n``."""
    cells = []
    for r in range(n):
        for c in range(n):
            t = 1 if (r + c) % 2 == 0 else 2
            x, y = x0 + c * size, y0 + r * size
            cells.append({
                "type": t, "target_volume": target_volume, "lambda_volume": lambda_volume,
                "target_surface": 0.0, "lambda_surface": 0.0,
                "seed_block": [x, y, 0, x + size, y + size, 1],
            })
    return cells


class CpmSorting(Process):
    config_schema = {
        # NOTE: no `_default` on container-typed leaves (`grid`, `checkerboard`,
        # `cells`, `contact`) -- bigraph-schema's generic "list"/container apply
        # *merges* a schema-declared `_default` with an incoming config value on
        # composition rather than replacing it (see the flagship's `seed_block`
        # comment, `cell_field.py`), so a caller-supplied dict/list would get
        # spuriously concatenated with any default here. Python-side defaulting
        # in `__init__` avoids that trap entirely.
        "grid": {"_type": "map[integer]"},
        "checkerboard": {"_type": "map[integer]"},
        "cells": {"_type": "list"},
        "contact": {"_type": "list"},
        "temperature": _f(10.0),
        "target_volume": _f(25.0),
        "lambda_volume": _f(2.0),
        "mcs": {"_type": "integer", "_default": 10},
    }

    def inputs(self):
        return {}

    def outputs(self):
        # per-tick absolute readings, not deltas -- same reasoning as the
        # flagship's `overwrite[...]` outputs: plain float/map apply is
        # additive/concatenating and would silently corrupt a multi-tick run.
        return {
            "hetero_frac": "overwrite[float]",
            "cell_pixels": "overwrite[float]",
            "n_type1": "overwrite[float]",
            "n_type2": "overwrite[float]",
            "type": "overwrite[map[float]]",
            "position": "overwrite[map[list]]",
            "volume": "overwrite[map[float]]",
        }

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        from cpm.schema import load_world

        c = self.config
        grid = dict(c.get("grid") or {})
        nx, ny = int(grid.get("nx", 70)), int(grid.get("ny", 70))
        self._nx, self._ny = nx, ny

        target_volume = float(c["target_volume"])
        lambda_volume = float(c["lambda_volume"])

        cell_cfgs = list(c.get("cells") or [])
        if not cell_cfgs:
            board = dict(c.get("checkerboard") or {})
            cell_cfgs = checkerboard_cells(
                n=int(board.get("n", 8)), size=int(board.get("size", 5)),
                x0=int(board.get("x0", 15)), y0=int(board.get("y0", 15)),
                target_volume=target_volume, lambda_volume=lambda_volume,
            )
        if not cell_cfgs:
            raise ValueError(
                "CpmSorting requires either `checkerboard` or an explicit `cells` list")

        contact = list(c.get("contact") or [
            {"a": 0, "b": 1, "j": 8.0}, {"a": 0, "b": 2, "j": 8.0},
            {"a": 1, "b": 1, "j": 2.0}, {"a": 2, "b": 2, "j": 2.0},
            {"a": 1, "b": 2, "j": 11.0},
        ])

        spec = {
            "potts": {"dims": [nx, ny, 1], "boundary": "noflux", "neighbor_order": 2,
                      "temperature": float(c["temperature"]), "seed": 1},
            "cells": cell_cfgs,
            "contact": contact,
        }
        self.world = load_world(spec)
        self._mcs = int(c["mcs"])

    def _lattice(self):
        return np.array(self.world.snapshot()).reshape(self._ny, self._nx)

    def update(self, state, interval):
        self.world.step(self._mcs)

        lat = self._lattice()
        # cell ids are assigned sequentially in `cells`-list order, starting at 1
        # (id 0 is reserved for medium) -- verified in the study-3 API map; live
        # ids are re-derived from the lattice every tick (never cached).
        live_ids = sorted(set(int(i) for i in np.unique(lat)) - {0})

        types = self.world.cell_types()
        coms = self.world.cell_coms()
        vols = self.world.cell_volumes()

        type_obs, position_obs, volume_obs = {}, {}, {}
        n_type1 = n_type2 = 0
        for cid in live_ids:
            t = int(types[cid])
            key = str(cid)
            type_obs[key] = float(t)
            position_obs[key] = list(coms[cid])[:2]
            volume_obs[key] = float(vols[cid])
            if t == 1:
                n_type1 += 1
            elif t == 2:
                n_type2 += 1

        return {
            "hetero_frac": hetero_frac(lat, types),
            "cell_pixels": float(cell_pixels(lat)),
            "n_type1": float(n_type1),
            "n_type2": float(n_type2),
            "type": type_obs,
            "position": position_obs,
            "volume": volume_obs,
        }
