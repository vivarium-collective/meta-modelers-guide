"""Fig 7 · molecular mechanism — an executable handler for the ``MolecularMechanism``
draft signature.

The Fig 7 draft is a single molecular process that couples the four physical
interaction channels of a molecule — chemical, electrical, mechanical, thermal —
plus a (string) ``structure`` identifier, transforming input channels into output
channels (Fig 7b). This handler names the transducer: the **F₁Fₒ ATP synthase**,
the rotary motor that converts a proton flux across the membrane into ATP. All
four channels are driven from ONE coupled quantity — the proton flux set by the
chemical (substrate/turnover) input — so the ports are physically consistent:

* **chemical**   — ATP synthesis flux, ``J_ATP = k_cat · activity``.
* **electrical** — the proton current carried by the H⁺ flux, ``I = J_H · e``,
  where ``J_H = (H⁺/ATP)·J_ATP`` and the driving proton-motive force is ≈ 150 mV.
* **mechanical** — rotary **torque** delivered by the Fₒ motor, ≈ 40 pN·nm
  (≈ 4×10⁻²⁰ N·m), roughly constant with load — the drive sets the rotor's
  *speed* (ω = 2π·J_H/c-ring), not its torque. Matches the draft's declared
  ``mechanical_out: torque`` port (N·m).
* **thermal**    — the non-conserved remainder dissipated as heat,
  ``(1 − η)·(PMF work)``, η ≈ 75 % (60–90 %).

Every literature constant lives in ``config``.

The four output channels are instantaneous *fluxes*, so they are written with
"set" semantics (each ``update`` returns the delta carrying the additive store to
the freshly-computed rate). ``structure`` is a read-only string identifier
(PDB/SMILES) and does not enter the dynamics.

Handler auto-registered at ``local:MolecularMechanismHandler`` by build_core; ports
are declared config-independently so conformance is checkable before instantiation.
Mirrors handlers_fig03b.py (the set-semantics exemplar).
"""
from __future__ import annotations

from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


class MolecularMechanismHandler(Process):
    """The F₁Fₒ ATP synthase as a four-channel transducer: a proton flux (set by the
    chemical/substrate input) drives ATP synthesis (chemical), carries a proton
    current across the proton-motive force (electrical), spins the Fₒ rotor at a
    fixed torque (mechanical), and dissipates its non-conserved remainder as heat
    (thermal). All four channels derive from the one proton flux → physically
    consistent."""

    config_schema = {
        # F₁Fₒ ATP synthase — literature constants (Milo & Phillips, Cell Biology
        # by the Numbers; Junge & Nelson 2015; Stock et al. 1999).
        "k_cat_atp": _f(100.0),       # ATP synthase turnover ≈ 100 ATP·s⁻¹ at unit activity
        "n_protons_per_atp": _f(3.3), # H⁺/ATP: c₁₀ ring ÷ 3 catalytic sites ≈ 3.3
        "pmf_volts": _f(0.150),       # proton-motive force |Δp| ≈ 150 mV
        "torque_pn_nm": _f(40.0),     # Fₒ rotary torque ≈ 40 pN·nm
        "c_ring": _f(10.0),           # c-subunits translocated per full rotation
        "efficiency": _f(0.75),       # fraction of PMF work conserved (60–90 %)
        "proton_charge": _f(1.602e-19),  # elementary charge (C)
    }

    def inputs(self):
        return {"chemical_in": "chemical_flux", "electrical_in": "current",
                "mechanical_in": "torque", "thermal_in": "heat_flux",
                "structure": "structure"}

    def outputs(self):
        return {"chemical_out": "chemical_flux", "electrical_out": "current",
                "mechanical_out": "torque", "thermal_out": "heat_flux"}

    def _set(self, port, value):
        if not hasattr(self, "_last"):
            self._last = {}
        delta = value - self._last.get(port, 0.0)
        self._last[port] = value
        return delta

    def update(self, state, interval):
        c = self.config
        activity = float(state.get("chemical_in", 0.0))   # substrate / enzyme activity

        # One coupled quantity — the proton flux — sets all four channels.
        j_atp = c["k_cat_atp"] * activity                 # ATP synthesis flux (ATP·s⁻¹)
        j_h = c["n_protons_per_atp"] * j_atp              # H⁺ flux (H⁺·s⁻¹)
        e = c["proton_charge"]

        i_proton = j_h * e                                # proton current (A)
        w_pmf = j_h * e * c["pmf_volts"]                  # PMF work rate (W) = input power
        torque_nm = c["torque_pn_nm"] * 1e-21             # rotary torque (N·m); 1 pN·nm = 1e-21 N·m
        q_heat = (1.0 - c["efficiency"]) * w_pmf          # non-conserved remainder → heat

        # Energy balance holds by construction on the electrical channel: the PMF
        # input power w_pmf = i_proton·pmf_volts is split into the conserved useful
        # fraction (η·w_pmf, driving ATP synthesis) and the dissipated remainder
        # q_heat = (1−η)·w_pmf, so w_pmf = η·w_pmf + q_heat exactly. The mechanical
        # channel carries the rotor's (near-constant) torque; the drive sets its speed.
        return {
            "chemical_out": self._set("chemical_out", j_atp),
            "electrical_out": self._set("electrical_out", i_proton),
            "mechanical_out": self._set("mechanical_out", torque_nm),
            "thermal_out": self._set("thermal_out", q_heat),
        }


class ProtonMotiveRamp(Process):
    """The membrane charging up: ramps the substrate/proton drive (``chemical_in``)
    linearly over the run so the transducer sweeps its operating range. Writes a
    fixed positive increment into the shared ``chemical_in`` store each tick, so the
    driving proton flux rises monotonically and every coupled output channel scales
    with it. This is the fig06 analogue of fig04's diffusing gradient — an evolving
    driver that makes the environment→transducer coupling legible over time."""

    config_schema = {"drive_rate": _f(0.06)}  # Δ(chemical_in) per unit interval

    def inputs(self):
        return {}

    def outputs(self):
        return {"drive": "chemical_flux"}

    def update(self, state, interval):
        # accumulate-by-default: this delta raises the shared chemical_in each tick.
        return {"drive": self.config["drive_rate"] * interval}


# ── handler environment ⟦Fig7⟧_H ──────────────────────────────────────────────
# init seeds the four numeric input channels (the ``structure`` string leaf is
# left as-is). init sets a leaf's ``_default`` (realize ignores ``_value``).
ENV = {
    "MolecularMechanism": {
        "handler": "MolecularMechanismHandler",
        "config": {"k_cat_atp": 100.0, "n_protons_per_atp": 3.3,
                   "pmf_volts": 0.150, "torque_pn_nm": 40.0, "c_ring": 10.0,
                   "efficiency": 0.75, "proton_charge": 1.602e-19},
        "init": {
            "ports.chemical_in": 1.0,
            "ports.electrical_in": 1.0,
            "ports.mechanical_in": 1.0,
            "ports.thermal_in": 0.5,
        },
    },
}
