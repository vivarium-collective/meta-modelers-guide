"""Fig 6 mechanistic variant — a real rotary F₁Fₒ ATP synthase.

These gates test the *mechanistic* upgrade (``fig06-mechanistic`` composite,
``AtpSynthaseRotor``), where torque, efficiency, stall and reversal are DERIVED
from the proton-motive force, ATP free energy and mechanical load rather than
imposed. Each test is labelled with the reviewer's evidence class:

  INVARIANT              — a conservation/identity that must hold on every step
  EMPIRICAL_COMPARISON   — a derived number checked against a literature value
  MECHANISTIC_ABLATION   — a counterfactual: change a driver, predict the response
  PROSPECTIVE_PREDICTION — a threshold stated from first principles, then verified

The baseline algebraic transducer (``fig06-runnable``) is unaffected and keeps its
own gates in ``test_fig06_atp_synthase.py``.
"""
from __future__ import annotations

import json
import math
import warnings
from pathlib import Path

import pytest
from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.handlers_fig06_mech import (
    AtpSynthaseRotor, MembranePMF, MechanicalLoad, _E, _NA, _R,
)

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig06-mechanistic.composite.json"

_CFG = dict(n_c=10.0, atp_per_rev=3.0, drag=1.0e-23, dg0_kjmol=30.5,
            temperature=298.15, buffer_pools=True, min_conc=1.0e-6)


def _run_composite():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def _rotor(**over):
    cfg = dict(_CFG); cfg.update(over)
    return AtpSynthaseRotor(cfg, core=build_core())


def _step(pmf=0.150, load=0.0, atp=10.0, adp=1.0, pi=0.2, **over):
    """One fresh-rotor update → the instantaneous channel values (set-semantics
    deltas from zero == the live values on a fresh rotor)."""
    return _rotor(**over).update(
        {"pmf": pmf, "load_torque": load, "atp": atp, "adp": adp, "pi": pi}, 1.0)


# ── composite trajectory ──────────────────────────────────────────────────────

def test_composite_builds_and_runs():
    """REGRESSION_PIN: fig06-mechanistic builds and runs 20 ticks (21 rows)."""
    rows = _run_composite()
    assert len(rows) == 21


def test_charge_current_identity_holds_every_step():
    """INVARIANT: the proton current is the proton flux carried as charge,
    I == J_H·e, exactly on every step (matter⇒charge)."""
    rows = _run_composite()
    core = build_core()  # noqa: F841 (ensures types registered)
    for r in rows[1:]:
        j_h = float(r["omega"]) * _CFG["n_c"] / (2 * math.pi)
        assert abs(float(r["proton_current"]) - j_h * _E) < 1e-30


def test_power_budget_closes_every_step():
    """INVARIANT: P_in = P_ATP + P_ext + P_heat exactly (energy conserved across
    the interface), to machine precision on every step."""
    rows = _run_composite()
    worst = max(
        abs(float(r["power_in"]) - (float(r["power_atp"]) + float(r["power_ext"]) + float(r["power_heat"])))
        for r in rows
    )
    assert worst < 1e-30, f"power residual {worst:.2e} not at machine precision"


def test_dissipated_heat_is_nonnegative():
    """INVARIANT: viscous dissipation P_heat = ζω² ≥ 0 on every step (the motor
    never creates free energy)."""
    rows = _run_composite()
    assert all(float(r["power_heat"]) >= 0.0 for r in rows)


# ── derived number vs literature ─────────────────────────────────────────────

def test_drive_torque_derived_matches_literature():
    """EMPIRICAL_COMPARISON: the rotary drive torque is DERIVED from the pmf,
    τ_drive = n_c·e·Δp/2π, and at Δp = 150 mV lands at ≈ 38 pN·nm — reproducing
    the ~40 pN·nm the baseline merely imposed."""
    out = _step(pmf=0.150)
    tau = float(out["drive_torque"])
    predicted = _CFG["n_c"] * _E * 0.150 / (2 * math.pi)
    assert abs(tau - predicted) < 1e-30
    assert 35e-21 < tau < 42e-21, f"{tau/1e-21:.1f} pN·nm outside literature band"


def test_drive_torque_scales_with_pmf_not_fixed():
    """MECHANISTIC_ABLATION: unlike the baseline's fixed torque leaf, the derived
    torque scales linearly with Δp — doubling the pmf doubles the torque."""
    t1 = float(_step(pmf=0.100)["drive_torque"])
    t2 = float(_step(pmf=0.200)["drive_torque"])
    assert abs(t2 / t1 - 2.0) < 1e-9


# ── load-dependent stall and reversal ────────────────────────────────────────

def test_load_ramp_drives_forward_stall_reversal():
    """MECHANISTIC_ABLATION: as the external load ramps, the rotor turns forward
    (ω>0, synthesis), stalls (ω≈0), then reverses (ω<0). ω and J_ATP flip sign
    together — speed and chemistry are one shaft, not independent."""
    rows = _run_composite()
    omega = [float(r["omega"]) for r in rows]
    jatp = [float(r["atp_flux"]) for r in rows]
    assert max(omega) > 100 and min(omega) < -100, "no forward→reversal sweep"
    # a stall crossing exists
    assert any(omega[i] > 0 >= omega[i + 1] for i in range(len(omega) - 1)), "no stall crossing"
    # ω and J_ATP share sign on every live step
    assert all((o > 0) == (j > 0) for o, j in zip(omega[1:], jatp[1:]) if abs(o) > 1e-9)


def test_reversal_pumps_protons_and_hydrolyses_atp():
    """MECHANISTIC_ABLATION: past stall (load above τ_drive−τ_chem) the motor runs
    backward — J_ATP < 0 (hydrolysis) and J_H < 0 (protons pumped the other way)
    together. A thermodynamically honest reversible machine, not a one-way script."""
    # load well past the stall point
    out = _step(load=1.2e-20)
    assert float(out["omega"]) < 0
    assert float(out["atp_flux"]) < 0          # hydrolysis
    assert float(out["proton_current"]) < 0    # protons pumped against the flux


# ── proton-gradient directionality (first-principles threshold) ──────────────

def test_pmf_threshold_sets_direction():
    """PROSPECTIVE_PREDICTION: synthesis proceeds iff n_c·e·Δp > atp_per_rev·ΔG_ATP.
    The stall gradient Δp* = atp_per_rev·ΔG_ATP/(n_c·e) is computed from first
    principles, then verified: below Δp* the motor reverses, above it synthesises,
    at Δp* it stalls."""
    kT = _R * _CFG["temperature"] / _NA
    dg = _CFG["dg0_kjmol"] * 1e3 / _NA + kT * math.log(10.0 / (1.0 * 0.2))
    d_star = _CFG["atp_per_rev"] * dg / (_CFG["n_c"] * _E)
    assert 0.10 < d_star < 0.15   # ≈ 125 mV
    assert float(_step(pmf=d_star - 0.03)["omega"]) < 0       # below threshold → reversal
    assert abs(float(_step(pmf=d_star)["omega"])) < 1.0        # at threshold → stall
    assert float(_step(pmf=d_star + 0.03)["omega"]) > 0        # above threshold → synthesis


def test_efficiency_is_derived_and_varies_with_pmf():
    """MECHANISTIC_ABLATION: η = P_ATP/P_in = τ_chem/τ_drive is DERIVED, not the
    baseline's imposed 0.75 — and it changes with the operating point (a higher
    pmf gives a lower chemical-storage fraction), proving it is an outcome."""
    e_lo = float(_step(pmf=0.150)["efficiency"])
    e_hi = float(_step(pmf=0.300)["efficiency"])
    assert 0.0 < e_hi < e_lo < 1.0            # derived, bounded, operating-point dependent
    assert abs(e_lo - 0.75) > 0.02            # not the imposed baseline constant


# ── ATP back-pressure → static head (no external load needed) ────────────────

def test_atp_backpressure_slows_rotor():
    """MECHANISTIC_ABLATION: with the pools unbuffered, synthesised ATP accumulates,
    the reaction quotient and ΔG_ATP climb, and the rotor slows monotonically under
    its own product back-pressure — no external load. (Honest scope: it slows, it
    does not reach a full static head over this window — ΔG rises only ~logarithmically
    with [ATP].)"""
    core = build_core()
    cfg = dict(_CFG, buffer_pools=False)
    atp, adp, pi = 0.5, 50.0, 50.0   # large ADP/Pi reservoir; start low on ATP
    omegas, dgs = [], []
    for _ in range(80):
        # a fresh rotor each tick: the model is stateless given its inputs, so the
        # set-semantics outputs (deltas-from-zero) read as absolute values. The
        # pool deltas are per-tick either way; we integrate the pools ourselves.
        out = AtpSynthaseRotor(cfg, core=core).update(
            {"pmf": 0.150, "load_torque": 0.0, "atp": atp, "adp": adp, "pi": pi}, 1.0)
        atp += out["atp"]; adp += out["adp"]; pi += out["pi"]
        omegas.append(out["omega"]); dgs.append(out["dg_atp"])
    assert atp > 0.5, "ATP should have accumulated"
    assert dgs[-1] > dgs[0], "ΔG_ATP should rise as product builds (back-pressure)"
    assert omegas[-1] < omegas[0], "rotor should slow under back-pressure"
    # monotone non-increasing (product inhibition, not oscillation)
    assert all(omegas[i + 1] <= omegas[i] + 1e-9 for i in range(len(omegas) - 1))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
