"""Fig 3 (paper §Cellular interface) · a *mechanistic* cellular interface with a
shared internal energy/metabolism state.

This is the real-mechanism upgrade of ``handlers_fig03b`` (the
``CellularInterfaceHandler``, kept as the didactic baseline). In the baseline each
output port is an INDEPENDENT function of its own driver — uptake ∝ nutrient,
growth = Monod(nutrient), viability = Arrhenius(T) — so "the interface responds"
says nothing about coherent physiology: the ports never talk to each other. The
review's objection is exactly that.

Here the ports are COUPLED through two shared internal state variables — an ATP
pool and a temperature-set enzyme activity — so a perturbation PROPAGATES:

    nutrient ──▶ (enzyme-limited, saturating) uptake ──▶ ATP production
    ATP ──▶ growth (anabolism, ATP-limited) AND maintenance (basal drain)
    temperature ──▶ enzyme activity ──▶ uptake AND growth
    ATP deficit (production < maintenance) OR heat ──▶ viability decline
    viability ──▶ gates growth

So dropping the nutrient moves ATP, growth, biomass AND viability (not just the
"chemical" port); raising the temperature throttles enzyme activity and cascades
the same way. A metabolically-disabled cell (``catalytic_capacity`` = ε) cannot
turn nutrient into ATP, so the propagation breaks — the matched-null control.

Typed ports (units): INPUTS nutrient (concentration, mol·L⁻¹), temperature (°C).
OUTPUTS uptake (chemical_flux), atp (energy pool), biomass (mass), viability
(0–1), growth_rate (hr⁻¹), enzyme_activity (fraction 0–1), atp_production
(chemical_flux). Instantaneous ports use set-semantics; atp/biomass/viability are
accumulating pools. Classes auto-register at ``local:<ClassName>`` via build_core.
"""
from __future__ import annotations

import math

from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


class MetabolicCell(Process):
    """A cellular interface whose ports are coupled through a shared ATP pool and a
    temperature-set enzyme activity. Uptake feeds ATP; ATP funds growth and a basal
    maintenance drain; temperature throttles enzyme activity (hence uptake and
    growth); an ATP deficit or heat erodes viability; viability gates growth."""

    config_schema = {
        # uptake (enzyme-limited saturating transporter)
        "vmax_uptake": _f(1.0),       # max uptake at full enzyme activity (flux)
        "km": _f(0.5),                # half-saturation nutrient (mol·L⁻¹)
        "atp_yield": _f(2.0),         # ATP produced per unit nutrient taken up
        "catalytic_capacity": _f(1.0),  # overall metabolic capacity; ε disables metabolism
        # enzyme activity vs temperature — a Gaussian thermal window (0–1)
        "temp_opt": _f(37.0),         # °C, activity peak
        "temp_width": _f(9.0),        # °C, width of the activity window
        # growth (ATP-limited anabolism) + maintenance (basal ATP drain)
        "growth_max": _f(0.6),        # max specific growth rate (hr⁻¹)
        "k_atp": _f(1.0),             # ATP half-saturation for growth
        "atp_per_biomass": _f(1.5),   # ATP spent per unit biomass made
        "maintenance_rate": _f(0.25), # basal ATP drain per interval
        "atp_min": _f(0.0),           # ATP pool floor
        # viability: thermal denaturation + energy-starvation stress
        "k_thermal": _f(0.02),        # thermal-death rate scale (per interval, per unit over-activity-loss)
        "k_energy": _f(0.15),         # viability loss rate under full energy starvation
    }

    def inputs(self):
        return {"nutrient": "concentration", "temperature": "temperature",
                "atp": "energy", "biomass": "mass", "viability": "viability"}

    def outputs(self):
        return {
            "uptake": "chemical_flux",
            "atp": "energy",
            "biomass": "mass",
            "viability": "viability",
            "growth_rate": "growth_rate",
            "enzyme_activity": "fraction",
            "atp_production": "chemical_flux",
            "maintenance": "chemical_flux",
        }

    def _set(self, port, value):
        if not hasattr(self, "_last"):
            self._last = {}
        d = value - self._last.get(port, 0.0)
        self._last[port] = value
        return d

    def update(self, state, interval):
        c = self.config
        nutrient = max(float(state.get("nutrient", 0.0)), 0.0)
        temp = float(state.get("temperature", c["temp_opt"]))
        atp = max(float(state.get("atp", 0.0)), 0.0)
        viability = min(max(float(state.get("viability", 1.0)), 0.0), 1.0)

        cap = c["catalytic_capacity"]
        # enzyme activity: a temperature window in [0, 1], scaled by metabolic capacity
        enzyme = cap * math.exp(-((temp - c["temp_opt"]) / c["temp_width"]) ** 2)

        # SHARED NODE 1 — uptake is enzyme-limited AND saturating in nutrient
        uptake = enzyme * c["vmax_uptake"] * nutrient / (c["km"] + nutrient) if (c["km"] + nutrient) else 0.0
        atp_production = c["atp_yield"] * uptake

        # SHARED NODE 2 — growth is ATP-limited, enzyme-limited, viability-gated
        atp_sat = atp / (c["k_atp"] + atp) if (c["k_atp"] + atp) else 0.0
        growth = c["growth_max"] * atp_sat * enzyme * viability
        growth_atp_cost = c["atp_per_biomass"] * growth
        maintenance = c["maintenance_rate"]

        # ATP pool balance (bounded ≥ atp_min); growth throttled if it would overdraw
        d_atp = (atp_production - growth_atp_cost - maintenance) * interval
        if atp + d_atp < c["atp_min"]:
            d_atp = c["atp_min"] - atp

        # viability: thermal denaturation (loss of enzyme activity from heat) + energy starvation
        heat_loss = max(0.0, cap - enzyme)                      # how far below peak activity (heat only)
        energy_stress = max(0.0, (maintenance - atp_production) / maintenance) if maintenance else 0.0
        k_v = c["k_thermal"] * heat_loss + c["k_energy"] * energy_stress
        dv = viability * (math.exp(-k_v * interval) - 1.0)      # ≤ 0

        d_biomass = growth * interval

        return {
            "uptake": self._set("uptake", uptake),
            "atp": d_atp,
            "biomass": d_biomass,
            "viability": dv,
            "growth_rate": self._set("growth_rate", growth),
            "enzyme_activity": self._set("enzyme_activity", enzyme),
            "atp_production": self._set("atp_production", atp_production),
            "maintenance": self._set("maintenance", maintenance),
        }


class EnvironmentStep(Process):
    """The environment: holds nutrient and temperature, each able to STEP once at a
    set time, so a run can perturb one input and watch the response propagate
    through the cell's shared state. Set-semantics into the shared environment
    stores."""

    config_schema = {
        "nutrient_hi": _f(2.0), "nutrient_lo": _f(2.0), "nutrient_step_time": _f(1e9),
        "temp_base": _f(37.0), "temp_step": _f(37.0), "temp_step_time": _f(1e9),
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"nutrient": "concentration", "temperature": "temperature"}

    def _set(self, port, value):
        if not hasattr(self, "_last"):
            self._last = {}
        d = value - self._last.get(port, 0.0)
        self._last[port] = value
        return d

    def update(self, state, interval):
        c = self.config
        if not hasattr(self, "_t"):
            self._t = 0.0
            # seed _last with the base values so the first delta is 0 (the env
            # stores already default to the base values — avoid double-adding).
            self._last = {"nutrient": c["nutrient_hi"], "temperature": c["temp_base"]}
        self._t += interval
        nutrient = c["nutrient_lo"] if self._t >= c["nutrient_step_time"] else c["nutrient_hi"]
        temp = c["temp_step"] if self._t >= c["temp_step_time"] else c["temp_base"]
        return {"nutrient": self._set("nutrient", nutrient),
                "temperature": self._set("temperature", temp)}
