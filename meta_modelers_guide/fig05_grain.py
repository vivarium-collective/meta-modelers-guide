"""Fig 5 · a process swapped between grains as a function of viability.

The runnable demonstration behind Fig 5b's *grain swap*. A cell's ``viability`` is
driven down by a simple external stress ramp. A :class:`GrainSelector` watches
that signal and picks which grain realizes the shared interface: while the cell is
comfortably viable the cheap **coarse** grain grows its biomass; once viability
falls below a threshold the mechanistic **fine** grain is swapped in to resolve the
regime that matters at the boundary — the cell is dying, so biomass stops growing
and DECAYS. Two gated processes act on the same ``biomass`` output at different
grains — :class:`CoarseGrainProcess` (linear growth while viable) and
:class:`FineGrainProcess` (first-order decay once past the threshold) — and exactly
one is active per tick, so as viability slides past the threshold **control switches
from the coarse growth process to the fine decay process** on-screen: the biomass
trajectory turns over from growth to decline.

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
    """Fine grain — the mechanistic DEATH/decay regime, resolved once the cell
    crosses the viability boundary.

    A viable cell GROWS (the coarse grain adds biomass). Below the viability
    threshold the cell has stopped growing and is dying: its ``biomass`` now DECAYS
    first-order — dX/dt = −decay_rate·biomass, and its ``energy`` reserve drains
    with it — the dynamics the coarse growth model cannot capture. Active ONLY when
    ``active_grain == "fine"``; otherwise a no-op. So at the switch the biomass
    trajectory turns over: growth → arrest → decay.
    """

    config_schema = {"decay_rate": _f(0.09), "energy_decay": _f(0.09)}

    def inputs(self):
        return {"biomass": "mass", "energy": "energy", "active_grain": "string"}

    def outputs(self):
        return {"biomass": "mass", "energy": "energy"}

    def update(self, state, interval):
        if state.get("active_grain") != "fine":
            return {}
        x = float(state.get("biomass", 0.0))
        e = float(state.get("energy", 0.0))
        c = self.config
        return {
            "biomass": -c["decay_rate"] * x * interval,
            "energy": -c["energy_decay"] * e * interval,
        }
