"""Fig 6 · a molecular mechanism is a process with typed physical channels.

The runnable fig06 composite (meta_modelers_guide.composites.fig06-runnable) wires the
F₁Fₒ ATP synthase (MolecularMechanismHandler) to a ProtonMotiveRamp that charges the
substrate/proton drive (chemical_in) linearly over the run. From the ONE coupled
quantity — the proton flux — the transducer drives four TYPED physical channels. This
test asserts the CAUSAL claims the figure makes, conserving matter/charge/
angular-momentum/energy:

  (a) ATP synthesis flux is positive and SCALES with the proton drive (drive the
      handler directly at two activity levels, and over the actual run);
  (b) the ATP:H⁺ stoichiometry is 1/n_protons_per_atp on every step;
  (c) the rotary torque is positive and holds at the configured value (N·m);
  (d) the electrical energy balance holds — dissipated heat = input power − useful
      work = (1−η)·input power, with heat and useful work non-negative.

Complements test_compilation.py (that the fig06 handler conforms + compiles). Mirrors
the trajectory-assertion style of test_fig10_topology.py / test_fig04_env_drives_interface.py.
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.handlers_fig06 import MolecularMechanismHandler

COMPOSITE = (
    Path(__file__).resolve().parent.parent
    / "meta_modelers_guide" / "composites" / "fig06-runnable.composite.json"
)

E_CHARGE = 1.602e-19   # elementary charge (C) — matches the composite's proton_charge
PMF_VOLTS = 0.15
N_PROTONS = 3.3
EFFICIENCY = 0.75
K_CAT = 100.0
TORQUE_NM = 40.0 * 1e-21  # configured 40 pN·nm in N·m


# ── (a) higher proton drive ⇒ larger ATP flux (drive the handler directly) ────
def test_higher_drive_scales_atp_flux():
    core = build_core()
    mech = MolecularMechanismHandler({}, core=core)

    def atp_at(activity: float) -> float:
        # each call is a fresh delta over the set-semantics baseline; drive the
        # substrate/proton input and read the chemical_out delta.
        return float(mech.update({"chemical_in": activity}, 1.0)["chemical_out"])

    low = atp_at(0.3)
    mech2 = MolecularMechanismHandler({}, core=core)
    high = float(mech2.update({"chemical_in": 1.2}, 1.0)["chemical_out"])
    assert low > 0.0
    assert high > low
    # ATP flux is linear in the drive: 4× the activity ⇒ 4× the ATP flux.
    assert abs(high / low - 4.0) < 1e-9
    # and set by k_cat: J_ATP = k_cat · activity.
    assert abs(low - K_CAT * 0.3) < 1e-9


# ── run the runnable composite for (a)–(d) over the actual trajectory ─────────
def _run_trajectory():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def _channels(rows):
    atp = [float(r["chemical_out"]) for r in rows]
    current = [float(r["electrical_out"]) for r in rows]
    torque = [float(r["mechanical_out"]) for r in rows]
    heat = [float(r["thermal_out"]) for r in rows]
    j_h = [i / E_CHARGE for i in current]   # driving proton flux H⁺·s⁻¹
    return atp, current, torque, heat, j_h


def test_atp_flux_rises_with_the_proton_drive():
    atp, _c, _t, _h, j_h = _channels(_run_trajectory())
    # the drive ramps up, so both the proton flux and the ATP flux rise over the run.
    assert j_h[-1] > j_h[1] > 0.0
    assert atp[-1] > atp[1] > 0.0
    # non-decreasing: the drive only increases, so ATP flux never falls.
    for a, b in zip(atp[1:], atp[2:]):
        assert b >= a - 1e-9


def test_atp_proton_stoichiometry():
    atp, _c, _t, _h, j_h = _channels(_run_trajectory())
    # J_ATP / J_H = 1 / n_protons_per_atp on every active step (matter/charge coupling).
    for a, h in zip(atp[1:], j_h[1:]):
        assert abs(a / h - 1.0 / N_PROTONS) < 1e-6


def test_rotary_torque_holds_at_configured_value():
    _a, _c, torque, _h, _j = _channels(_run_trajectory())
    for x in torque[1:]:
        assert x > 0.0
        assert abs(x - TORQUE_NM) < 1e-24   # ~constant, angular-momentum channel


def test_energy_balance_heat_equals_input_minus_useful():
    _a, current, _t, heat, _j = _channels(_run_trajectory())
    for i, q in zip(current[1:], heat[1:]):
        input_power = i * PMF_VOLTS          # PMF work rate = proton current · pmf
        useful = input_power - q
        # dissipated heat is the non-conserved remainder = (1−η)·input power.
        assert abs(q - (1.0 - EFFICIENCY) * input_power) < 1e-24
        # useful work is the conserved fraction; both are non-negative (energy conserved).
        assert q >= 0.0
        assert useful >= 0.0
        assert abs(useful - EFFICIENCY * input_power) < 1e-24


# ── the four typed channels are ONE coupled quantity, not four free knobs ──────
def test_four_channels_all_derive_from_the_single_proton_flux():
    """Fig 6a's core claim: a molecular mechanism exchanges matter AND energy through
    coupled physical channels, not independent ones. Every step, the electrical channel
    is the chemical channel carried as charge (I = J_ATP·n·e — matter⇒charge) and the
    thermal channel is the fixed remainder of the electrical channel's PMF power
    (Q = (1−η)·I·pmf — charge⇒energy). Pin the whole coupling chain on the live run."""
    atp, current, torque, heat, _j = _channels(_run_trajectory())
    for a, i, tau, q in zip(atp[1:], current[1:], torque[1:], heat[1:]):
        # chemical ⇒ electrical: the proton current IS the ATP flux carried as charge.
        assert abs(i - a * N_PROTONS * E_CHARGE) < 1e-30
        # electrical ⇒ thermal: heat is the fixed (1−η) remainder of the PMF power.
        assert abs(q - (1.0 - EFFICIENCY) * i * PMF_VOLTS) < 1e-30
        # all four typed channels co-fire from the one drive; none is independently zero.
        assert a > 0.0 and i > 0.0 and tau > 0.0 and q > 0.0


# ── no drive ⇒ no flux: the channels are driven, not spontaneous ──────────────
def test_zero_drive_yields_zero_flux_on_every_channel():
    """No proton-motive force ⇒ no output on any channel (a molecular mechanism
    transduces a supplied drive; it does not manufacture flux). At zero substrate
    activity all four typed outputs are exactly zero — except the constant mechanical
    torque leaf, whose port is a fixed motor property, so it never turns negative."""
    core = build_core()
    mech = MolecularMechanismHandler({}, core=core)
    out = mech.update({"chemical_in": 0.0}, 1.0)
    assert out["chemical_out"] == 0.0
    assert out["electrical_out"] == 0.0
    assert out["thermal_out"] == 0.0
