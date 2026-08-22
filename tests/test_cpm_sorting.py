"""CpmSorting: a mixed 2-type checkerboard, run as a world-owning process inside a
process-bigraph Composite (`local:CpmSorting`, no field input), demixes under CPM
contact energetics -- the heterotypic interface collapses (`hetero_frac` -> low)
while the clump stays cohesive (`cell_pixels` doesn't drop, guarding against a
dissolved clump being misread as 'sorted') and per-type cell counts stay constant
(no cell created/destroyed, just moved)."""
from __future__ import annotations
import pytest
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

pytest.importorskip("cpm")

NX = NY = 70


def _state():
    return {
        "cell": {
            "_type": "process",
            "address": "local:CpmSorting",
            "config": {
                "grid": {"nx": NX, "ny": NY},
                "checkerboard": {"n": 8, "size": 5, "x0": 15, "y0": 15},
                "contact": [{"a": 0, "b": 1, "j": 8.0}, {"a": 0, "b": 2, "j": 8.0},
                            {"a": 1, "b": 1, "j": 2.0}, {"a": 2, "b": 2, "j": 2.0},
                            {"a": 1, "b": 2, "j": 11.0}],
                "temperature": 10.0, "target_volume": 25.0, "lambda_volume": 2.0,
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


def test_checkerboard_sorts_cohesively_in_composite():
    core = build_core()
    comp = Composite({"state": _state()}, core=core)

    # The raw-well-mixed starting fraction (>0.8) is asserted directly against a
    # freshly-constructed bare `cpm` world in `tests/test_cpm_sorting_spike.py`;
    # a process `update()` always runs its configured `mcs` before its first
    # observation exists at all, so by the very first tick sorting is already
    # underway (`comp.run(1)` here is just the earliest baseline this Composite
    # can read). `p0` is the cohesion-guard reference point for the run below.
    comp.run(1)                                          # one tick (10 mcs): early baseline
    obs0 = dict(comp.state["obs"])
    p0 = obs0["cell_pixels"]
    assert obs0["n_type1"] == 32 and obs0["n_type2"] == 32  # 8x8 checkerboard, even split

    for _ in range(59):
        comp.run(10)                                      # 59*10 = 590 more mcs (~600 total)
    obs = comp.state["obs"]

    assert obs["hetero_frac"] < 0.2                        # sorted: heterotypic interface collapsed
    assert abs(obs["cell_pixels"] - p0) < 0.10 * p0         # cohesion guard: clump did NOT dissolve
    assert obs["n_type1"] == 32 and obs["n_type2"] == 32    # cell counts unchanged
    assert set(obs["type"].keys()) == set(obs["volume"].keys()) == set(obs["position"].keys())
    assert len(obs["type"]) == 64                           # all 64 cells still live
