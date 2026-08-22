"""Fig 4b · the minimal cellular interface — an executable handler for the
``CellularInterface`` draft process.

The Fig 4b draft is an effect *signature*: a single ``cell`` node that senses four
environmental drivers and exposes the cell's physical exchange ports (chemical,
mechanical, electrical, thermal) plus higher-level cellular ports (growth rate,
shape, signaling, objective, viability). This module supplies a conforming
executable :class:`~process_bigraph.Process` — a *handler* — with genuine
toy-real dynamics for a bounded, goal-directed cell, and the handler environment
(:data:`ENV`) the compiler swaps in for the draft (mirrors ``handlers.py`` +
the Fig 6 grain-swap exemplar).

Style matches ``handlers.py`` exactly: ``config_schema`` of named floats,
``inputs``/``outputs`` return CONSTANT port dicts (so conformance is checkable
before instantiation), and ``update`` returns per-port deltas.

Dynamics (all constants come from ``config`` — none fabricated inline):

* **chemical** (flux)   — net nutrient uptake, ``-uptake_rate · chemical_ext``.
* **growth_rate**       — Monod law, ``growth_max · c/(km + c)``.
* **shape** (volume)    — accumulates via growth: ``d = growth · interval``.
* **objective**         — biomass proxy, accumulates with growth × yield.
* **viability**         — honest first-order **Arrhenius thermal death**,
  ``dV/dt = −k(T)·V`` with ``k(T) = A·exp(−Ea/RT)`` (protein-denaturation-limited,
  Ea ≈ 300 kJ·mol⁻¹): viability holds near 37 °C and collapses within minutes at
  55 °C (E. coli D-value).
* **mechanical** (force) / **electrical** (current) / **thermal** (heat flux) /
  **signaling** (rate) — small, physically-plausible responses to their drivers
  (elastic force, Ohmic current, Fourier heat flux, Monod-scaled signaling).

Ports that name an *instantaneous* quantity (a flux/rate/current — everything
except the two accumulating pools ``shape`` and ``objective``) are written with
"set" semantics: each ``update`` returns the delta that carries the additive
store to the freshly-computed value, so the store holds the current rate rather
than an ever-growing integral.
"""
from __future__ import annotations

import math

from process_bigraph import Process


def _f(default):  # a float config field
    return {"_type": "float", "_default": default}


# ── Fig 4b · cellular-interface signature: one conforming handler ─────────────
# signature CellularInterface:
#   in  {chemical_ext: concentration, mechanical_ext: force,
#        electrical_ext: voltage, thermal_ext: temperature}
#   out {chemical: chemical_flux, mechanical: force, electrical: current,
#        thermal: heat_flux, growth_rate: growth_rate, shape: volume,
#        signaling: signaling_rate, objective: objective, viability: viability}

class CellularInterfaceHandler(Process):
    """A bounded, goal-directed cell at its interface: it takes up chemical
    supply (Monod), grows and accretes volume + a biomass-proxy objective, keeps
    its viability up while its thermal environment stays within tolerance, and
    passes its physical exchange ports (force, current, heat flux, signaling)
    through plausible linear responses to their drivers."""

    config_schema = {
        # chemical uptake + growth (Monod)
        "uptake_rate": _f(0.8),          # nutrient flux per unit external conc.
        "growth_max": _f(0.6),           # max specific growth rate (hr⁻¹)
        "km": _f(0.5),                   # half-saturation concentration
        # goal-directed accretion
        "shape_growth_coupling": _f(1.0),  # volume gained per unit growth·interval
        "objective_yield": _f(0.5),        # biomass-proxy gained per unit growth
        # thermal death — first-order Arrhenius, k(T) = A·exp(−Ea/RT).
        # Ea ≈ 300 kJ·mol⁻¹ is the protein-denaturation-limited activation energy
        # for bacterial thermal inactivation (E. coli; cf. moist-heat D/z data).
        # A is pinned so the D-value (time for a 1-log kill) is ~1 min at 55 °C —
        # the standard E. coli thermal-death reference — which makes death
        # negligible near 37 °C (D ≈ 10 h) and catastrophic by 55 °C.
        "death_Ea": _f(300000.0),        # activation energy (J·mol⁻¹)
        "gas_R": _f(8.314),              # gas constant (J·mol⁻¹·K⁻¹)
        "d_value_ref_min": _f(1.0),      # D-value target at the reference T (minutes)
        "temp_ref_death": _f(55.0),      # E. coli thermal-death reference T (°C)
        "temp_opt": _f(37.0),            # optimal temperature (°C); heat-flux zero point
        "viability_init": _f(1.0),       # starting viability (matches ENV init)
        # linear physical responses to the other drivers
        "elasticity": _f(0.1),           # force returned per unit applied force
        "membrane_conductance": _f(0.05),  # current per unit voltage (Ohm)
        "thermal_conductance": _f(0.02),   # heat flux per °C above optimum
        "signaling_gain": _f(0.4),         # signaling rate at chemical saturation
    }

    def inputs(self):
        return {
            "chemical_ext": "concentration",
            "mechanical_ext": "force",
            "electrical_ext": "voltage",
            "thermal_ext": "temperature",
        }

    def outputs(self):
        return {
            "chemical": "chemical_flux",
            "mechanical": "force",
            "electrical": "current",
            "thermal": "heat_flux",
            "growth_rate": "growth_rate",
            "shape": "volume",
            "signaling": "signaling_rate",
            "objective": "objective",
            "viability": "viability",
        }

    def _set(self, port, value):
        """Delta that carries the additive store for an instantaneous port to
        ``value`` (set-semantics over process-bigraph's accumulate-by-default)."""
        if not hasattr(self, "_last"):
            self._last = {}
        delta = value - self._last.get(port, 0.0)
        self._last[port] = value
        return delta

    def update(self, state, interval):
        c = self.config
        chem = float(state.get("chemical_ext", 0.0))
        mech = float(state.get("mechanical_ext", 0.0))
        volt = float(state.get("electrical_ext", 0.0))
        temp = float(state.get("thermal_ext", 0.0))

        # Monod growth on the chemical supply
        denom = c["km"] + chem
        growth = c["growth_max"] * chem / denom if denom else 0.0
        saturation = chem / denom if denom else 0.0

        # instantaneous exchange responses
        chemical_flux = -c["uptake_rate"] * chem                  # net uptake
        force = c["elasticity"] * mech                            # elastic return
        current = c["membrane_conductance"] * volt               # Ohmic
        heat_flux = c["thermal_conductance"] * (temp - c["temp_opt"])  # Fourier
        signaling = c["signaling_gain"] * saturation             # Monod-scaled

        # Arrhenius thermal death: k(T) = A·exp(−Ea/RT), dV/dt = −k(T)·V.
        # A is fixed by the E. coli D-value at the reference temperature, so
        # k(T_ref) = ln(10)/D_ref (a 1-log kill in D_ref minutes). Time here is in
        # minutes. Integrated exactly per step (exp) to stay in [0, 1] even for
        # large k·interval. temp is °C → Kelvin.
        Ea, R = c["death_Ea"], c["gas_R"]
        T_K = temp + 273.15
        T_ref_K = c["temp_ref_death"] + 273.15
        k_ref = math.log(10.0) / c["d_value_ref_min"]           # k at reference T
        k_death = k_ref * math.exp((Ea / R) * (1.0 / T_ref_K - 1.0 / T_K)) if T_K > 0 else 0.0
        v = getattr(self, "_viability", c["viability_init"])
        dv = v * (math.exp(-k_death * interval) - 1.0)          # V·(e^{-kΔt} − 1) ≤ 0
        self._viability = v + dv

        # accumulating pools: volume + biomass-proxy objective grow with growth
        d_shape = c["shape_growth_coupling"] * growth * interval
        d_objective = c["objective_yield"] * growth * interval

        return {
            "chemical": self._set("chemical", chemical_flux),
            "mechanical": self._set("mechanical", force),
            "electrical": self._set("electrical", current),
            "thermal": self._set("thermal", heat_flux),
            "growth_rate": self._set("growth_rate", growth),
            "signaling": self._set("signaling", signaling),
            "shape": d_shape,
            "objective": d_objective,
            "viability": dv,
        }


# ── Fig 4b · a SECOND conforming handler: same contract, different mechanism ──
# The whole point of the cellular-interface *contract* (Fig 4b) is that it names
# only the externally observable exchange relation — the typed ``cell`` ports —
# and commits to no internal mechanism. ``CellularInterfaceHandler`` realizes it
# with first-order (diffusion-limited) uptake + independent Monod growth +
# Arrhenius thermal death. This handler realizes the SAME contract (byte-identical
# ``inputs``/``outputs``) with a genuinely DIFFERENT internal organization, each
# interface relation carried by a different functional law:
#
#   * uptake        — a SATURABLE MEMBRANE CARRIER (Michaelis–Menten transporter),
#                     ``-Vmax·c/(Ku + c)``, operating below saturation — a bending,
#                     capacity-limited flux rather than the twin's straight
#                     first-order ``-uptake_rate·c``.
#   * growth        — a COOPERATIVE (Moser / Hill, n>1) growth law,
#                     ``growth_max·cⁿ/(Kⁿ + cⁿ)``, a sigmoid rather than the twin's
#                     n=1 Monod hyperbola.
#   * thermal death — a Q10 temperature-coefficient power law,
#                     ``k(T) = k_opt · Q10^((T−T_opt)/10)``, rather than Arrhenius.
#
# The parameters are fitted so the interface-level observables track
# ``CellularInterfaceHandler``'s across the interface's whole OPERATING RANGE of
# chemical supply (chem ∈ [0.2, 2.5] at T = 37 °C) — not just at one point — to
# within a measured, non-zero tolerance (max relative divergence ~10%, dominated
# by the cooperative growth law; see ``tests/test_cellular_interface_substitutability``).
# Two independent boxes, one coarse-grained cellular-interface relation:
# mechanism-independence measured across the operating range of the contract itself.

class CooperativeCellularInterfaceHandler(Process):
    """The cellular interface realized by a DIFFERENT internal mechanism than
    :class:`CellularInterfaceHandler`: a saturable Michaelis–Menten membrane
    carrier for uptake, an independent cooperative (Moser/Hill n>1) growth law, and
    Q10 thermal death — where the twin uses first-order uptake, Monod growth, and
    Arrhenius death. Declares byte-identical ports to ``CellularInterfaceHandler``
    and, across the interface's operating range of chemical supply, produces
    interface observables that agree with it within tolerance — the same externally
    observable relation from a genuinely different box."""

    config_schema = {
        # saturable membrane-carrier uptake (Michaelis–Menten): -Vmax·c/(Ku + c).
        # Ku sits well above the operating range so the carrier runs below
        # saturation — a bending, capacity-limited flux, not the twin's first-order
        # straight line; fitted (with Vmax) to track -uptake_rate·c to <9% over
        # chem ∈ [0.2, 2.5].
        "uptake_vmax": _f(10.6),         # carrier maximum uptake rate
        "uptake_ku": _f(12.0),           # carrier half-saturation concentration
        # independent cooperative (Moser/Hill) growth: growth_max·cⁿ/(Kⁿ + cⁿ),
        # n>1 → a sigmoid, a genuinely different law from the twin's n=1 Monod
        # hyperbola; K,n fitted to track it to ~10% over chem ∈ [0.2, 2.5].
        "growth_max": _f(0.6),           # max specific growth rate (hr⁻¹)
        "growth_k": _f(0.455),           # growth half-saturation concentration
        "growth_n": _f(1.3),             # cooperativity exponent (>1)
        # goal-directed accretion (same downstream couplings as the Monod twin)
        "shape_growth_coupling": _f(1.0),  # volume gained per unit growth·interval
        "objective_yield": _f(0.5),        # biomass-proxy gained per unit growth
        # thermal death — Q10 power law, k(T) = k_opt · Q10^((T−T_opt)/10).
        # k_opt is pinned to the Arrhenius twin's death rate at the 37 °C optimum
        # so viability tracks it there; Q10 sets how death accelerates with heat.
        "death_rate_opt": _f(0.0039),    # first-order death rate at T_opt (per min)
        "death_q10": _f(6.0),            # thermal-death temperature coefficient
        "temp_opt": _f(37.0),            # optimal temperature (°C); heat-flux zero point
        "viability_init": _f(1.0),       # starting viability (matches ENV init)
        # linear physical responses to the other drivers (same as the twin)
        "elasticity": _f(0.1),           # force returned per unit applied force
        "membrane_conductance": _f(0.05),  # current per unit voltage (Ohm)
        "thermal_conductance": _f(0.02),   # heat flux per °C above optimum
        "signaling_gain": _f(0.4),         # signaling rate at chemical saturation
    }

    def inputs(self):
        return {
            "chemical_ext": "concentration",
            "mechanical_ext": "force",
            "electrical_ext": "voltage",
            "thermal_ext": "temperature",
        }

    def outputs(self):
        return {
            "chemical": "chemical_flux",
            "mechanical": "force",
            "electrical": "current",
            "thermal": "heat_flux",
            "growth_rate": "growth_rate",
            "shape": "volume",
            "signaling": "signaling_rate",
            "objective": "objective",
            "viability": "viability",
        }

    def _set(self, port, value):
        """Delta that carries the additive store for an instantaneous port to
        ``value`` (set-semantics over process-bigraph's accumulate-by-default)."""
        if not hasattr(self, "_last"):
            self._last = {}
        delta = value - self._last.get(port, 0.0)
        self._last[port] = value
        return delta

    def update(self, state, interval):
        c = self.config
        chem = float(state.get("chemical_ext", 0.0))
        mech = float(state.get("mechanical_ext", 0.0))
        volt = float(state.get("electrical_ext", 0.0))
        temp = float(state.get("thermal_ext", 0.0))

        # saturable membrane-carrier uptake: a capacity-limited (bending) flux
        uptake = c["uptake_vmax"] * chem / (c["uptake_ku"] + chem) if (c["uptake_ku"] + chem) else 0.0
        chemical_flux = -uptake                        # net uptake (negative)

        # independent cooperative (Moser/Hill) growth on the chemical supply
        n = c["growth_n"]
        cn = chem ** n
        kn = c["growth_k"] ** n
        gdenom = kn + cn
        saturation = cn / gdenom if gdenom else 0.0
        growth = c["growth_max"] * saturation

        # instantaneous exchange responses (same linear laws as the Monod twin)
        force = c["elasticity"] * mech                            # elastic return
        current = c["membrane_conductance"] * volt               # Ohmic
        heat_flux = c["thermal_conductance"] * (temp - c["temp_opt"])  # Fourier
        signaling = c["signaling_gain"] * saturation             # cooperative-scaled

        # Q10 thermal death: k(T) = k_opt · Q10^((T−T_opt)/10), dV/dt = −k(T)·V.
        # Integrated exactly per step (exp) to stay in [0, 1]. Time in minutes.
        k_death = c["death_rate_opt"] * c["death_q10"] ** ((temp - c["temp_opt"]) / 10.0)
        v = getattr(self, "_viability", c["viability_init"])
        dv = v * (math.exp(-k_death * interval) - 1.0)          # V·(e^{-kΔt} − 1) ≤ 0
        self._viability = v + dv

        # accumulating pools: volume + biomass-proxy objective grow with growth
        d_shape = c["shape_growth_coupling"] * growth * interval
        d_objective = c["objective_yield"] * growth * interval

        return {
            "chemical": self._set("chemical", chemical_flux),
            "mechanical": self._set("mechanical", force),
            "electrical": self._set("electrical", current),
            "thermal": self._set("thermal", heat_flux),
            "growth_rate": self._set("growth_rate", growth),
            "signaling": self._set("signaling", signaling),
            "shape": d_shape,
            "objective": d_objective,
            "viability": dv,
        }


# ── handler environment ⟦C⟧_H : the compiler swaps this in for the draft ──────
# init sets store leaves' ``_default`` (process-bigraph realize IGNORES _value):
# the environmental drivers seed the sim, and viability/shape start at their
# biological baselines so the handler's set/accumulate deltas stay consistent.
ENV = {
    "CellularInterface": {
        "handler": "CellularInterfaceHandler",
        "config": {
            "uptake_rate": 0.8,
            "growth_max": 0.6,
            "km": 0.5,
            "shape_growth_coupling": 1.0,
            "objective_yield": 0.5,
            "death_Ea": 300000.0,
            "gas_R": 8.314,
            "d_value_ref_min": 1.0,
            "temp_ref_death": 55.0,
            "temp_opt": 37.0,
            "viability_init": 1.0,
            "elasticity": 0.1,
            "membrane_conductance": 0.05,
            "thermal_conductance": 0.02,
            "signaling_gain": 0.4,
        },
        "init": {
            "environment.chemical": 1.0,
            "environment.thermal": 37.0,
            "environment.mechanical": 0.0,
            "environment.electrical": 0.0,
            "interface.shape": 1.0,
            "interface.viability": 1.0,
        },
    }
}
