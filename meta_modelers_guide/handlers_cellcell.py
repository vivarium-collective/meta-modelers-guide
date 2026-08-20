"""Cell–cell coupling handlers — two cells over ONE shared nutrient store.

Competition and cross-feeding are two handler environments over the same coupling
interface (law 4). Both deplete the shared pool; the cross-feeding cell also
returns a usable byproduct, so the pair persists where competition starves one.
Handlers auto-registered at ``local:<ClassName>`` by build_core."""
from __future__ import annotations

from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


class NutrientPool(Process):
    """Shared environmental pool: bounded first-order replenishment toward capacity."""
    config_schema = {"supply": _f(0.02), "capacity": _f(1.0)}

    def inputs(self):
        return {"nutrient": "concentration"}

    def outputs(self):
        return {"nutrient": "concentration"}

    def update(self, state, interval):
        n = float(state.get("nutrient", 0.0))
        c = self.config
        return {"nutrient": c["supply"] * (c["capacity"] - n) * interval}


class CompetingCell(Process):
    """Saturating uptake from the shared pool; viability falls when uptake drops
    below maintenance. Depletes the shared nutrient (negative delta) — the coupling.
    ``vmax`` sets competitive strength; the compete env assigns a HIGHER ``vmax`` to
    the ``CellAgent`` role than to the ``RivalCellAgent`` role (two draft roles over
    the same coupling interface — see handler_envs.py), so the asymmetry is entirely
    an env-layer choice, not something this handler or the draft composite bakes in."""
    config_schema = {"vmax": _f(0.6), "km": _f(0.3), "yield_": _f(0.5),
                     "maintenance": _f(0.15), "via_gain": _f(0.4)}

    def inputs(self):
        return {"nutrient": "concentration", "viability": "viability"}

    def outputs(self):
        return {"nutrient": "concentration", "biomass": "mass", "viability": "viability"}

    def update(self, state, interval):
        n = float(state.get("nutrient", 0.0))
        v = float(state.get("viability", 1.0))
        c = self.config
        uptake = c["vmax"] * n / (c["km"] + n) if (c["km"] + n) else 0.0
        # viability climbs toward 1 when uptake beats maintenance, falls otherwise.
        surplus = uptake - c["maintenance"]
        target = 1.0 if surplus >= 0 else 0.0
        dv = c["via_gain"] * (target - v) * interval
        return {"nutrient": -uptake * interval,
                "biomass": c["yield_"] * uptake * v * interval,
                "viability": dv}


class CrossFeedingCell(Process):
    """Same coupling interface as CompetingCell, but returns a usable byproduct to
    the shared pool (partial return), so the pair does not exhaust the resource and
    both stay above maintenance — cooperation stabilizes viability (law 4 contrast)."""
    config_schema = {"vmax": _f(0.6), "km": _f(0.3), "yield_": _f(0.5),
                     "maintenance": _f(0.15), "via_gain": _f(0.4), "return_frac": _f(0.7)}

    def inputs(self):
        return {"nutrient": "concentration", "viability": "viability"}

    def outputs(self):
        return {"nutrient": "concentration", "biomass": "mass", "viability": "viability"}

    def update(self, state, interval):
        n = float(state.get("nutrient", 0.0))
        v = float(state.get("viability", 1.0))
        c = self.config
        uptake = c["vmax"] * n / (c["km"] + n) if (c["km"] + n) else 0.0
        surplus = uptake - c["maintenance"]
        target = 1.0 if surplus >= 0 else 0.0
        dv = c["via_gain"] * (target - v) * interval
        net = uptake * (1.0 - c["return_frac"])  # byproduct returned to the pool
        return {"nutrient": -net * interval,
                "biomass": c["yield_"] * uptake * v * interval,
                "viability": dv}
