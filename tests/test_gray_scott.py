"""GrayScott -- wraps the Task-1 Gray-Scott reaction-diffusion physics
(`tests/test_gray_scott_physics.py`) as a `fields`-store process, emitting
the pattern-formation metric (`v_var`, `n_domains`) plus a gated `patterned`
flag, with an optional thermal (Arrhenius) channel.

The physics is unchanged: `laplacian`/`gs_step`/`seed_uv`/`run_gs`/`v_var`/
`n_domains` are lifted (with `gs_step` extended by an optional elementwise
`rate` multiplier on the reaction term, for the thermal channel) from the
Task-1 spike into `meta_modelers_guide/molecular/gray_scott.py`. What this
test verifies is the process wrapping:

1. Registration + the additive `fields` map[array] field-write contract
   (same convention as `condensate/cahn_hilliard.py`'s `CahnHilliard` and
   `protocell/autopoiesis.py`'s `Protocell`): built through
   `build_core()`/`Composite` at `local:GrayScott`, the store must end up
   holding the actual new `u`/`v` (not double-counted), cross-checked
   against an independent reference trajectory computed directly with
   `gs_step`.
2. Canonical differential-diffusion params (`Du=0.16, Dv=0.08`), run
   `steps_per_tick x n_ticks` = 8000 total internal steps (same total as the
   Task-1 physics spike) -> `patterned == 1.0`, `v_var` above the pattern
   floor.
3. The equal-diffusion control (`Du=Dv=0.12`) -> `patterned == 0.0`,
   `v_var` ~= 0 (well below the pattern floor).
4. The thermal channel: with a raised uniform `temperature` field present
   (and `Ea != 0`), the Arrhenius rate factor speeds up the reaction versus
   the identical run with no `temperature` field at all (rate factor == 1,
   pure chemical) -- a measurably different `v_var`/`n_domains` after the
   same number of steps proves the thermal channel is actually wired into
   the reaction term, not just accepted and ignored.
"""
from __future__ import annotations

import numpy as np
import pytest

from meta_modelers_guide.molecular.gray_scott import (
    GrayScott,
    PATTERN_FLOOR,
    gs_step,
    n_domains,
    seed_uv,
    v_var,
)

N = 128
DU, DV, F, K, DT = 0.16, 0.08, 0.037, 0.06, 1.0


def _build_composite(core, *, Du, Dv, steps_per_tick, u0, v0, temperature=None,
                      Ea=0.0, Tref=1.0, thr=0.2):
    from process_bigraph import Composite

    fields = {"u": u0.copy(), "v": v0.copy()}
    if temperature is not None:
        fields["temperature"] = temperature.copy()

    state = {
        "fields": fields,
        "gs": {
            "_type": "process",
            "address": "local:GrayScott",
            "config": {
                "grid": {"nx": u0.shape[0], "ny": u0.shape[1]},
                "Du": Du, "Dv": Dv, "F": F, "k": K, "dt": DT,
                "steps_per_tick": steps_per_tick,
                "thr": thr,
                "seed": 1,
                "Ea": Ea, "Tref": Tref,
            },
            "inputs": {"fields": ["fields"]},
            "outputs": {
                "fields": ["fields"],
                "v_var": ["obs", "v_var"],
                "n_domains": ["obs", "n_domains"],
                "patterned": ["obs", "patterned"],
            },
        },
    }
    return Composite({"state": state}, core=core)


def test_registers_and_resolves_as_local_gray_scott_and_writes_delta_and_patterns():
    pytest.importorskip("process_bigraph")
    from meta_modelers_guide.core import build_core

    core = build_core()
    u0, v0 = seed_uv(n=N, seed=1)
    steps_per_tick = 500
    n_ticks = 16  # 8000 total internal steps -- same as the Task-1 physics spike.

    comp = _build_composite(core, Du=DU, Dv=DV, steps_per_tick=steps_per_tick,
                             u0=u0, v0=v0)

    # Independent reference trajectory computed directly with gs_step, advanced
    # the same total number of steps -- what the store SHOULD hold if the
    # delta-write is correct (not double-counted by the additive `fields` apply).
    u_ref, v_ref = u0.copy(), v0.copy()
    for _ in range(n_ticks):
        for _ in range(steps_per_tick):
            u_ref, v_ref = gs_step(u_ref, v_ref, DU, DV, F, K, dt=DT)

    for _ in range(n_ticks):
        comp.run(1)

    got_u = np.asarray(comp.state["fields"]["u"])
    got_v = np.asarray(comp.state["fields"]["v"])
    assert np.allclose(got_u, u_ref, atol=1e-9)
    assert np.allclose(got_v, v_ref, atol=1e-9)

    obs = comp.state["obs"]
    assert obs["v_var"] == pytest.approx(float(v_ref.var()), abs=1e-9)
    assert obs["n_domains"] == pytest.approx(float(n_domains(v_ref, thr=0.2)), abs=1e-9)
    assert obs["patterned"] == 1.0
    assert obs["v_var"] > PATTERN_FLOOR
    assert np.all(np.isfinite(got_u)) and np.all(np.isfinite(got_v))


def test_equal_diffusion_control_stays_uniform():
    pytest.importorskip("process_bigraph")
    from meta_modelers_guide.core import build_core

    core = build_core()
    u0, v0 = seed_uv(n=N, seed=1)
    steps_per_tick = 500
    n_ticks = 16  # 8000 total internal steps

    comp = _build_composite(core, Du=0.12, Dv=0.12, steps_per_tick=steps_per_tick,
                             u0=u0, v0=v0)
    for _ in range(n_ticks):
        comp.run(1)

    obs = comp.state["obs"]
    assert obs["patterned"] == 0.0
    assert obs["v_var"] < 1e-4  # ~0.0, well below PATTERN_FLOOR


def test_thermal_channel_modulates_reaction_rate():
    pytest.importorskip("process_bigraph")
    from meta_modelers_guide.core import build_core

    u0, v0 = seed_uv(n=N, seed=1)
    steps_per_tick = 500
    n_ticks = 8  # 4000 total internal steps -- well short of full patterning,
    #  chosen so the thermal-vs-chemical CONTRAST is visible before the
    #  no-thermal run itself saturates near the pattern's plateau variance.

    Ea, Tref = 1.0, 1.0
    T_raised = np.full((N, N), 1.5)  # T > Tref -> Arrhenius rate factor > 1

    core_hot = build_core()
    comp_hot = _build_composite(
        core_hot, Du=DU, Dv=DV, steps_per_tick=steps_per_tick, u0=u0, v0=v0,
        temperature=T_raised, Ea=Ea, Tref=Tref,
    )
    core_cold = build_core()
    comp_cold = _build_composite(
        core_cold, Du=DU, Dv=DV, steps_per_tick=steps_per_tick, u0=u0, v0=v0,
        temperature=None, Ea=Ea, Tref=Tref,
    )

    for _ in range(n_ticks):
        comp_hot.run(1)
        comp_cold.run(1)

    obs_hot = comp_hot.state["obs"]
    obs_cold = comp_cold.state["obs"]

    # Same seed, same chemistry/diffusion params, same step count -- the ONLY
    # difference is the presence of a raised `temperature` field (rate factor
    # > 1 vs the implicit rate factor == 1 with no temperature field at all).
    # A measurable v_var difference proves the Arrhenius scaling is actually
    # applied to the reaction term, not silently accepted and ignored.
    assert obs_hot["v_var"] != pytest.approx(obs_cold["v_var"], rel=1e-6)
    assert abs(obs_hot["v_var"] - obs_cold["v_var"]) > 1e-4


def test_zero_config_scalar_is_not_silently_refilled():
    # bigraph-schema's `core.fill` merge treats a Float/Integer value equal to
    # 0 as "empty" and silently refills it from the schema `_default` -- Ea=0
    # (explicitly disabling the thermal channel even with a temperature field
    # present) must survive construction, mirroring Protocell's guard for the
    # same trap (k_prod=0 negative control).
    from meta_modelers_guide.core import build_core

    proc = GrayScott(
        config={"grid": {"nx": N, "ny": N}, "Du": DU, "Dv": DV, "F": F, "k": K,
                "dt": DT, "steps_per_tick": 1, "thr": 0.2, "seed": 1,
                "Ea": 0.0, "Tref": 1.0},
        core=build_core(),
    )
    assert proc.config["Ea"] == 0.0


def test_finite_guard_raises_on_nonfinite_fields():
    from meta_modelers_guide.core import build_core

    proc = GrayScott(
        config={"grid": {"nx": 4, "ny": 4}, "Du": DU, "Dv": DV, "F": F, "k": K,
                "dt": DT, "steps_per_tick": 1, "thr": 0.2, "seed": 1,
                "Ea": 0.0, "Tref": 1.0},
        core=build_core(),
    )
    u_bad = np.full((4, 4), np.nan)
    v_bad = np.zeros((4, 4))
    with pytest.raises(FloatingPointError):
        proc.update({"fields": {"u": u_bad, "v": v_bad}}, 1.0)
