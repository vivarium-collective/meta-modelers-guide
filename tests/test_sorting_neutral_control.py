"""Neutral-J negative control for the biomolecular differential-adhesion sorting
study -- promoted from a documented regime sweep to a committed, rerunnable
pytest (peer-review: minor 11 / the study's SORTING-NEUTRAL-J-DOES-NOT-SORT
control).

The sorting flagship (``cell-sorting-spatial``) demixes a mixed checkerboard
because heterotypic contact is made expensive (J(1,2)=11) relative to homotypic
(J(1,1)=J(2,2)=2). The causal claim is that the *contact-energy asymmetry*
drives the demixing, not the CPM Metropolis dynamics per se. This is the
control that isolates that variable: run the SAME 8x8 checkerboard, at the SAME
temperature (10.0), with the SAME volume constraints and mcs schedule, but with
NEUTRAL contact energies -- every pair set to J=8, so heterotypic contact is no
costlier than homotypic. With the thermodynamic drive to demix removed, the
checkerboard must stay mixed: ``hetero_frac`` stays high instead of collapsing.

Previously this was "a documented regime sweep, not a committed pytest"; this
file runs the neutral-J composite end-to-end through the process-bigraph engine
and asserts the control result, so it now reruns with the suite.

Observed (deterministic, cpm world seed=1): neutral-J ``hetero_frac`` ~0.52 at
~600 MCS, versus ~0.06 for the differential-J flagship. The assertion floor is
set well below the observed ~0.52 (and far above the flagship's sorted ~0.06)
so the control is robust while still unambiguously distinguishing "stayed mixed"
from "sorted".
"""
from __future__ import annotations

import pytest
from process_bigraph import Composite

from meta_modelers_guide.core import build_core

pytest.importorskip("cpm")

NX = NY = 70
NEUTRAL_J = 8.0

# The flagship's sorted end-state; the neutral control must stay far above this.
SORTED_HETERO_FRAC = 0.2


def _neutral_state():
    """The cell-sorting-spatial flagship config, with every contact energy set
    to the SAME neutral J -- the only change from the sorting composite."""
    contact = [
        {"a": 0, "b": 1, "j": NEUTRAL_J},
        {"a": 0, "b": 2, "j": NEUTRAL_J},
        {"a": 1, "b": 1, "j": NEUTRAL_J},
        {"a": 2, "b": 2, "j": NEUTRAL_J},
        {"a": 1, "b": 2, "j": NEUTRAL_J},
    ]
    return {
        "cell": {
            "_type": "process",
            "address": "local:CpmSorting",
            "config": {
                "grid": {"nx": NX, "ny": NY},
                "checkerboard": {"n": 8, "size": 5, "x0": 15, "y0": 15},
                "contact": contact,
                "temperature": 10.0,
                "target_volume": 25.0,
                "lambda_volume": 2.0,
                "mcs": 10,
            },
            "inputs": {},
            "outputs": {
                "hetero_frac": ["obs", "hetero_frac"],
                "cell_pixels": ["obs", "cell_pixels"],
                "n_type1": ["obs", "n_type1"],
                "n_type2": ["obs", "n_type2"],
                "type": ["obs", "type"],
                "position": ["obs", "position"],
                "volume": ["obs", "volume"],
            },
        },
    }


def test_neutral_J_does_not_sort():
    """Under neutral contact energies (all J=8) the checkerboard stays mixed --
    the causal control proving differential adhesion, not CPM dynamics, drives
    the flagship's sorting."""
    core = build_core()
    comp = Composite({"state": _neutral_state()}, core=core)

    comp.run(1)  # one tick (10 mcs): early baseline
    obs0 = dict(comp.state["obs"])
    p0 = obs0["cell_pixels"]
    assert obs0["n_type1"] == 32 and obs0["n_type2"] == 32  # 8x8 checkerboard, even split
    assert obs0["hetero_frac"] > 0.5  # starts clearly mixed

    for _ in range(59):
        comp.run(10)  # 59*10 = 590 more mcs (~600 total), matching the flagship run length
    obs = comp.state["obs"]

    # THE CONTROL RESULT: no demixing. hetero_frac stays high (observed ~0.52),
    # nowhere near the flagship's sorted ~0.06.
    assert obs["hetero_frac"] > 0.4, (
        f"neutral-J control unexpectedly sorted: hetero_frac fell to "
        f"{obs['hetero_frac']:.3f} (<= 0.4) with all J equal -- the flagship's "
        f"demixing would then NOT be attributable to contact-energy asymmetry"
    )
    assert obs["hetero_frac"] > SORTED_HETERO_FRAC  # unambiguously not the sorted regime

    # Cohesion guard: the "no sort" reading is only valid if the clump did not
    # dissolve (a dissolved clump reads as hetero_frac -> 0, a false "sort").
    assert abs(obs["cell_pixels"] - p0) < 0.10 * p0
    assert obs["n_type1"] == 32 and obs["n_type2"] == 32  # cells conserved, just not sorted
    assert len(obs["type"]) == 64  # all 64 cells still live
