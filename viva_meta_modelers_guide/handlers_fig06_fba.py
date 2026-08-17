"""Phase 2 · a REAL-simulator handler for the Fig 6 metabolism signature.

The concept doc anticipates this: "the same signature can later be handled by a
real external simulator (COBRA/dFBA, tellurium/COPASI, …) — the swap is exactly a
new, conforming handler, with the interface preserved by law 2." Here that handler
is genuine flux-balance analysis over the **``e_coli_core`` model** (COBRApy's
``load_model('textbook')`` — 95 reactions, the real central-carbon network): each
step it sets the glucose-uptake bound from the incoming nutrient flux, solves the
LP for maximum biomass, and reports biomass/energy/entropy/secretions on the SAME
four ports the toy ``CoarseMetabolism`` and ``KineticMetabolism`` handlers use.

The payoff is the **secretions** port. With oxygen uptake capped (a real
respiratory-capacity constraint), ``e_coli_core`` exhibits **acetate overflow**:
at low glucose the cell fully respires and secretes nothing, but past the
respiratory ceiling it overflows carbon to acetate (``EX_ac_e``). Only the real
network puts acetate on the interface — the coarse/kinetic handlers, which lump
the network into a single yield, structurally cannot. So Fig 6 now has THREE
conforming handlers over one interface (law 4): linear, saturating, and real FBA —
and the real one carries a phenomenon the toys can't express.

``cobra`` is a heavy optional dependency, imported **lazily** and the model is
loaded **once per handler instance** (cached on ``self._model``), never per step —
so this module (and therefore build_core discovery + executable materialization)
works without it, and running stays fast. Running the compiled composite raises a
clear error if cobra is absent; the tests skip in that case. Install with
``pip install cobra``.
"""
from __future__ import annotations

from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


# reaction ids in COBRApy's e_coli_core ("textbook") model
_GLC = "EX_glc__D_e"   # glucose exchange (uptake = negative flux)
_O2 = "EX_o2_e"        # oxygen exchange (uptake = negative flux)
_AC = "EX_ac_e"        # acetate exchange (secretion = positive flux)
_CO2 = "EX_co2_e"      # CO2 exchange (dissipation = positive flux)


class FBAMetabolism(Process):
    """Real flux-balance-analysis metabolism over ``e_coli_core`` (COBRApy). Same
    signature as the Fig 6 coarse/kinetic handlers — ``nutrients ⇒ biomass, energy,
    entropy, secretions`` — but every port carries a genuine flux from the LP
    optimum of the real central-carbon network, with the glucose-uptake bound
    driven by the incoming nutrient flux each step (a minimal dFBA step):

    * ``biomass``    ← biomass-objective flux (growth),
    * ``secretions`` ← acetate efflux ``EX_ac_e`` — the overflow phenotype,
    * ``energy``     ← oxygen uptake ``|EX_o2_e|`` (respiration),
    * ``entropy``    ← CO2 efflux ``EX_co2_e`` (metabolic dissipation).

    Oxygen uptake is capped at ``o2_bound`` so the network has a finite respiratory
    capacity; above it, carbon overflows to acetate. Below it, ``secretions`` is 0.
    """

    config_schema = {
        # glucose uptake bound (mmol·gDW⁻¹·h⁻¹) per unit incoming nutrient flux
        "uptake_scale": _f(10.0),
        # ceiling on glucose uptake, so a large nutrient signal can't run away
        "max_uptake": _f(20.0),
        # oxygen-uptake cap (respiratory capacity) — the overflow enabler.
        # Capping O2 is what makes e_coli_core secrete acetate at high glucose.
        "o2_bound": _f(18.0),
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
            from cobra.io import load_model
        except Exception as exc:  # pragma: no cover - exercised only without cobra
            raise RuntimeError(
                "FBAMetabolism requires the optional 'cobra' package "
                "(pip install cobra). Use the CoarseMetabolism/KineticMetabolism "
                "handlers for a dependency-free Fig 6.") from exc
        # e_coli_core — the real 95-reaction central-carbon network, loaded ONCE.
        model = load_model("textbook")
        # a genuine network constraint: finite respiratory capacity. With O2 capped
        # the LP must overflow carbon to acetate once glucose exceeds what oxidative
        # phosphorylation can burn — this is why FBA (and not the lumped-yield
        # handlers) can put acetate on the secretions port.
        model.reactions.get_by_id(_O2).lower_bound = -abs(self.config["o2_bound"])
        self._model = model

    def update(self, state, interval):
        if self._model is None:
            self._build_model()
        nutrients = max(0.0, float(state.get("nutrients", 0.0)))
        c = self.config
        # map the sensed nutrient flux → glucose uptake lower bound (uptake is a
        # negative exchange flux in COBRA's convention), clamped to a capacity.
        uptake = min(c["max_uptake"], c["uptake_scale"] * nutrients)
        self._model.reactions.get_by_id(_GLC).lower_bound = -uptake

        sol = self._model.optimize()
        if sol.status != "optimal":
            return {"biomass": 0.0, "energy": 0.0, "entropy": 0.0, "secretions": 0.0}

        fx = sol.fluxes
        growth = float(sol.objective_value)
        acetate = max(0.0, float(fx[_AC]))       # secretion (efflux ≥ 0)
        o2_uptake = abs(float(fx[_O2]))          # respiration (energy proxy)
        co2 = max(0.0, float(fx[_CO2]))          # dissipation (entropy proxy)
        # nan guard (infeasible corners)
        growth = 0.0 if growth != growth else growth
        return {
            "biomass": growth * interval,
            "energy": o2_uptake * interval,
            "entropy": co2 * interval,
            "secretions": acetate * interval,     # ← acetate overflow appears here
        }


class NonConformingMetabolism(Process):
    """An IMPOSTOR handler for the Fig 6 metabolism signature — deliberately
    non-conforming, to make the compiler's type judgment a visible scene.

    It looks like a metabolism handler but does NOT supply the signature's ports:
    it renames the biomass output to ``growth`` with the wrong type (``growth_rate``
    instead of ``mass``) and drops ``energy``/``entropy``/``secretions`` entirely.
    Compiling it against ``CoarseGrainedMetabolism`` raises ``CompileError`` naming
    every missing port — one interface, three mechanisms accepted, one rejected.
    """

    config_schema = {"rate": _f(0.5)}

    def inputs(self):
        return {"nutrients": "chemical_flux"}

    def outputs(self):
        # WRONG: 'growth: growth_rate' is neither the required 'biomass: mass' nor
        # any of the other required output ports.
        return {"growth": "growth_rate"}

    def update(self, state, interval):
        n = float(state.get("nutrients", 0.0))
        return {"growth": self.config["rate"] * n}


# ── handler environment ⟦Fig6⟧_H (real FBA) — a third env over the same interface ─
ENV = {
    "CoarseGrainedMetabolism": {
        "handler": "FBAMetabolism",
        "config": {"uptake_scale": 10.0, "max_uptake": 20.0, "o2_bound": 18.0},
        "init": {"coarse.nutrients": 1.0},
    },
    # the molecular sub-network keeps its (dependency-free) kinetic handler.
    "CatalyzedReactionNetwork": {
        "handler": "KineticReactionNetwork",
        "config": {"k": 0.2},
        "init": {"molecular.substrates": 1.0, "molecular.catalysts": 1.0},
    },
}
