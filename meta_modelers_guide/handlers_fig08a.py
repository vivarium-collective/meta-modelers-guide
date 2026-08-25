"""Fig 9a · coarse-graining stack — executable handlers for the three biological
functions (metabolism, containment, replication) each at three grains.

Fig 9a is the atlas's second worked example of handler independence (law 4),
alongside Fig 6: the same function appears at a coarse-grained closure, a
self-organised process, and a molecular mechanism. This module supplies a
conforming handler for each of the eight draft signatures so ``compile_composite``
turns the whole three-by-three stack into running dynamics.

String-valued ports (``template``/``polymer`` typed ``sequence``) are declared for
conformance but carry no numeric dynamics — the molecular-grain template processes
are structural. The composite still evolves through the seven numeric handlers.

Handlers auto-registered at ``local:<ClassName>`` by build_core; ports declared
config-independently for pre-instantiation conformance.
"""
from __future__ import annotations

from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


# ── metabolism · three grains ─────────────────────────────────────────────────
class MetabolismClosureODE(Process):
    """Coarse grain: lumped nutrient→metabolite yield with entropy production.
    metabolites = yield · nutrients ; entropy = entropy_rate · nutrients."""
    config_schema = {"metabolite_yield": _f(0.6), "entropy_rate": _f(0.1)}

    def inputs(self):
        return {"nutrients": "chemical_flux", "energy": "energy"}

    def outputs(self):
        return {"metabolites": "concentration", "entropy": "entropy"}

    def update(self, state, interval):
        n = float(state.get("nutrients", 0.0))
        c = self.config
        return {"metabolites": c["metabolite_yield"] * n * interval,
                "entropy": c["entropy_rate"] * n * interval}


class AutocatalysisODE(Process):
    """Self-organised grain: an autocatalytic cycle producing product and catalyst
    from substrate. products = k · substrates ; catalysts = k_cat · substrates."""
    config_schema = {"k": _f(0.3), "k_cat": _f(0.15)}

    def inputs(self):
        return {"substrates": "concentration"}

    def outputs(self):
        return {"products": "concentration", "catalysts": "concentration"}

    def update(self, state, interval):
        s = float(state.get("substrates", 0.0))
        return {"products": self.config["k"] * s * interval,
                "catalysts": self.config["k_cat"] * s * interval}


# ── containment · three grains ────────────────────────────────────────────────
class ContainmentClosureODE(Process):
    """Coarse grain: membrane boundary area accretes from the lipid pool, and the
    permeability level saturates with available lipid (set-semantics)."""
    config_schema = {"assembly_rate": _f(0.15), "perm_max": _f(0.8), "perm_km": _f(1.0)}

    def inputs(self):
        return {"lipids": "concentration"}

    def outputs(self):
        return {"boundary": "area", "permeability": "fraction"}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._last_perm = 0.0

    def update(self, state, interval):
        lip = float(state.get("lipids", 0.0))
        c = self.config
        perm = c["perm_max"] * lip / (c["perm_km"] + lip) if (c["perm_km"] + lip) else 0.0
        d_perm = perm - self._last_perm
        self._last_perm = perm
        return {"boundary": c["assembly_rate"] * lip * interval, "permeability": d_perm}


class MembraneSelfAssemblyODE(Process):
    """Self-organised grain: membrane area self-assembles first-order in lipid."""
    config_schema = {"k": _f(0.2)}

    def inputs(self):
        return {"lipids": "concentration"}

    def outputs(self):
        return {"membrane": "area"}

    def update(self, state, interval):
        return {"membrane": self.config["k"] * float(state.get("lipids", 0.0)) * interval}


class LipidAggregationODE(Process):
    """Molecular grain: lipid monomers aggregate into micelle/bilayer counts."""
    config_schema = {"k": _f(0.1)}

    def inputs(self):
        return {"lipid_monomers": "concentration"}

    def outputs(self):
        return {"aggregate": "count"}

    def update(self, state, interval):
        return {"aggregate": self.config["k"] * float(state.get("lipid_monomers", 0.0)) * interval}


# ── replication · three grains ────────────────────────────────────────────────
class ReplicationClosureODE(Process):
    """Coarse grain: template-directed copying driven by free energy. copies =
    k · energy ; the template is conserved (declared, not rewritten)."""
    config_schema = {"k": _f(0.2)}

    def inputs(self):
        return {"template": "sequence", "energy": "energy"}

    def outputs(self):
        return {"template": "sequence", "copies": "count"}

    def update(self, state, interval):
        return {"copies": self.config["k"] * float(state.get("energy", 0.0)) * interval}


class TemplateReplicationODE(Process):
    """Self-organised grain: constant-rate copying while the template is present."""
    config_schema = {"k": _f(0.15)}

    def inputs(self):
        return {"template": "sequence"}

    def outputs(self):
        return {"copies": "count"}

    def update(self, state, interval):
        return {"copies": self.config["k"] * interval}


class TemplateDirectedSynthesisProc(Process):
    """Molecular grain: monomers polymerise on a template into a (string) polymer.
    The polymer product is structural (a sequence), so this handler has no numeric
    output — it is the deliberately-inert molecular grain; the composite evolves
    through the other seven handlers."""
    config_schema = {}

    def inputs(self):
        return {"monomers": "concentration", "template": "sequence"}

    def outputs(self):
        return {"polymer": "sequence"}

    def update(self, state, interval):
        return {}


# ── handler environment ⟦Fig9a⟧_H ─────────────────────────────────────────────
ENV = {
    "MetabolismClosure": {"handler": "MetabolismClosureODE",
                          "config": {"metabolite_yield": 0.6, "entropy_rate": 0.1},
                          "init": {"metabolism_coarse.nutrients": 1.0,
                                   "metabolism_coarse.energy": 1.0}},
    "Autocatalysis": {"handler": "AutocatalysisODE", "config": {"k": 0.3, "k_cat": 0.15},
                      "init": {"metabolism_selforg.substrates": 1.0}},
    "ContainmentClosure": {"handler": "ContainmentClosureODE",
                           "config": {"assembly_rate": 0.15, "perm_max": 0.8, "perm_km": 1.0},
                           "init": {"containment_coarse.lipids": 1.0}},
    "MembraneSelfAssembly": {"handler": "MembraneSelfAssemblyODE", "config": {"k": 0.2},
                             "init": {"containment_selforg.lipids": 1.0}},
    "LipidAggregation": {"handler": "LipidAggregationODE", "config": {"k": 0.1},
                         "init": {"containment_molecular.lipid_monomers": 1.0}},
    "ReplicationClosure": {"handler": "ReplicationClosureODE", "config": {"k": 0.2},
                           "init": {"replication_coarse.energy": 1.0}},
    "TemplateReplication": {"handler": "TemplateReplicationODE", "config": {"k": 0.15}},
    "TemplateDirectedSynthesis": {"handler": "TemplateDirectedSynthesisProc", "config": {},
                                  "init": {"replication_molecular.monomers": 1.0}},
}
