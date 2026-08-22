"""ProtocellV2 -- the GENUINELY LOCAL-MECHANISM autopoiesis (peer-review M4).

v1 `Protocell` gates production on a GLOBAL `binary_fill_holes` observer; M4's
objection is that closure-dependence is then hand-coded, not emergent. v2
removes that observer from the update: production depends on a LOCAL interior
precursor field `p` (`k_prod*phi*p*(1-phi/phi_max)`), the membrane secretes and
is a barrier to `p`, and closure-dependence EMERGES from geometry -- a closed
ring confines the precursor it secretes and sustains itself; a punctured ring
bleeds precursor through the gap and starves locally.

These tests pin the MEASURED behaviour (deterministic, no RNG):
  * closed loop sustains topological closure well inside its ~2451-step
    metastable window, and the interior precursor genuinely pools;
  * the precursor knockout `s_p=0` AND the production knockout `k_prod=0` each
    collapse fast (~step 95);
  * the update contains NO global closure operator (asserted structurally);
  * a puncture starves the punctured wedge locally and does not self-heal;
  * the CFL guard rejects an unstable diffusivity.

The process-level tests run the committed
`meta_modelers_guide/composites/protocell-autopoietic-v2.composite.json`
through the engine, so they also guard that composite file.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from meta_modelers_guide.protocell.autopoiesis import (
    ProtocellV2,
    V2_PARAMS,
    enclosed_area_v2,
    rd_step_v2,
    seed_annulus,
)

N = 64
THR = V2_PARAMS["thr"]
COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"

# Comfortably inside the measured ~2451-step metastable closure window.
CLOSED_STEPS = 1000
# Well past the measured ~95-step collapse of the knockouts.
CONTROL_STEPS = 400


def _step_kwargs(**overrides):
    kw = dict(
        D=V2_PARAMS["D"], k_decay=V2_PARAMS["k_decay"], k_prod=V2_PARAMS["k_prod"],
        Mp=V2_PARAMS["Mp"], alpha=V2_PARAMS["alpha"], s_p=V2_PARAMS["s_p"],
        k_leak=V2_PARAMS["k_leak"], k_cons=V2_PARAMS["k_cons"],
        phi_max=V2_PARAMS["phi_max"], dt=V2_PARAMS["dt"],
    )
    kw.update(overrides)
    return kw


def _run_physics(nsteps, *, puncture_at=None, wedge_deg=60.0, **overrides):
    """Advance the (phi, p) pair with rd_step_v2 for nsteps, optionally zeroing
    a wedge of the membrane at `puncture_at`. Returns (phi, p, collapse_step)."""
    phi = seed_annulus(n=N)
    p = np.zeros_like(phi)
    kw = _step_kwargs(**overrides)
    collapse = -1
    yy, xx = np.mgrid[0:N, 0:N]
    theta = np.degrees(np.arctan2(yy - N / 2.0, xx - N / 2.0)) % 360.0
    wedge = (theta >= 0.0) & (theta <= wedge_deg)
    for t in range(nsteps):
        if puncture_at is not None and t == puncture_at:
            phi = phi.copy()
            phi[wedge] = 0.0
        phi, p = rd_step_v2(phi, p, **kw)
        if collapse == -1 and int(enclosed_area_v2(phi, THR).sum()) == 0:
            collapse = t
    return phi, p, collapse


# ---------------------------------------------------------------------------
# The emergence guarantee: NO global closure operator inside the update.
# ---------------------------------------------------------------------------

def test_update_has_no_global_closure_operator():
    """The whole point of v2: no global closure test (`binary_fill_holes` /
    `enclosed_area`) may be REFERENCED by the physics update. Assert it on the
    bytecode-referenced names (`co_names`) of `rd_step_v2` and its only helper
    `_variable_diffusion` -- so docstrings/comments that merely mention the
    absent operator (as v2's do) don't give a false positive, only an actual
    call would."""
    from meta_modelers_guide.protocell import autopoiesis as mod

    names = set(rd_step_v2.__code__.co_names) | set(mod._variable_diffusion.__code__.co_names)
    assert "binary_fill_holes" not in names
    assert "enclosed_area_v2" not in names  # no closure readout feeds the update
    assert "enclosed_area" not in names


# ---------------------------------------------------------------------------
# Physics-level behaviour.
# ---------------------------------------------------------------------------

def test_closed_loop_sustains_closure_and_pools_precursor():
    """The closed loop holds a genuinely enclosed interior well inside its
    metastable window, and the interior precursor pools from ~0 (the local
    confinement mechanism actually operating)."""
    phi0 = seed_annulus(n=N)
    seed_area = int(enclosed_area_v2(phi0, THR).sum())
    assert seed_area > 400  # sanity: seed is a real closed ring

    phi, p, collapse = _run_physics(CLOSED_STEPS)
    assert np.all(np.isfinite(phi)) and np.all(np.isfinite(p))
    assert collapse == -1  # never lost closure within the window
    final_area = int(enclosed_area_v2(phi, THR).sum())
    assert final_area > 100  # still a genuinely enclosed ring (observed ~293)
    assert final_area < seed_area  # throttled inward, not runaway growth

    # The precursor the membrane secretes accumulates in the enclosed pocket --
    # the confinement that IS the local closure mechanism.
    yy, xx = np.mgrid[0:N, 0:N]
    interior = np.sqrt((yy - N / 2.0) ** 2 + (xx - N / 2.0) ** 2) < (N / 4.0 - 4)
    assert float(p[interior].sum()) > 20.0  # pooled (observed ~72 at 1000 steps)


def test_precursor_knockout_collapses():
    """s_p=0 -- the membrane produces NO local precursor. With nothing to
    sustain production the ring dissipates fast. This is v2's mechanistic
    negative control (there is no analogue in v1)."""
    phi, p, collapse = _run_physics(CONTROL_STEPS, s_p=0.0)
    assert 0 <= collapse < 150  # closure lost fast (observed ~95)
    assert int(enclosed_area_v2(phi, THR).sum()) == 0
    assert float(phi.sum()) < 20.0  # membrane decays toward ~0
    assert float(p.sum()) == 0.0  # no precursor ever produced


def test_production_knockout_collapses():
    """k_prod=0 -- production off entirely. Same fast collapse as v1's knockout,
    reproduced in the v2 physics."""
    phi, _p, collapse = _run_physics(CONTROL_STEPS, k_prod=0.0)
    assert 0 <= collapse < 150
    assert int(enclosed_area_v2(phi, THR).sum()) == 0
    assert float(phi.sum()) < 20.0


def test_puncture_starves_locally_and_does_not_heal():
    """From the steady closed loop, zero a 60deg wedge. The gap does NOT
    self-heal -- interior precursor bleeds out through it and production starves
    LOCALLY at the wedge: wedge membrane mass stays far below the intact ring's
    at the same time. This is a real local prediction, not a global gate."""
    yy, xx = np.mgrid[0:N, 0:N]
    theta = np.degrees(np.arctan2(yy - N / 2.0, xx - N / 2.0)) % 360.0
    wedge = (theta >= 0.0) & (theta <= 60.0)

    # Intact reference and punctured run to the same horizon.
    phi_intact, _pi, _ci = _run_physics(1600)
    phi_punc, p_punc, collapse = _run_physics(1600, puncture_at=1000)

    assert collapse == 1000  # closure lost at the puncture and never regained
    assert int(enclosed_area_v2(phi_punc, THR).sum()) == 0

    wedge_intact = float(phi_intact[wedge].sum())
    wedge_punc = float(phi_punc[wedge].sum())
    # Local starvation: the punctured wedge is not rebuilt (observed ~2 vs ~79).
    assert wedge_punc < 0.2 * wedge_intact


# ---------------------------------------------------------------------------
# Process / composite level (through the process-bigraph engine).
# ---------------------------------------------------------------------------

def _build(core, *, phi0, p0, steps_per_tick, **cfg_over):
    from process_bigraph import Composite

    cfg = {
        "grid": {"nx": N, "ny": N},
        **{k: V2_PARAMS[k] for k in (
            "D", "k_decay", "k_prod", "thr", "dt", "Mp", "alpha", "s_p",
            "k_leak", "k_cons", "phi_max")},
        "steps_per_tick": steps_per_tick,
        "seed": 1,
    }
    cfg.update(cfg_over)
    state = {
        "fields": {"phi": phi0.copy(), "p": p0.copy()},
        "protocell": {
            "_type": "process",
            "address": "local:ProtocellV2",
            "config": cfg,
            "inputs": {"fields": ["fields"]},
            "outputs": {
                "fields": ["fields"],
                "enclosed_area": ["obs", "enclosed_area"],
                "membrane_mass": ["obs", "membrane_mass"],
                "precursor_mass": ["obs", "precursor_mass"],
                "persists": ["obs", "persists"],
                "collapse_tick": ["obs", "collapse_tick"],
            },
        },
    }
    return Composite({"state": state}, core=core)


def test_process_delta_write_tracks_both_fields():
    """The additive `fields` store must end up holding the actual new phi AND p
    (delta-emission not double-counting), cross-checked against an independent
    rd_step_v2 trajectory."""
    pytest.importorskip("process_bigraph")
    from meta_modelers_guide.core import build_core

    core = build_core()
    phi0 = seed_annulus(n=N)
    p0 = np.zeros_like(phi0)
    spt, n_ticks = 200, 5  # 1000 steps, inside the window

    comp = _build(core, phi0=phi0, p0=p0, steps_per_tick=spt)

    kw = _step_kwargs()
    phi_ref, p_ref = phi0.copy(), p0.copy()
    for _ in range(n_ticks * spt):
        phi_ref, p_ref = rd_step_v2(phi_ref, p_ref, **kw)

    for _ in range(n_ticks):
        comp.run(1)

    got_phi = np.asarray(comp.state["fields"]["phi"])
    got_p = np.asarray(comp.state["fields"]["p"])
    assert np.allclose(got_phi, phi_ref, atol=1e-6)
    assert np.allclose(got_p, p_ref, atol=1e-6)


def test_composite_closed_loop_persists():
    """Run the committed v2 composite JSON through the engine, inside the
    window: persists == 1.0, enclosed interior held, precursor pooled, no
    collapse."""
    pytest.importorskip("process_bigraph")
    from process_bigraph import Composite
    from meta_modelers_guide.core import build_core

    core = build_core()
    state = copy.deepcopy(
        json.loads((COMPOSITES / "protocell-autopoietic-v2.composite.json").read_text())["state"]
    )
    comp = Composite({"state": state}, core=core)
    for _ in range(20):  # 20 ticks * 50 = 1000 steps
        comp.run(1)

    obs = comp.state["obs"]
    assert obs["persists"] == 1.0
    assert obs["enclosed_area"] > 100
    assert obs["collapse_tick"] == -1.0
    assert obs["membrane_mass"] > 0
    assert obs["precursor_mass"] > 20.0  # local precursor genuinely pooled


def test_composite_precursor_knockout_collapses():
    """The single-variable mechanistic knockout at the composite level: override
    s_p=0 and the loop collapses (persists 0.0, enclosed_area 0)."""
    pytest.importorskip("process_bigraph")
    from process_bigraph import Composite
    from meta_modelers_guide.core import build_core

    core = build_core()
    state = copy.deepcopy(
        json.loads((COMPOSITES / "protocell-autopoietic-v2.composite.json").read_text())["state"]
    )
    state["protocell"]["config"]["s_p"] = 0.0
    comp = Composite({"state": state}, core=core)
    for _ in range(8):  # 400 steps, past the ~95-step collapse
        comp.run(1)

    obs = comp.state["obs"]
    assert obs["persists"] == 0.0
    assert obs["enclosed_area"] == 0.0
    assert obs["collapse_tick"] > 0


def test_cfl_guard_raises_for_unstable_mobility():
    from meta_modelers_guide.core import build_core

    with pytest.raises(ValueError):
        ProtocellV2(
            config={
                "grid": {"nx": N, "ny": N},
                **{k: V2_PARAMS[k] for k in (
                    "D", "k_decay", "k_prod", "thr", "dt", "alpha", "s_p",
                    "k_leak", "k_cons", "phi_max")},
                "Mp": 0.5,  # Mp*dt*4 = 2.0 >= 1 -- unstable
                "steps_per_tick": 1,
                "seed": 1,
            },
            core=build_core(),
        )
