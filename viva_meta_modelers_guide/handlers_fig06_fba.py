"""Phase 2 · a REAL-simulator handler for the Fig 6 metabolism signature.

The concept doc anticipates this: "the same signature can later be handled by a
real external simulator (COBRA/dFBA, tellurium/COPASI, …) — the swap is exactly a
new, conforming handler, with the interface preserved by law 2." Here that handler
is genuine flux-balance analysis via **COBRApy**: each step it sets the nutrient
uptake bound from the incoming chemical flux, solves the LP for maximum biomass
flux, and reports biomass/energy/entropy/secretions on the same four ports the toy
``CoarseMetabolism`` and ``KineticMetabolism`` handlers use. So Fig 6 now has THREE
conforming handlers over one interface (law 4): linear, saturating, and real FBA —
toy vs. real, not toy vs. toy.

``cobra`` is a heavy optional dependency, imported **lazily** so this module (and
therefore build_core discovery + executable materialization) works without it.
Running the compiled composite raises a clear error if cobra is absent; the tests
skip in that case (``importorskip('cobra')``). Install with ``pip install cobra``.
"""
from __future__ import annotations

from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


class FBAMetabolism(Process):
    """Real flux-balance-analysis metabolism (COBRApy). Same signature as the Fig 6
    coarse/kinetic handlers — ``nutrients ⇒ biomass, energy, entropy, secretions`` —
    but the biomass flux is the LP optimum of a small metabolic network whose
    nutrient-uptake bound is driven by the incoming flux each step (a minimal dFBA
    step)."""

    config_schema = {
        "uptake_scale": _f(1.0),        # uptake bound = uptake_scale · nutrient flux
        "biomass_capacity": _f(0.8),    # LP cap on biomass flux (a network constraint)
        "biomass_yield": _f(0.5),       # mass produced per unit biomass flux
        "energy_yield": _f(0.3),
        "entropy_rate": _f(0.1),
        "secretion_frac": _f(0.2),
    }

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._model = None

    def inputs(self):
        return {"nutrients": "chemical_flux"}

    def outputs(self):
        return {"biomass": "mass", "energy": "energy",
                "entropy": "entropy", "secretions": "chemical_flux"}

    def _build_model(self):
        try:
            from cobra import Model, Reaction, Metabolite
        except Exception as exc:  # pragma: no cover - exercised only without cobra
            raise RuntimeError(
                "FBAMetabolism requires the optional 'cobra' package "
                "(pip install cobra). Use the CoarseMetabolism/KineticMetabolism "
                "handlers for a dependency-free Fig 6.") from exc
        model = Model("fig06_fba")
        nutrient = Metabolite("nutrient_c", compartment="c")
        biomass = Metabolite("biomass_c", compartment="c")
        uptake = Reaction("EX_nutrient")
        uptake.add_metabolites({nutrient: 1}); uptake.lower_bound = 0; uptake.upper_bound = 0
        grow = Reaction("BIOMASS")
        grow.add_metabolites({nutrient: -1, biomass: 1}); grow.lower_bound = 0
        # a genuine network constraint: biomass flux is capped, so the LP optimum
        # is min(uptake, capacity) — FBA differs from the linear/kinetic handlers
        # because of a network limit, not just a rate constant.
        grow.upper_bound = self.config["biomass_capacity"]
        sink = Reaction("DM_biomass")
        sink.add_metabolites({biomass: -1}); sink.lower_bound = 0; sink.upper_bound = 1000
        model.add_reactions([uptake, grow, sink])
        model.objective = "BIOMASS"
        self._model = model

    def update(self, state, interval):
        if self._model is None:
            self._build_model()
        nutrients = float(state.get("nutrients", 0.0))
        c = self.config
        self._model.reactions.EX_nutrient.upper_bound = max(0.0, c["uptake_scale"] * nutrients)
        flux = self._model.slim_optimize()  # biomass flux (nan if infeasible)
        flux = 0.0 if flux != flux else float(flux)
        return {
            "biomass": c["biomass_yield"] * flux * interval,
            "energy": c["energy_yield"] * flux * interval,
            "entropy": c["entropy_rate"] * flux * interval,
            "secretions": c["secretion_frac"] * flux * interval,
        }


# ── handler environment ⟦Fig6⟧_H (real FBA) — a third env over the same interface ─
ENV = {
    "CoarseGrainedMetabolism": {
        "handler": "FBAMetabolism",
        "config": {"uptake_scale": 1.0, "biomass_capacity": 0.8, "biomass_yield": 0.5,
                   "energy_yield": 0.3, "entropy_rate": 0.1, "secretion_frac": 0.2},
        "init": {"coarse.nutrients": 1.0},
    },
    # the molecular sub-network keeps its (dependency-free) kinetic handler.
    "CatalyzedReactionNetwork": {
        "handler": "KineticReactionNetwork",
        "config": {"k": 0.2},
        "init": {"molecular.substrates": 1.0, "molecular.catalysts": 1.0},
    },
}
