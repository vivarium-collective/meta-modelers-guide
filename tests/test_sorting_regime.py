"""The two flagship composites, each locking one demonstrating claim end-to-end
from its `.composite.json` spec (not the raw process): `cell-sorting-spatial`
demixes (hetero_frac collapses) while staying cohesive (cell_pixels + per-type
counts hold) -- a dissolved clump must NOT pass. `condensate-cahn-hilliard`
phase-separates (phi_var rises) while conserving mass (phi_mean holds), staying
bounded, and emitting no NaN.

The composite's first observation lands AFTER its first `mcs`-chunk of internal
dynamics, so the emitted hetero_frac start is already partway sorted (~0.6, not
the raw well-mixed ~1.0 seeded checkerboard) -- see tests/test_cpm_sorting.py's
comment for the underlying reason. Thresholds below were observed directly
(with margin) by running each composite spec here before writing the asserts.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from process_bigraph import Composite

from meta_modelers_guide.core import build_core

COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"

pytest.importorskip("cpm")


def _load(name):
    spec = json.loads((COMPOSITES / f"{name}.composite.json").read_text())
    return Composite({"state": spec["state"]}, core=build_core())


def test_sorting_demixes_cohesively():
    comp = _load("cell-sorting-spatial")

    comp.run(1)                                          # one tick (10 mcs): early baseline
    obs0 = dict(comp.state["obs"])
    p0 = obs0["cell_pixels"]
    assert obs0["hetero_frac"] > 0.5                       # clearly-mixed start (observed ~0.64)
    assert obs0["n_type1"] == 32 and obs0["n_type2"] == 32  # 8x8 checkerboard, even split

    for _ in range(59):
        comp.run(10)                                      # 59*10 = 590 more mcs (~600 total)
    obs = comp.state["obs"]

    assert obs["hetero_frac"] < 0.2                         # sorted (observed ~0.055)
    assert abs(obs["cell_pixels"] - p0) < 0.10 * p0          # cohesion guard: clump did NOT dissolve
    assert obs["n_type1"] == 32 and obs["n_type2"] == 32     # cell counts unchanged


def test_cahn_hilliard_phase_separates_mass_conserved():
    comp = _load("condensate-cahn-hilliard")

    comp.run(1)                                           # one tick (200 CH steps): early baseline
    obs0 = dict(comp.state["obs"])
    mean0 = obs0["phi_mean"]
    assert obs0["phi_var"] < 0.01                           # still near-flat (observed ~7e-5)

    for _ in range(49):
        comp.run(1)                                        # 49 more ticks (~10000 CH steps total)
    obs = comp.state["obs"]

    assert obs["phi_var"] > 0.3                              # phase-separated (observed ~0.38)
    assert abs(obs["phi_mean"] - mean0) < 1e-3                # mass conserved (observed ~4e-18 drift)
    assert -1.05 < obs["phi_min"]
    assert obs["phi_max"] < 1.05                              # bounded domains
    assert not math.isnan(obs["phi_var"])
    assert not math.isnan(obs["phi_mean"])
