"""ProtocellV2Open -- the EXTERNALLY-DRIVEN (open-system) variant, the explicitly
named remaining EMERGE step, built and MEASURED.

v2 (`ProtocellV2`) sustains emergent closure only METASTABLY (~2451 internal
steps): the precursor it secretes concentrates in the enclosed pocket and slowly
thickens the membrane inward until the centre crosses `thr`. The open-system
question: does an EXTERNAL DRIVE -- a local open dissipative throughflow that lifts
the closed-budget constraint -- turn that metastable plateau into an INDEFINITE
steady self-maintenance?

These tests pin the MEASURED, HONEST answer (deterministic, no RNG): NO. The
canonical drive DESTABILISES the ring into faster runaway filling (closure lost
~step 591 vs the undriven ~2451, membrane mass runs away ~624 -> ~3092), and the
controls stay load-bearing (the s_p=0 knockout still collapses fast; a puncture is
not healed). They also guard that the drive reduces exactly to v2 when off, that no
global closure operator enters the update, and the committed composite JSON.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from meta_modelers_guide.protocell.autopoiesis import (
    ProtocellV2Open,
    V2_OPEN_PARAMS,
    V2_PARAMS,
    enclosed_area_v2,
    rd_step_v2,
    rd_step_v2_open,
    seed_annulus,
)

N = 64
THR = V2_OPEN_PARAMS["thr"]
COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"

# The undriven v2 ring loses closure at this internal step (metastable window).
CLOSED_COLLAPSE = 2451


def _open_kwargs(**overrides):
    kw = dict(
        D=V2_OPEN_PARAMS["D"], k_decay=V2_OPEN_PARAMS["k_decay"],
        k_prod=V2_OPEN_PARAMS["k_prod"], Mp=V2_OPEN_PARAMS["Mp"],
        alpha=V2_OPEN_PARAMS["alpha"], s_p=V2_OPEN_PARAMS["s_p"],
        k_leak=V2_OPEN_PARAMS["k_leak"], k_cons=V2_OPEN_PARAMS["k_cons"],
        phi_max=V2_OPEN_PARAMS["phi_max"], f_in=V2_OPEN_PARAMS["f_in"],
        k_wash=V2_OPEN_PARAMS["k_wash"], k_turn=V2_OPEN_PARAMS["k_turn"],
        dt=V2_OPEN_PARAMS["dt"],
    )
    kw.update(overrides)
    return kw


def _run_open(nsteps, *, puncture_at=None, wedge_deg=60.0, **overrides):
    """Advance (phi, p) with rd_step_v2_open for nsteps, optionally zeroing a
    membrane wedge at `puncture_at`. Returns (phi, p, collapse_step)."""
    phi = seed_annulus(n=N)
    p = np.zeros_like(phi)
    kw = _open_kwargs(**overrides)
    collapse = -1
    yy, xx = np.mgrid[0:N, 0:N]
    theta = np.degrees(np.arctan2(yy - N / 2.0, xx - N / 2.0)) % 360.0
    wedge = (theta >= 0.0) & (theta <= wedge_deg)
    for t in range(nsteps):
        if puncture_at is not None and t == puncture_at:
            phi = phi.copy()
            phi[wedge] = 0.0
        phi, p = rd_step_v2_open(phi, p, **kw)
        if collapse == -1 and int(enclosed_area_v2(phi, THR).sum()) == 0:
            collapse = t
    return phi, p, collapse


# ---------------------------------------------------------------------------
# Emergence guarantee is preserved: no global closure operator in the update.
# ---------------------------------------------------------------------------

def test_open_update_has_no_global_closure_operator():
    """The drive must not smuggle a global closure test back in. Assert on the
    bytecode-referenced names (`co_names`) of `rd_step_v2_open` (and its only
    helper `_variable_diffusion`) so a docstring mention cannot give a false
    positive -- only a real call would fail."""
    from meta_modelers_guide.protocell import autopoiesis as mod

    names = set(rd_step_v2_open.__code__.co_names) | set(mod._variable_diffusion.__code__.co_names)
    assert "binary_fill_holes" not in names
    assert "enclosed_area_v2" not in names
    assert "enclosed_area" not in names


def test_drive_off_reduces_exactly_to_closed_v2():
    """With f_in=k_wash=k_turn=0 the open update is EXACTLY v2 -- same trajectory,
    same ~2451-step metastable collapse. This pins that the drive is the only
    difference and that any destabilisation below is caused by it, not by a code
    divergence."""
    phi_o, p_o, col_o = _run_open(1200, f_in=0.0, k_wash=0.0, k_turn=0.0)

    phi = seed_annulus(n=N)
    p = np.zeros_like(phi)
    kw = {k: V2_PARAMS[k] for k in (
        "D", "k_decay", "k_prod", "Mp", "alpha", "s_p", "k_leak", "k_cons",
        "phi_max", "dt")}
    for _ in range(1200):
        phi, p = rd_step_v2(phi, p, **kw)

    assert np.allclose(phi_o, phi, atol=1e-9)
    assert np.allclose(p_o, p, atol=1e-9)
    assert col_o == -1  # not yet collapsed at 1200 (matches v2's ~2451 window)


# ---------------------------------------------------------------------------
# The measured verdict: external drive DESTABILISES rather than sustains.
# ---------------------------------------------------------------------------

def test_open_drive_destabilises_faster_than_closed():
    """HONEST RESULT. The canonical open drive does NOT sustain closure
    indefinitely -- it loses closure FASTER than the undriven ring (~step 591 vs
    ~2451) via runaway autocatalytic filling: membrane mass runs away far above the
    seed and enclosed_area goes to 0. No bounded steady enclosed_area is reached."""
    phi, p, collapse = _run_open(2000)
    seed_mass = float(seed_annulus(n=N).sum())

    assert 0 < collapse < CLOSED_COLLAPSE  # collapses, and sooner than closed
    assert collapse < 800                  # observed ~591 -- a large margin
    assert int(enclosed_area_v2(phi, THR).sum()) == 0  # closure gone, not steady
    assert float(phi.sum()) > 2.0 * seed_mass  # runaway fill (observed ~3092 vs ~624)


def test_open_precursor_knockout_still_collapses():
    """Control: the drive must NOT rescue closure. s_p=0 (no self-secreted
    precursor) still loses closure fast under the external feed (~step 188). The
    feed sustains a little diffuse membrane mass but never re-closes the ring."""
    phi, p, collapse = _run_open(600, s_p=0.0)
    assert 0 <= collapse < 400  # closure lost fast (observed ~188)
    assert int(enclosed_area_v2(phi, THR).sum()) == 0


def test_open_puncture_is_not_healed_by_drive():
    """Control: the drive must NOT heal a broken boundary. Puncture a 60deg wedge
    of the driven ring -- enclosed_area stays 0 for the rest of the run even as
    membrane mass runs away; the external drive never restores the punctured
    topology, so closure remains genuinely load-bearing under drive."""
    phi, p, collapse = _run_open(1600, puncture_at=400)
    assert collapse == 400  # closure lost at the puncture and never regained
    assert int(enclosed_area_v2(phi, THR).sum()) == 0


# ---------------------------------------------------------------------------
# Process / composite level (through the process-bigraph engine).
# ---------------------------------------------------------------------------

def test_composite_open_does_not_sustain():
    """Run the committed v2-open composite JSON through the engine. The MEASURED
    verdict at the composite level: the drive does not sustain closure -- persists
    flips to 0.0, enclosed_area -> 0, the ring collapsed (collapse_tick > 0) well
    before the undriven ~2451 window, and membrane mass has run away above the
    seed."""
    pytest.importorskip("process_bigraph")
    from process_bigraph import Composite
    from meta_modelers_guide.core import build_core

    core = build_core()
    state = copy.deepcopy(
        json.loads((COMPOSITES / "protocell-autopoietic-v2-open.composite.json").read_text())["state"]
    )
    comp = Composite({"state": state}, core=core)
    for _ in range(20):  # 20 ticks * 50 = 1000 steps, past the ~591 collapse
        comp.run(1)

    obs = comp.state["obs"]
    assert obs["persists"] == 0.0
    assert obs["enclosed_area"] == 0.0
    assert 0 < obs["collapse_tick"] < CLOSED_COLLAPSE
    assert obs["membrane_mass"] > 1000.0  # runaway fill (observed ~3092)


def test_composite_open_off_recovers_v2_persistence():
    """Sanity: override the drive off (f_in=0, k_wash=0) on the SAME open composite
    and the loop persists at 1000 steps exactly as v2 does -- confirming the
    destabilisation is caused by the drive, not by the ProtocellV2Open code path."""
    pytest.importorskip("process_bigraph")
    from process_bigraph import Composite
    from meta_modelers_guide.core import build_core

    core = build_core()
    state = copy.deepcopy(
        json.loads((COMPOSITES / "protocell-autopoietic-v2-open.composite.json").read_text())["state"]
    )
    state["protocell"]["config"]["f_in"] = 0.0
    state["protocell"]["config"]["k_wash"] = 0.0
    comp = Composite({"state": state}, core=core)
    for _ in range(20):  # 1000 steps, inside v2's ~2451 window
        comp.run(1)

    obs = comp.state["obs"]
    assert obs["persists"] == 1.0
    assert obs["enclosed_area"] > 100
    assert obs["collapse_tick"] == -1.0


def test_open_cfl_guard_raises_for_unstable_mobility():
    from meta_modelers_guide.core import build_core

    with pytest.raises(ValueError):
        ProtocellV2Open(
            config={
                "grid": {"nx": N, "ny": N},
                **{k: V2_OPEN_PARAMS[k] for k in (
                    "D", "k_decay", "k_prod", "thr", "dt", "alpha", "s_p",
                    "k_leak", "k_cons", "phi_max", "f_in", "k_wash", "k_turn")},
                "Mp": 0.5,  # Mp*dt*4 = 2.0 >= 1 -- unstable
                "steps_per_tick": 1,
                "seed": 1,
            },
            core=build_core(),
        )
