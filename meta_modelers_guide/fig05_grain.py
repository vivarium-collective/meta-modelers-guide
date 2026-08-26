"""Fig 5 · a process swapped between grains as a function of viability.

The runnable demonstration behind Fig 5b's *grain swap*. A cell's ``viability`` is
driven down by a simple external stress ramp. A :class:`GrainSelector` watches
that signal and picks which grain realizes the shared interface: while the cell is
comfortably viable the cheap **coarse** grain suffices; once viability falls below
a threshold the mechanistic **fine** grain is swapped in to resolve the regime that
matters near the boundary. Two gated processes realize the same ``biomass`` output
at different grains — :class:`CoarseGrainProcess` (cheap linear yield) and
:class:`FineGrainProcess` (saturating Michaelis–Menten kinetics) — and exactly one
is active per tick, so as viability slides past the threshold **control switches
from the coarse process to the fine process** on-screen.

Decision (spec Pilot B): low viability → fine grain; above threshold → coarse.

All four classes are auto-registered at ``local:<ClassName>`` by ``build_core``.
Mirrors the small-handler style of :mod:`meta_modelers_guide.handlers`.
"""
from __future__ import annotations

from process_bigraph import Process


def _f(default):  # a float config field
    return {"_type": "float", "_default": default}


class StressRamp(Process):
    """External stress: drives ``viability`` steadily down over the run.

    Reads the current viability and returns a NEGATIVE delta (``-stress_rate·
    interval``), clamped so viability never falls below 0. This is the clean,
    controllable driver that slides the cell toward its boundary.
    """

    config_schema = {"stress_rate": _f(0.045)}

    def inputs(self):
        return {"viability": "viability"}

    def outputs(self):
        return {"viability": "viability"}

    def update(self, state, interval):
        v = float(state.get("viability", 0.0))
        drop = self.config["stress_rate"] * interval
        # clamp: never push viability below 0.
        return {"viability": -min(drop, v)}


class GrainSelector(Process):
    """Swap the active grain on the viability function.

    Reads ``viability`` and SETS ``active_grain`` (a string store): ``"coarse"``
    while viability ≥ ``threshold`` (the cheap lumped model suffices), ``"fine"``
    once it drops below (the stressed cell needs the resolved model). The returned
    string uses set-semantics — it overwrites the store rather than accumulating.
    """

    config_schema = {"threshold": _f(0.5)}

    def inputs(self):
        return {"viability": "viability"}

    def outputs(self):
        return {"active_grain": "string"}

    def update(self, state, interval):
        v = float(state.get("viability", 0.0))
        return {"active_grain": "coarse" if v >= self.config["threshold"] else "fine"}


class CoarseGrainProcess(Process):
    """Coarse grain — cheap, lumped realization of the interface.

    Produces ``biomass`` by a linear yield on ``inflow`` (dX/dt = yield · inflow),
    but ONLY when it is the active grain. When ``active_grain != "coarse"`` it
    returns an empty update (no-op), so it goes inert the moment control is handed
    to the fine grain.
    """

    config_schema = {"biomass_yield": _f(0.3), "energy_yield": _f(0.2)}

    def inputs(self):
        return {"inflow": "chemical_flux", "active_grain": "string"}

    def outputs(self):
        return {"biomass": "mass", "energy": "energy"}

    def update(self, state, interval):
        if state.get("active_grain") != "coarse":
            return {}
        n = float(state.get("inflow", 0.0))
        c = self.config
        return {
            "biomass": c["biomass_yield"] * n * interval,
            "energy": c["energy_yield"] * n * interval,
        }


class FineGrainProcess(Process):
    """Fine grain — mechanistic, higher-fidelity realization of the interface.

    Produces ``biomass`` by a saturating Michaelis–Menten law on ``inflow``
    (rate = vmax · inflow / (km + inflow)), standing in for resolved kinetics, but
    ONLY when it is the active grain. When ``active_grain != "fine"`` it returns an
    empty update (no-op). Its per-step production differs visibly from the coarse
    grain, so the switch is legible in the biomass trajectory.
    """

    config_schema = {
        "vmax": _f(1.2), "km": _f(0.5),
        "biomass_yield": _f(1.0), "energy_yield": _f(0.6),
    }

    def inputs(self):
        return {"inflow": "chemical_flux", "active_grain": "string"}

    def outputs(self):
        return {"biomass": "mass", "energy": "energy"}

    def update(self, state, interval):
        if state.get("active_grain") != "fine":
            return {}
        n = float(state.get("inflow", 0.0))
        c = self.config
        rate = c["vmax"] * n / (c["km"] + n) if (c["km"] + n) else 0.0
        return {
            "biomass": c["biomass_yield"] * rate * interval,
            "energy": c["energy_yield"] * rate * interval,
        }
