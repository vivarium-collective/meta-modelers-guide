"""Toy-real handlers — executable Process implementations of the figures' effect
signatures (draft processes). Each handler exposes the EXACT draft port names so
the semantic composite's wiring transfers verbatim under compilation, and has a
genuine ``update`` (no fabricated constants). See compile.py + the concept doc.

Handlers are auto-registered at ``local:<ClassName>`` by build_core (top-level
module). Ports are declared config-independently so conformance can be checked
before instantiation.
"""
from __future__ import annotations

from process_bigraph import Process


def _f(default):  # a float config field
    return {"_type": "float", "_default": default}


# ── Fig 6 · metabolism signature: two conforming handlers (law #4) ───────────
# signature CoarseGrainedMetabolism:
#   in  {nutrients: chemical_flux}
#   out {biomass: mass, energy: energy, entropy: entropy, secretions: chemical_flux}

class CoarseMetabolism(Process):
    """Coarse grain: the whole network lumped into linear yields on the nutrient
    supply (dX/dt = Y · nutrients)."""
    config_schema = {
        "biomass_yield": _f(0.5), "energy_yield": _f(0.3),
        "entropy_rate": _f(0.1), "secretion_frac": _f(0.2),
    }

    def inputs(self):
        return {"nutrients": "chemical_flux"}

    def outputs(self):
        return {"biomass": "mass", "energy": "energy",
                "entropy": "entropy", "secretions": "chemical_flux"}

    def update(self, state, interval):
        n = float(state.get("nutrients", 0.0))
        c = self.config
        return {
            "biomass": c["biomass_yield"] * n * interval,
            "energy": c["energy_yield"] * n * interval,
            "entropy": c["entropy_rate"] * n * interval,
            "secretions": c["secretion_frac"] * n * interval,
        }


class KineticMetabolism(Process):
    """Fine grain, same interface: a saturating (Michaelis–Menten) uptake law
    standing in for resolved enzyme kinetics, coarse-grained back to the cell's
    nutrient→biomass exchange ports. Same signature as CoarseMetabolism, different
    dynamics — the demonstration of handler independence (law #4)."""
    config_schema = {
        "vmax": _f(1.0), "km": _f(0.5),
        "biomass_yield": _f(0.5), "energy_yield": _f(0.3),
        "entropy_rate": _f(0.1), "secretion_frac": _f(0.2),
    }

    def inputs(self):
        return {"nutrients": "chemical_flux"}

    def outputs(self):
        return {"biomass": "mass", "energy": "energy",
                "entropy": "entropy", "secretions": "chemical_flux"}

    def update(self, state, interval):
        n = float(state.get("nutrients", 0.0))
        c = self.config
        rate = c["vmax"] * n / (c["km"] + n) if (c["km"] + n) else 0.0
        return {
            "biomass": c["biomass_yield"] * rate * interval,
            "energy": c["energy_yield"] * rate * interval,
            "entropy": c["entropy_rate"] * rate * interval,
            "secretions": c["secretion_frac"] * rate * interval,
        }


class KineticReactionNetwork(Process):
    """Molecular grain: mass-action kinetics for the catalyzed reaction network.
    signature CatalyzedReactionNetwork: in {substrates, catalysts} → out {products}."""
    config_schema = {"k": _f(0.2)}

    def inputs(self):
        return {"substrates": "concentration", "catalysts": "concentration"}

    def outputs(self):
        return {"products": "concentration"}

    def update(self, state, interval):
        s = float(state.get("substrates", 0.0))
        cat = float(state.get("catalysts", 0.0))
        return {"products": self.config["k"] * s * cat * interval}
