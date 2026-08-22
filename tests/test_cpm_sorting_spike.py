"""Differential-adhesion cell sorting (Steinberg): a mixed 2-type checkerboard demixes
under CPM contact energetics — heterotypic interface collapses while the clump stays
cohesive (the guard that a dissolved clump isn't misread as 'sorted').

`hetero_frac`/`cell_pixels`/`checkerboard_cells` are factored into
``meta_modelers_guide.cpm.sorting`` (and reused by the `CpmSorting` process
itself, see ``tests/test_cpm_sorting.py``) — this module now just exercises them
directly against a bare ``cpm`` world, one level below the process-bigraph
Composite, as a fast raw-API regression check."""
from __future__ import annotations
import numpy as np
import pytest
pytest.importorskip("cpm")
from cpm.schema import load_world
from meta_modelers_guide.cpm.sorting import checkerboard_cells, hetero_frac, cell_pixels

NX = NY = 70

def _world():
    return load_world({
        "potts": {"dims": [NX, NY, 1], "boundary": "noflux", "neighbor_order": 2,
                  "temperature": 10.0, "seed": 1},
        "cells": checkerboard_cells(n=8, size=5, x0=15, y0=15,
                                     target_volume=25.0, lambda_volume=2.0),
        "contact": [{"a": 0, "b": 1, "j": 8.0}, {"a": 0, "b": 2, "j": 8.0},
                    {"a": 1, "b": 1, "j": 2.0}, {"a": 2, "b": 2, "j": 2.0},
                    {"a": 1, "b": 2, "j": 11.0}],
    })

def _lattice(w):
    return np.array(w.snapshot()).reshape(NY, NX)

def test_checkerboard_demixes_and_stays_cohesive():
    w = _world()
    f0, p0 = hetero_frac(_lattice(w), w.cell_types()), cell_pixels(_lattice(w))
    assert f0 > 0.8                                  # starts well-mixed
    for _ in range(60):
        w.step(10)                                    # ~600 MCS
    f1, p1 = hetero_frac(_lattice(w), w.cell_types()), cell_pixels(_lattice(w))
    assert f1 < 0.2                                   # sorted: heterotypic interface collapsed
    assert abs(p1 - p0) < 0.10 * p0                   # cohesion guard: clump did NOT dissolve
