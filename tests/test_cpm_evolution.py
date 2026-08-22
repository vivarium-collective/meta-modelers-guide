# tests/test_cpm_evolution.py
"""Study-9 Task 2: the real `CpmEvolution` process
(`meta_modelers_guide/cpm/evolution.py`) built via `build_core()` /
`local:CpmEvolution` -- not the Task-1 spike harness. Proves the same
selection-shift + no-mutation-control invariants hold through the process
registry + `Composite`, and that the dev/evo observables (`mean_vmax`,
`var_vmax`, `rim_core_ratio`) are actually wired.
"""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")
pytest.importorskip("cobra")

from process_bigraph import Composite

from meta_modelers_guide.core import build_core

NX = NY = 60
FOUNDER_VMAX = 1.5
MUT_SIGMA = 0.3
# Seed 3 is a clearly-rising selection seed (verified in the Task 1 spike /
# the API map: 45 ticks, founder 1.5, sigma 0.3 -> mean 1.500 -> 2.200+).
SELECTION_SEED = 3


def _state(seed, mutate):
    glucose = np.full((NY, NX), 12.0)
    return {
        "fields": {"glucose": glucose, "acetate": np.zeros((NY, NX))},
        "evo": {"_type": "process", "address": "local:CpmEvolution",
            "config": {"grid": {"nx": NX, "ny": NY},
                       "cell": {"seed_block": [27, 27, 0, 33, 33, 1], "target_volume": 40.0,
                                "lambda_volume": 2.0, "temperature": 11.0},
                       "box_volume_L": 0.3, "grow_per_biomass": 40.0,
                       "glucose_km": 0.5, "oxygen_vmax": 15.0, "mcs": 3,
                       "vol_threshold": 80.0, "reset_target": 40.0, "init_biomass": 1.25,
                       "vmax0": FOUNDER_VMAX, "mut_sigma": MUT_SIGMA, "mutate": mutate,
                       "vmax_min": 0.2, "vmax_max": 20.0, "seed": seed,
                       "contact": [{"a": 0, "b": 1, "j": 14.0}, {"a": 1, "b": 1, "j": 14.0}]},
            "inputs": {"fields": ["fields"]},
            "outputs": {"fields": ["fields"], "n_cells": ["obs", "n_cells"],
                        "total_volume": ["obs", "total_volume"], "volume": ["obs", "volume"],
                        "position": ["obs", "position"], "local_glucose": ["obs", "local_glucose"],
                        "biomass": ["obs", "biomass"], "generation": ["obs", "generation"],
                        "vmax": ["obs", "vmax"], "max_generation": ["obs", "max_generation"],
                        "mean_vmax": ["obs", "mean_vmax"], "var_vmax": ["obs", "var_vmax"],
                        "rim_core_ratio": ["obs", "rim_core_ratio"]},
        },
    }


def _run(seed, mutate, steps=45):
    core = build_core()
    comp = Composite({"state": _state(seed, mutate)}, core=core)
    comp.run(steps)
    return comp


def test_selection_shifts_mean_vmax_up():
    """Under selection (`mutate: true`, trait feeds dFBA uptake), the
    population mean vmax ends clearly above the founder value, variance has
    built up (mutation supplied raw material), and the colony compounded."""
    comp = _run(SELECTION_SEED, mutate=True)
    mean_vmax = comp.state["obs"]["mean_vmax"]
    var_vmax = comp.state["obs"]["var_vmax"]
    n_cells = comp.state["obs"]["n_cells"]
    assert mean_vmax > FOUNDER_VMAX + 0.1, (
        f"mean vmax {mean_vmax} did not clearly rise above founder {FOUNDER_VMAX}")
    assert var_vmax > 0.0
    assert n_cells >= 10, "too few cells/divisions for a meaningful selection signal"


def test_rim_core_ratio_shows_heterogeneity():
    """The radial core-vs-rim heterogeneity metric ends > 1 -- the colony's
    core is more glucose-depleted than its rim by the end of the run
    (development, Fig 10c-d's collective interface)."""
    comp = _run(SELECTION_SEED, mutate=True)
    ratio = comp.state["obs"]["rim_core_ratio"]
    assert ratio > 1.0, f"rim_core_ratio {ratio} shows no emergent heterogeneity"


def test_no_mutation_control_is_static():
    """With `mutate: false` (BOOLEAN, not `mut_sigma=0.0`), the mean vmax
    stays EXACTLY the founder value and variance is exactly 0 through the
    real process/Composite path -- no raw material for selection to act on."""
    comp = _run(SELECTION_SEED, mutate=False)
    assert comp.state["obs"]["mean_vmax"] == pytest.approx(FOUNDER_VMAX, abs=1e-9)
    assert comp.state["obs"]["var_vmax"] == pytest.approx(0.0, abs=1e-9)
    assert comp.state["obs"]["n_cells"] >= 2, "need at least one division to exercise the control"
