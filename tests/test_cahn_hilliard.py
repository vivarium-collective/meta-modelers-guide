"""CahnHilliard -- the independent, uncoupled condensate-phase-separation analogue:
a scalar field phi seeded with near-critical noise spinodally decomposes (phi_var
rises from ~0 toward the coexistence variance) while total mass (mean(phi)) is
conserved and phi stays bounded, at the pinned-stable dt=0.002.

Two things are verified:
1. The pure-numpy physics (`ch_step`/`update()`, no Composite) over ~20000 total
   steps: phi_var rise, mass conservation, boundedness, no NaN.
2. Registration + the additive `fields` map[array] field-write contract: built
   through `build_core()`/`Composite` at `local:CahnHilliard`, the store must end
   up holding the actual new phi (not phi doubled) because the engine SUMS each
   tick's emitted array onto the prior store value -- so `update()` must emit the
   DELTA, not the full new field. Cross-checked against an independent reference
   trajectory computed directly with `ch_step`.
"""
from __future__ import annotations

import numpy as np
import pytest

from meta_modelers_guide.condensate.cahn_hilliard import CahnHilliard, ch_step

N = 64
M, KAPPA, DT = 1.0, 0.5, 0.002


def _seed_phi(n=N, seed=0):
    # near-critical noise: mean 0, +/-0.025, deterministic via a fixed Generator.
    rng = np.random.default_rng(seed)
    return rng.uniform(-0.025, 0.025, size=(n, n))


def test_spinodal_decomposition_conserves_mass_and_stays_bounded():
    phi0 = _seed_phi()
    mean0 = float(phi0.mean())
    var0 = float(phi0.var())
    assert var0 < 0.001                                    # near-critical: starts ~flat

    phi = phi0.copy()
    total_steps = 20000
    for _ in range(total_steps):
        phi = ch_step(phi, M, KAPPA, DT)
        assert np.all(np.isfinite(phi))                     # guard: no NaN/Inf at any step

    var_end = float(phi.var())
    mean_end = float(phi.mean())

    assert var_end > 0.3                                    # phase-separated
    assert abs(mean_end - mean0) < 1e-3                      # mass conserved
    assert -1.05 < float(phi.min())
    assert float(phi.max()) < 1.05                           # bounded domains


def test_dt_above_stability_limit_raises_instead_of_nan():
    # dt=0.05 is well above the ~dx^4/(16*M*kappa) limit for M=1, kappa=0.5 and
    # blows up within a few thousand steps (verified in the API map) -- the
    # process must raise loudly rather than silently emit NaN observables.
    from meta_modelers_guide.core import build_core

    proc = CahnHilliard(config={"grid": {"nx": N, "ny": N}, "M": M, "kappa": KAPPA,
                                 "dt": 0.05, "steps_per_tick": 5000}, core=build_core())
    state = {"fields": {"phi": _seed_phi()}}
    with pytest.raises(FloatingPointError):
        proc.update(state, 1.0)


def test_registers_and_resolves_as_local_cahn_hilliard_and_writes_delta():
    pytest.importorskip("process_bigraph")
    from process_bigraph import Composite
    from meta_modelers_guide.core import build_core

    core = build_core()
    steps_per_tick = 50
    n_ticks = 4
    phi0 = _seed_phi(n=32, seed=1)

    state = {
        "fields": {"phi": phi0.copy()},
        "ch": {
            "_type": "process",
            "address": "local:CahnHilliard",
            "config": {
                "grid": {"nx": 32, "ny": 32}, "M": M, "kappa": KAPPA, "dt": DT,
                "steps_per_tick": steps_per_tick,
            },
            "inputs": {"fields": ["fields"]},
            "outputs": {
                "fields": ["fields"],
                "phi_var": ["obs", "phi_var"],
                "phi_mean": ["obs", "phi_mean"],
                "phi_min": ["obs", "phi_min"],
                "phi_max": ["obs", "phi_max"],
            },
        },
    }
    comp = Composite({"state": state}, core=core)

    # Independent reference trajectory computed directly with ch_step, advanced
    # the same total number of steps -- this is what the store SHOULD hold if
    # the delta-write is correct (i.e. NOT double-counted by the additive apply).
    ref = phi0.copy()
    for _ in range(n_ticks):
        for _ in range(steps_per_tick):
            ref = ch_step(ref, M, KAPPA, DT)

    for _ in range(n_ticks):
        comp.run(1)

    got = np.asarray(comp.state["fields"]["phi"])
    assert np.allclose(got, ref, atol=1e-9)                  # store tracks phi, not phi*2

    obs = comp.state["obs"]
    assert obs["phi_mean"] == pytest.approx(float(ref.mean()), abs=1e-9)
    assert obs["phi_var"] == pytest.approx(float(ref.var()), abs=1e-9)
    assert np.all(np.isfinite(got))
