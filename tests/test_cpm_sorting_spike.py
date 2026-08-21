"""Differential-adhesion cell sorting (Steinberg): a mixed 2-type checkerboard demixes
under CPM contact energetics — heterotypic interface collapses while the clump stays
cohesive (the guard that a dissolved clump isn't misread as 'sorted')."""
from __future__ import annotations
import numpy as np
import pytest
pytest.importorskip("cpm")
from cpm.schema import load_world

NX = NY = 70

def _checkerboard(n=8, size=5, x0=15, y0=15):
    cells = []
    for r in range(n):
        for c in range(n):
            t = 1 if (r + c) % 2 == 0 else 2
            x, y = x0 + c * size, y0 + r * size
            cells.append({"type": t, "target_volume": 25.0, "lambda_volume": 2.0,
                          "target_surface": 0.0, "lambda_surface": 0.0,
                          "seed_block": [x, y, 0, x + size, y + size, 1]})
    return cells

def _world():
    return load_world({
        "potts": {"dims": [NX, NY, 1], "boundary": "noflux", "neighbor_order": 2,
                  "temperature": 10.0, "seed": 1},
        "cells": _checkerboard(),
        "contact": [{"a": 0, "b": 1, "j": 8.0}, {"a": 0, "b": 2, "j": 8.0},
                    {"a": 1, "b": 1, "j": 2.0}, {"a": 2, "b": 2, "j": 2.0},
                    {"a": 1, "b": 2, "j": 11.0}],
    })

def hetero_frac(w):
    # "Intercell" = between two DIFFERENT cells; interior same-id pixel pairs
    # (which dominate a 5x5 block) are intracell, not intercell, and must be excluded.
    lat = np.array(w.snapshot()).reshape(NY, NX); types = w.cell_types()
    hetero = total = 0
    for i in range(NY):
        for j in range(NX):
            a = lat[i, j]
            if a == 0: continue
            for di, dj in ((0, 1), (1, 0)):
                ii, jj = i + di, j + dj
                if ii < NY and jj < NX and lat[ii, jj] > 0:
                    b = lat[ii, jj]
                    if b == a: continue
                    total += 1
                    if types[a] != types[b]: hetero += 1
    return hetero / total if total else 0.0

def cell_pixels(w):
    return int((np.array(w.snapshot()) > 0).sum())

def test_checkerboard_demixes_and_stays_cohesive():
    w = _world()
    f0, p0 = hetero_frac(w), cell_pixels(w)
    assert f0 > 0.8                                  # starts well-mixed
    for _ in range(60):
        w.step(10)                                    # ~600 MCS
    f1, p1 = hetero_frac(w), cell_pixels(w)
    assert f1 < 0.2                                   # sorted: heterotypic interface collapsed
    assert abs(p1 - p0) < 0.10 * p0                   # cohesion guard: clump did NOT dissolve
