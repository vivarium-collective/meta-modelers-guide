"""Protocell -- wraps the Task-1 reaction-diffusion protocell physics
(`tests/test_protocell_physics.py`) as a `fields`-store process, emitting the
boundary-integrity metric (`enclosed_area`) plus a gated `persists` flag.

The physics is unchanged: `laplacian`/`enclosed_area`/`seed_annulus`/`rd_step`
are lifted verbatim from the Task-1 spike into
`meta_modelers_guide/protocell/autopoiesis.py`. What this test verifies is the
process wrapping:

1. Registration + the additive `fields` map[array] field-write contract (same
   convention as `condensate/cahn_hilliard.py`'s `CahnHilliard`): built through
   `build_core()`/`Composite` at `local:Protocell`, the store must end up
   holding the actual new `phi` (not double-counted), cross-checked against an
   independent reference trajectory computed directly with `rd_step`.
2. The closed loop (canonical params) reaches `persists == 1.0` with
   `enclosed_area > 0` and `collapse_tick == -1.0` -- run WITHIN the ~2000-step
   homeostatic-plateau window established by Task 1 (the plateau is
   metastable and eventually runs down past ~2450-2650 steps; this test does
   not probe that far).
3. The negative control (`k_prod=0`) collapses: `persists == 0.0`,
   `enclosed_area == 0.0`, `collapse_tick > 0`.
4. The CFL guard (`D*dt*4 < 1`) raises a clear error instead of silently
   admitting an unstable config.
"""
from __future__ import annotations

import numpy as np
import pytest

from meta_modelers_guide.protocell.autopoiesis import Protocell, rd_step, seed_annulus

N = 64
THR = 0.30
D, K_DECAY, K_PROD, DT = 0.02, 0.01, 0.03, 1.0


def _build_composite(core, *, k_prod, steps_per_tick, phi0):
    from process_bigraph import Composite

    state = {
        "fields": {"phi": phi0.copy()},
        "protocell": {
            "_type": "process",
            "address": "local:Protocell",
            "config": {
                "grid": {"nx": N, "ny": N},
                "D": D,
                "k_decay": K_DECAY,
                "k_prod": k_prod,
                "thr": THR,
                "dt": DT,
                "steps_per_tick": steps_per_tick,
                "seed": 1,
            },
            "inputs": {"fields": ["fields"]},
            "outputs": {
                "fields": ["fields"],
                "enclosed_area": ["obs", "enclosed_area"],
                "membrane_mass": ["obs", "membrane_mass"],
                "persists": ["obs", "persists"],
                "collapse_tick": ["obs", "collapse_tick"],
            },
        },
    }
    return Composite({"state": state}, core=core)


def test_closed_loop_persists_within_stable_window():
    pytest.importorskip("process_bigraph")
    from meta_modelers_guide.core import build_core

    core = build_core()
    phi0 = seed_annulus(n=N)
    steps_per_tick = 200
    n_ticks = 9  # 1800 total internal steps -- comfortably inside the ~2000-step
    #  homeostatic-plateau window (Task 1: stable through ~2600, plateau accepted
    #  as metastable, not perpetual).

    comp = _build_composite(core, k_prod=K_PROD, steps_per_tick=steps_per_tick, phi0=phi0)

    # Independent reference trajectory computed directly with rd_step, advanced
    # the same total number of steps -- what the store SHOULD hold if the
    # delta-write is correct (not double-counted by the additive `fields` apply).
    seed_area = None
    from meta_modelers_guide.protocell.autopoiesis import enclosed_area as _enclosed_area
    seed_area = int(_enclosed_area(phi0, THR).sum())
    ref = phi0.copy()
    for _ in range(n_ticks):
        for _ in range(steps_per_tick):
            ref = rd_step(ref, D, K_DECAY, K_PROD, seed_area, thr=THR, dt=DT)

    for _ in range(n_ticks):
        comp.run(1)

    got = np.asarray(comp.state["fields"]["phi"])
    assert np.allclose(got, ref, atol=1e-6)  # store tracks phi_new, not phi_new*2

    obs = comp.state["obs"]
    assert obs["persists"] == 1.0
    assert obs["enclosed_area"] > 0
    assert obs["collapse_tick"] == -1.0  # never collapsed within the window
    assert obs["membrane_mass"] > 0


def test_negative_control_k_prod_zero_collapses():
    pytest.importorskip("process_bigraph")
    from meta_modelers_guide.core import build_core

    core = build_core()
    phi0 = seed_annulus(n=N)
    steps_per_tick = 50
    n_ticks = 6  # 300 total internal steps -- well past the <150-step collapse
    #  observed in the Task-1 physics test for this negative control.

    comp = _build_composite(core, k_prod=0.0, steps_per_tick=steps_per_tick, phi0=phi0)
    for _ in range(n_ticks):
        comp.run(1)

    obs = comp.state["obs"]
    assert obs["persists"] == 0.0
    assert obs["enclosed_area"] == 0.0
    assert obs["collapse_tick"] > 0


def test_cfl_guard_raises_for_unstable_dt():
    from meta_modelers_guide.core import build_core

    with pytest.raises(ValueError):
        Protocell(
            config={
                "grid": {"nx": N, "ny": N},
                "D": 0.5,  # D*dt*4 = 2.0 >= 1 -- unstable
                "k_decay": K_DECAY,
                "k_prod": K_PROD,
                "thr": THR,
                "dt": DT,
                "steps_per_tick": 1,
                "seed": 1,
            },
            core=build_core(),
        )
