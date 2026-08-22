"""Task 4 of study 5 `molecular-interfaces`: locks the demonstrating claims of
the three `molecular-*` composites into a regression test.

Runs the composites as-authored (`meta_modelers_guide/composites/molecular-
turing-pattern.composite.json`, `molecular-equal-diffusion-control
.composite.json`, `molecular-thermal-graded.composite.json`) through the real
`process_bigraph.Composite` engine -- `GrayScott`'s `gs`/`v_var`/`n_domains`/
`patterned` wrapping is already verified in `tests/test_gray_scott.py`; what
this module verifies is the STUDY-LEVEL claims:

1. `test_turing_pattern_forms`: the flagship (Du=0.16, Dv=0.08) patterns.
2. `test_equal_diffusion_control_stays_uniform`: the causal control (Du=Dv
   =0.12, differential diffusion removed) stays uniform -- proving diffusion
   asymmetry, not chemistry, drives the pattern.
3. `test_thermal_channel_grades_the_pattern`: the thermal channel (a raised
   uniform `temperature` field, Arrhenius-scaled reaction) COARSENS the
   pattern relative to the flagship at the same step count -- fewer, larger
   domains and a lower-but-still-patterned v_var -- a real graded second
   modality, not a chemistry collapse.

   Retuning note (task-3 API-map finding, applied here): the composite's
   original Ea=1.0/T=1.5 setting OVERSHOOTS -- the raised reaction rate runs
   away and collapses the pattern to near-uniform (v_var~=0) by 8000 total
   steps, which reads as "no pattern" rather than a graded one (confirmed
   directly below by re-sweeping that combination with `gs_step`). The
   composite was retuned to Ea=0.15/Tref=1.0 with a milder T=1.2, which
   legibly coarsens instead: fewer domains, v_var still comfortably above
   `PATTERN_FLOOR` -- see `molecular-thermal-graded.composite.json`'s
   `gs.config` and `fields.temperature`.
4. `test_pattern_is_multiseed_robust`: the flagship patterns for >=5 seeds.
   `GrayScott`'s own `seed` config key is currently inert (see its module
   docstring -- reserved for a future stochastic-seeding variant; the
   physics itself has no RNG). The composites bake a STATIC `seed_uv(seed=1)`
   draw into `fields.u`/`fields.v` at build time (composite JSON can't call
   an RNG). So "vary the seed" here means re-seeding the initial `u`/`v`
   arrays with `seed_uv(seed=<s>)` for s in 1..5, in an otherwise-identical
   copy of the flagship composite's state -- everything else (Du, Dv, F, k,
   dt, steps_per_tick, tick count) held fixed.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("process_bigraph")

from process_bigraph import Composite  # noqa: E402
from meta_modelers_guide.core import build_core  # noqa: E402
from meta_modelers_guide.molecular.gray_scott import (  # noqa: E402
    PATTERN_FLOOR,
    gs_step,
    n_domains as _n_domains,
    seed_uv,
    v_var as _v_var,
)

COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
N_TICKS = 16  # steps_per_tick=500 x 16 = 8000 total internal steps, same total
#  as tests/test_gray_scott.py's canonical-diffusion assertion and the
#  composites' own documented "v_var reaches ~0.0117-0.0119 by 8000 steps".

SEEDS = (1, 2, 3, 4, 5)


def _load_state(name: str) -> dict:
    return copy.deepcopy(
        json.loads((COMPOSITES / f"{name}.composite.json").read_text())["state"]
    )


def _run(name: str, n_ticks: int = N_TICKS) -> dict:
    core = build_core()
    comp = Composite({"state": _load_state(name)}, core=core)
    for _ in range(n_ticks):
        comp.run(1)
    return comp.state["obs"]


def test_turing_pattern_forms():
    """The flagship: canonical differential diffusion (Du=0.16, Dv=0.08)
    destabilizes the near-uniform seed into an emergent Turing spot pattern."""
    obs = _run("molecular-turing-pattern")

    assert obs["patterned"] == 1.0
    assert obs["v_var"] > PATTERN_FLOOR
    assert obs["n_domains"] > 1


def test_equal_diffusion_control_stays_uniform():
    """The causal control: identical setup except Du=Dv=0.12 (differential
    diffusion removed, chemistry unchanged) -- the Turing instability never
    triggers, proving diffusion asymmetry (not chemistry) drives the
    flagship's pattern."""
    obs = _run("molecular-equal-diffusion-control")

    assert obs["patterned"] == 0.0
    assert obs["v_var"] == pytest.approx(0.0, abs=1e-6)


def test_thermal_channel_grades_the_pattern():
    """The thermal channel: a raised uniform temperature field (Arrhenius-
    scaled reaction) coarsens the pattern relative to the no-temperature
    flagship at the same step count -- fewer, larger domains and a
    lower-but-still-patterned v_var. A real graded second modality, not a
    chemistry collapse.

    Also re-sweeps the composite's PRIOR (Ea=1.0, T=1.5) setting directly
    with gs_step, confirming the task-3 finding that motivated the retune:
    that combination overshoots into a near-total collapse (v_var ~= 0),
    which is what "graded, not collapsed" is being tested against here.
    """
    obs_base = _run("molecular-turing-pattern")
    obs_thermal = _run("molecular-thermal-graded")

    # Sanity: same seed, same chemistry/diffusion params -- the composite's
    # gs.config only differs in Ea/temperature (see the composite JSONs).
    base_cfg = _load_state("molecular-turing-pattern")["gs"]["config"]
    thermal_cfg = _load_state("molecular-thermal-graded")["gs"]["config"]
    for key in ("Du", "Dv", "F", "k", "dt", "steps_per_tick", "thr"):
        assert base_cfg[key] == thermal_cfg[key]
    assert thermal_cfg["Ea"] != 0.0

    # Still a real pattern -- not a collapse.
    assert obs_thermal["patterned"] == 1.0
    assert obs_thermal["v_var"] > PATTERN_FLOOR

    # But a MEASURABLY coarser one than the flagship: fewer, larger domains,
    # and a lower (but not ~0) v_var. Thresholds observed with margin (this
    # machine: base v_var~=0.0119/n_domains=12, thermal v_var~=0.0096/
    # n_domains=2).
    assert obs_thermal["n_domains"] < obs_base["n_domains"]
    assert obs_thermal["v_var"] < obs_base["v_var"]
    assert obs_thermal["v_var"] > 0.5 * PATTERN_FLOOR  # margin above the floor -- not collapsing toward it

    print(
        f"\nthermal grading: base v_var={obs_base['v_var']:.5f} "
        f"n_domains={obs_base['n_domains']:.0f} -> thermal "
        f"v_var={obs_thermal['v_var']:.5f} n_domains={obs_thermal['n_domains']:.0f}"
    )

    # Confirms the task-3 finding that motivated the retune: the composite's
    # ORIGINAL Ea=1.0/T=1.5 setting overshoots the reaction rate and collapses
    # the pattern to near-uniform by the same 8000-step count -- reads as "no
    # pattern", not "graded pattern". Computed directly with gs_step (not
    # through a composite) at the flagship's seed/params.
    u0, v0 = seed_uv(n=128, seed=1)
    rate_overshoot = np.exp(-1.0 * (1.0 / 1.5 - 1.0 / 1.0))  # Ea=1.0, T=1.5, Tref=1.0
    u, v = u0.copy(), v0.copy()
    for _ in range(500 * N_TICKS):
        u, v = gs_step(u, v, 0.16, 0.08, 0.037, 0.06, dt=1.0, rate=rate_overshoot)
    overshoot_var = _v_var(v)
    assert overshoot_var < PATTERN_FLOOR, (
        f"expected the prior Ea=1.0/T=1.5 setting to collapse (v_var below "
        f"the pattern floor {PATTERN_FLOOR}); got v_var={overshoot_var:.5f} "
        f"-- the task-3 overshoot finding no longer reproduces, the retune "
        f"rationale should be re-checked."
    )


def test_pattern_is_multiseed_robust():
    """The flagship's Turing pattern forms across >=5 seeds -- not just the
    single hard-coded seed=1 draw baked into the composite JSON. `v_var`
    stays above the floor for every seed (reported as a range); `n_domains`
    is reported as a range too (seed-sensitive by nature of a stochastic
    nucleation-patch placement -- not asserted at a point)."""
    base_state = _load_state("molecular-turing-pattern")
    v_vars, n_doms = [], []

    for seed in SEEDS:
        core = build_core()
        state = copy.deepcopy(base_state)
        u0, v0 = seed_uv(n=128, seed=seed)
        state["fields"]["u"] = u0.tolist()
        state["fields"]["v"] = v0.tolist()

        comp = Composite({"state": state}, core=core)
        for _ in range(N_TICKS):
            comp.run(1)
        obs = comp.state["obs"]

        assert obs["patterned"] == 1.0, f"seed {seed} failed to pattern"
        assert obs["v_var"] > PATTERN_FLOOR, f"seed {seed} v_var below floor"
        v_vars.append(obs["v_var"])
        n_doms.append(obs["n_domains"])

    lo, hi = min(v_vars), max(v_vars)
    dlo, dhi = min(n_doms), max(n_doms)
    print(
        f"\nmolecular-turing-pattern multi-seed (seeds {SEEDS[0]}-{SEEDS[-1]}): "
        f"v_var={[round(v, 5) for v in v_vars]} range=[{lo:.5f}, {hi:.5f}]; "
        f"n_domains={[int(d) for d in n_doms]} range=[{dlo:.0f}, {dhi:.0f}]"
    )

    # Range assertions with margin (not the observed edge) -- a robustness
    # gate, not a brittle golden-value check. Observed band: v_var in
    # [0.01157, 0.01193], n_domains in [8, 12].
    assert lo > 2.0 * PATTERN_FLOOR, f"lower end of the v_var band too close to the floor: {lo:.5f}"
    assert hi < 0.03, f"upper end of the v_var band implausibly high: {hi:.5f}"
    assert dlo > 1, f"lower end of the n_domains band collapsed to <=1: {dlo:.0f}"
