# tests/test_cpm_divide_spike.py
"""Native CPM division: divide_cells splits a grown cell into two mass-conserved
daughters (parent keeps id, one new id), ids stable, no phantom from a tiny split."""
from __future__ import annotations
import numpy as np
import pytest

pytest.importorskip("cpm"); pytest.importorskip("spatio_flux")
from cpm.schema import load_world

NX = NY = 40

def _one_cell(target=150.0):
    return load_world({
        "potts": {"dims": [NX, NY, 1], "boundary": "noflux", "neighbor_order": 2,
                  "temperature": 11.0, "seed": 1},
        "cells": [{"type": 1, "target_volume": target, "lambda_volume": 2.0,
                   "target_surface": 0.0, "lambda_surface": 0.0,
                   "seed_block": [15, 15, 0, 25, 25, 1]}],
        "contact": [{"a": 0, "b": 1, "j": 14.0}, {"a": 1, "b": 1, "j": 14.0}],
    })

def test_divide_splits_one_into_two_mass_conserved():
    w = _one_cell(150.0)
    w.step(40)                                   # grow toward 150
    vol_before = w.cell_volumes()[1]
    new_ids = w.divide_cells(80.0, 40.0)         # threshold 80, daughters reset to 40
    assert len(new_ids) == 1                      # one new daughter id
    ids = sorted(set(int(x) for x in np.unique(w.snapshot())) - {0})
    assert ids == [1, new_ids[0]]                 # parent id 1 kept + the new id
    vols = w.cell_volumes()
    assert abs((vols[1] + vols[new_ids[0]]) - vol_before) <= 2   # mass conserved (±rounding)
    w.step(10)
    ids2 = sorted(set(int(x) for x in np.unique(w.snapshot())) - {0})
    assert ids2 == ids                            # ids stable across further steps

def test_below_threshold_is_noop():
    w = _one_cell(60.0)
    w.step(20)
    assert w.divide_cells(500.0, 40.0) == []      # nothing over threshold -> no split
