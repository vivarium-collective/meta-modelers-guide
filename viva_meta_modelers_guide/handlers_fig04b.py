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
* **viability**         — relaxes toward 1 while ``thermal_ext`` is inside the
  tolerance band ``[temp_opt ± temp_tol]``, else decays toward 0.
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
        # thermal viability band
        "temp_opt": _f(37.0),            # optimal temperature (°C)
        "temp_tol": _f(5.0),             # half-width of the survivable band
        "viability_relax": _f(0.3),      # rate viability relaxes to its target
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

        # viability relaxes toward 1 inside the thermal tolerance band, else to 0
        in_band = abs(temp - c["temp_opt"]) <= c["temp_tol"]
        target = 1.0 if in_band else 0.0
        v = getattr(self, "_viability", c["viability_init"])
        dv = c["viability_relax"] * (target - v) * interval
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
            "temp_opt": 37.0,
            "temp_tol": 5.0,
            "viability_relax": 0.3,
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
