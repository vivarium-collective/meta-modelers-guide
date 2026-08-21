"""Prove the flagship composition primitives: a CPM cell world runs, its lattice +
COM are readable, and a spatio-flux DiffusionAdvection field composes over a shared
(ny,nx) grid — all addressed by full import path."""
from __future__ import annotations
import numpy as np
import pytest
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

# The flagship composition depends on optional frameworks that are editable-installed
# locally but absent from the base CI image (cpm needs a Rust/maturin build); skip
# rather than fail when they are unavailable.
pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")

NX = NY = 40

def _cpm_spec(nx=NX, ny=NY):
    return {
        "potts": {"dims": [nx, ny, 1], "boundary": "noflux",
                  "neighbor_order": 2, "temperature": 10.0, "seed": 1},
        "cells": [{"type": 1, "target_volume": 60.0, "lambda_volume": 2.0,
                   "target_surface": 0.0, "lambda_surface": 0.0,
                   "seed_block": [17, 17, 0, 24, 24, 1]}],  # half-open; z1=1 for 2D
        "contact": [{"a": 0, "b": 1, "j": 14.0}],
    }

def test_cpm_world_runs_and_lattice_readable():
    from cpm.schema import load_world
    world = load_world(_cpm_spec())
    world.step(5)
    lattice = np.array(world.snapshot()).reshape(NY, NX)
    assert lattice.shape == (NY, NX)
    assert (lattice > 0).sum() > 0                     # the cell occupies pixels
    coms = world.cell_coms()
    assert len(coms) >= 2 and 0 < coms[1][0] < NX      # cell 1 has a COM in-bounds

def test_diffusion_advection_composes_full_address():
    core = build_core()
    field = np.zeros((NY, NX)); field[NY//2, NX//2] = 100.0
    state = {
        "fields": {"glucose": field},
        "diff": {"_type": "process",
                 "address": "local:!spatio_flux.processes.diffusion_advection.DiffusionAdvection",
                 "config": {"n_bins": (NX, NY), "bounds": (float(NX), float(NY)),
                            "diffusion_coeffs": {"glucose": 0.5},
                            "boundary_conditions": {"glucose": {"default": {"type": "neumann"}}}},
                 "inputs": {"fields": ["fields"]}, "outputs": {"fields": ["fields"]}},
    }
    comp = Composite({"state": state}, core=core)
    before = float(np.sum(comp.state["fields"]["glucose"]))
    comp.run(5)
    after = float(np.sum(comp.state["fields"]["glucose"]))
    assert abs(after - before) < 1e-6                  # mass conserved under neumann
    assert comp.state["fields"]["glucose"][NY//2, NX//2] < 100.0  # spread out
