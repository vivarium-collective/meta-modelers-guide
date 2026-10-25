"""Fig 6 · molecular interface — a *mechanistic* F₁Fₒ ATP synthase.

This is the real-mechanism upgrade of ``handlers_fig06`` (the algebraic
``MolecularMechanismHandler``, kept as the didactic baseline). Where the baseline
*imposes* a 40 pN·nm torque and a 75 % efficiency as fixed constants, this model
**derives** them from a genuine reduced rotary-motor thermodynamics, so torque,
efficiency, stall and reversal all emerge from the proton-motive force, the ATP
free energy, and the mechanical load rather than being scripted.

Physics (Oster & Wang 2000; Junge & Nelson 2015; Silverstein 2014 — a standard
overdamped rotary model, one rotational degree of freedom):

* A c-ring of ``n_c`` subunits turns once per ``n_c`` protons translocated; the
  F₁ head makes ``atp_per_rev`` ATP per revolution.
* Each proton crossing releases the per-proton free energy ``Δμ = e·Δp`` (J),
  where ``Δp`` is the proton-motive force (V). Delivered over one revolution by
  ``n_c`` protons and shared across 2π radians, this is a **drive torque**
      ``τ_drive = n_c · e · Δp / (2π)``  (N·m)
  — with n_c=10 and Δp=150 mV this is ≈ 3.8×10⁻²⁰ N·m ≈ 38 pN·nm, i.e. the
  baseline's "imposed 40 pN·nm" falls out as a *derived, validated* number.
* Synthesising ATP costs the free energy ``ΔG_ATP = ΔG°' + k_BT·ln([ATP]/[ADP][Pi])``
  per molecule; as a back-torque opposing rotation
      ``τ_chem = atp_per_rev · ΔG_ATP / (2π)``  (N·m).
* An external mechanical load ``τ_ext`` opposes rotation too. Overdamped rotor:
      ``ω = (τ_drive − τ_chem − τ_ext) / ζ``   (rad·s⁻¹)
  so the sign of ω — forward synthesis, **stall** (ω=0), or **reversal**
  (ω<0 → ATP hydrolysis pumping protons) — is an outcome, not a setting.
* Fluxes follow the shaft: ``J_H = n_c·ω/2π`` (H⁺·s⁻¹), ``J_ATP = atp_per_rev·ω/2π``
  (ATP·s⁻¹), proton current ``I = J_H·e`` (A).
* The **power budget closes exactly, by construction** (multiply the torque
  balance by ω):
      ``P_in = P_ATP + P_ext + P_heat``
  with ``P_in = J_H·Δμ = τ_drive·ω`` (W), ``P_ATP = J_ATP·ΔG_ATP = τ_chem·ω``,
  ``P_ext = τ_ext·ω``, and ``P_heat = ζ·ω² ≥ 0`` (viscous dissipation). Efficiency
  ``η = P_ATP/P_in`` is then **emergent** — it rises toward 1 near stall
  (reversible) and falls as viscous loss grows at speed — not a fixed 0.75.

``buffer_pools`` (default ``True``) holds [ATP]/[ADP]/[Pi] fixed so the external
load is the only thing that moves — a clean stall/reversal demonstration. Set it
``False`` to let ATP accumulate: ΔG_ATP then climbs and the rotor coasts to a
**static head** (ω→0 at τ_drive=τ_chem) under its own back-pressure — the real
reason a synthase does not run away.

All classes auto-register at ``local:<ClassName>`` via ``build_core``.
"""
from __future__ import annotations

import math

from process_bigraph import Process

# physical constants
_E = 1.602176634e-19       # elementary charge (C)
_NA = 6.02214076e23        # Avogadro (mol⁻¹)
_R = 8.314462618           # gas constant (J·mol⁻¹·K⁻¹)
_TWO_PI = 2.0 * math.pi


def _f(default):
    return {"_type": "float", "_default": default}


class AtpSynthaseRotor(Process):
    """A reduced rotary F₁Fₒ ATP synthase: one overdamped rotational degree of
    freedom driven by the proton-motive force against the ATP back-torque and an
    external load. Torque, speed, flux, power split, efficiency, stall and
    reversal are all derived from Δp, ΔG_ATP and τ_ext — nothing is imposed."""

    config_schema = {
        "n_c": _f(10.0),            # c-ring subunits (protons per revolution)
        "atp_per_rev": _f(3.0),     # catalytic sites (ATP per revolution)
        "drag": _f(1.0e-23),        # rotational drag ζ (N·m·s·rad⁻¹)
        "dg0_kjmol": _f(30.5),      # standard ATP synthesis free energy (kJ·mol⁻¹)
        "temperature": _f(298.15),  # K
        "buffer_pools": {"_type": "boolean", "_default": True},
        "min_conc": _f(1.0e-6),     # floor so ln(Q) stays finite (mol·L⁻¹)
        "pool_coupling": _f(1.0e-3),  # turnover(ATP·s⁻¹) → pool-concentration change scale
    }

    def inputs(self):
        return {
            "pmf": "voltage",            # Δp across the membrane (V)
            "load_torque": "torque",     # external mechanical load τ_ext (N·m)
            "atp": "concentration",
            "adp": "concentration",
            "pi": "concentration",
        }

    def outputs(self):
        return {
            # instantaneous (set-semantics) readouts
            "omega": "float",                 # angular velocity ω (rad·s⁻¹)
            "angle": "angle",                 # rotor angle θ (rad) — accumulates
            "proton_flux": "float",           # J_H (H⁺·s⁻¹)
            "proton_current": "current",      # I = J_H·e (A)
            "atp_flux": "chemical_flux",      # J_ATP (ATP·s⁻¹)
            "drive_torque": "torque",         # τ_drive (N·m)
            "chem_torque": "torque",          # τ_chem back-torque (N·m)
            "net_torque": "torque",           # τ_drive−τ_chem−τ_ext (N·m)
            "dg_atp": "energy",               # ΔG_ATP per molecule (J)
            "power_in": "power",              # P_in = J_H·Δμ (W)
            "power_atp": "power",             # P_ATP = J_ATP·ΔG_ATP (W)
            "power_ext": "power",             # P_ext = τ_ext·ω (W)
            "power_heat": "heat_flux",        # P_heat = ζω² (W)
            "efficiency": "float",            # η = P_ATP/P_in (dimensionless)
            # pools (accumulate; zero delta when buffer_pools)
            "atp": "concentration",
            "adp": "concentration",
            "pi": "concentration",
        }

    def _set(self, port, value):
        if not hasattr(self, "_last"):
            self._last = {}
        delta = value - self._last.get(port, 0.0)
        self._last[port] = value
        return delta

    def update(self, state, interval):
        c = self.config
        n_c = c["n_c"]
        npr = c["atp_per_rev"]
        zeta = c["drag"]

        pmf = float(state.get("pmf", 0.0))                 # V
        tau_ext = float(state.get("load_torque", 0.0))     # N·m
        atp = max(float(state.get("atp", 1.0)), c["min_conc"])
        adp = max(float(state.get("adp", 1.0)), c["min_conc"])
        pi = max(float(state.get("pi", 1.0)), c["min_conc"])

        kT = _R * c["temperature"] / _NA                   # J per molecule
        dmu = _E * pmf                                     # J per proton
        dg0 = c["dg0_kjmol"] * 1.0e3 / _NA                 # J per molecule
        q = atp / (adp * pi)                               # reaction quotient
        dg_atp = dg0 + kT * math.log(q)                    # J per molecule (synthesis cost)

        tau_drive = n_c * dmu / _TWO_PI                    # N·m
        tau_chem = npr * dg_atp / _TWO_PI                  # N·m (opposes rotation)
        net_torque = tau_drive - tau_chem - tau_ext        # N·m
        omega = net_torque / zeta                          # rad·s⁻¹ (overdamped)

        revs = omega / _TWO_PI
        j_h = n_c * revs                                   # H⁺·s⁻¹
        j_atp = npr * revs                                 # ATP·s⁻¹
        i_proton = j_h * _E                                # A

        power_in = j_h * dmu                               # W (= tau_drive·ω)
        power_atp = j_atp * dg_atp                         # W (= tau_chem·ω)
        power_ext = tau_ext * omega                        # W
        power_heat = zeta * omega * omega                  # W ≥ 0

        eff = (power_atp / power_in) if abs(power_in) > 0.0 else 0.0

        # pool bookkeeping: synthesis consumes ADP+Pi, produces ATP (per tick).
        # `pool_coupling` converts the enzyme's turnover (ATP·s⁻¹) into a finite
        # pool-concentration change, and the change is clamped so no pool crosses
        # its floor in one step (keeps the reaction quotient — and ΔG — finite).
        if c["buffer_pools"]:
            d_atp = d_adp = d_pi = 0.0
        else:
            made = c["pool_coupling"] * j_atp * interval
            floor = c["min_conc"]
            if made > 0.0:                                 # synthesis: draws ADP, Pi down
                made = min(made, adp - floor, pi - floor)
                made = max(made, 0.0)
            else:                                          # hydrolysis: draws ATP down
                made = max(made, floor - atp)
                made = min(made, 0.0)
            d_atp, d_adp, d_pi = made, -made, -made

        return {
            "omega": self._set("omega", omega),
            "angle": omega * interval,                     # accumulate θ
            "proton_flux": self._set("proton_flux", j_h),
            "proton_current": self._set("proton_current", i_proton),
            "atp_flux": self._set("atp_flux", j_atp),
            "drive_torque": self._set("drive_torque", tau_drive),
            "chem_torque": self._set("chem_torque", tau_chem),
            "net_torque": self._set("net_torque", net_torque),
            "dg_atp": self._set("dg_atp", dg_atp),
            "power_in": self._set("power_in", power_in),
            "power_atp": self._set("power_atp", power_atp),
            "power_ext": self._set("power_ext", power_ext),
            "power_heat": self._set("power_heat", power_heat),
            "efficiency": self._set("efficiency", eff),
            "atp": d_atp,
            "adp": d_adp,
            "pi": d_pi,
        }


class MembranePMF(Process):
    """The membrane's proton-motive force Δp (V). Holds a set-point, optionally
    ramping it by ``dpmf_dt`` per unit time so a run can **sweep the proton
    gradient** and show the rotor's directionality flip as Δp falls below the
    threshold n_c·e·Δp = atp_per_rev·ΔG_ATP (set-semantics into the shared pmf
    store)."""

    config_schema = {"pmf0": _f(0.150), "dpmf_dt": _f(0.0), "pmf_min": _f(0.0)}

    def inputs(self):
        return {}

    def outputs(self):
        return {"pmf": "voltage"}

    def update(self, state, interval):
        if not hasattr(self, "_t"):
            self._t = 0.0
        if not hasattr(self, "_last"):
            self._last = self.config["pmf0"]
        self._t += interval
        value = max(self.config["pmf0"] + self.config["dpmf_dt"] * self._t,
                    self.config["pmf_min"])
        delta = value - self._last
        self._last = value
        return {"pmf": delta}


class MechanicalLoad(Process):
    """An external mechanical load on the rotor shaft, ramping linearly from
    ``load0`` by ``load_rate`` per unit time. Sweeping τ_ext past the stall point
    τ_drive−τ_chem drives the motor **forward → stall → reversal**, the decisive
    loaded/unloaded comparison the review asks for (set-semantics into the shared
    load store)."""

    config_schema = {"load0": _f(0.0), "load_rate": _f(6.5e-22)}

    def inputs(self):
        return {}

    def outputs(self):
        return {"load_torque": "torque"}

    def update(self, state, interval):
        if not hasattr(self, "_t"):
            self._t = 0.0
        if not hasattr(self, "_last"):
            self._last = 0.0
        self._t += interval
        value = self.config["load0"] + self.config["load_rate"] * self._t
        delta = value - self._last
        self._last = value
        return {"load_torque": delta}
