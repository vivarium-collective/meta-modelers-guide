"""Fig 7 · nested cellular hierarchy — a *mechanistic* variant where the nesting
INFLUENCES FUNCTION, not just routes a scalar.

The baseline (handlers_fig07) runs a gene-expression cascade through a deep place
graph, but — as the scientific review notes — a deep scalar changing establishes
nested ROUTING, not multilevel biological ORGANIZATION. This variant adds the
thing that makes hierarchy functional: COMPARTMENT BOUNDARIES whose PERMEABILITY
gates cross-compartment flux, so a boundary-level knob causally controls a deep
observable.

Three kinds of hierarchical relation are made explicit and distinct:
  * CONTAINMENT — environment ⊃ cell ⊃ cytoplasm ⊃ nucleus (the place-graph nesting).
  * PART-OF / ASSEMBLY — each ``PermeableBoundary`` is the boundary that DEFINES a
    compartment (the membrane is part of the cell; the envelope is part of the
    nucleus); it is not a contained thing but the interface of one.
  * REGULATORY DEPENDENCE — the nuclear reporter's production DEPENDS ON the signal
    that reaches it (a functional edge, not a containment edge).

What hierarchy DEPTH means here, biologically: the number of permeability barriers
a signal must cross to reach a process. The nuclear reporter sits behind TWO
boundaries (membrane, then nuclear envelope), so it is gated TWICE — each boundary
independently (series resistances).

Mechanism:
  * ``PermeableBoundary`` — passive transport across a boundary,
    J = permeability·(c_outer − c_inner)·interval, subtracted from the outer store
    and added to the inner store (CONSERVATIVE by construction). Two instances: the
    plasma membrane (environment↔cytoplasm) and the nuclear envelope
    (cytoplasm↔nucleus).
  * ``LocalMetabolism`` — a LOCALLY-RESTRICTED first-order consumption of substrate
    that acts only in the cytoplasm (so the compartments do different things).
  * ``RegulatedReporter`` — in the nucleus, substrate catalytically drives reporter
    production with turnover (dR = k_prod·substrate − k_deg·R): a regulatory
    dependence, substrate not consumed.

Because the nuclear substrate (and hence the reporter) depends on BOTH permeabilities
in series, lowering EITHER boundary's permeability shuts the deep reporter down —
a boundary-level cause with a deep functional effect. All classes auto-register at
``local:<ClassName>`` via build_core.
"""
from __future__ import annotations

from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


class PermeableBoundary(Process):
    """Passive, CONSERVATIVE transport across a compartment boundary:
    J = permeability·(outer − inner)·interval, removed from the outer store and
    added to the inner store. Permeability is the real knob — raise it and the
    inner compartment fills faster; set it to ~0 (epsilon) and the boundary
    isolates the compartment. Nothing is created: whatever leaves the outer enters
    the inner."""
    config_schema = {"permeability": _f(0.3)}

    def inputs(self):
        return {"outer": "concentration", "inner": "concentration"}

    def outputs(self):
        return {"outer": "concentration", "inner": "concentration"}

    def update(self, state, interval):
        outer = float(state.get("outer", 0.0))
        inner = float(state.get("inner", 0.0))
        j = self.config["permeability"] * (outer - inner) * interval
        return {"outer": -j, "inner": j}


class LocalMetabolism(Process):
    """A LOCALLY-RESTRICTED first-order consumption of substrate — it acts only on
    the compartment it is wired to (the cytoplasm), so compartments are functionally
    distinct (cytoplasm metabolises; nucleus reports). dS = −k·S·interval."""
    config_schema = {"k": _f(0.05)}

    def inputs(self):
        return {"substrate": "concentration"}

    def outputs(self):
        return {"substrate": "concentration"}

    def update(self, state, interval):
        s = float(state.get("substrate", 0.0))
        return {"substrate": -self.config["k"] * s * interval}


class RegulatedReporter(Process):
    """The deep (nuclear) observable: substrate catalytically drives reporter
    production with first-order turnover — a REGULATORY dependence (substrate is not
    consumed). dR = (k_prod·substrate − k_deg·R)·interval, so at steady state
    R ∝ nuclear substrate — which is itself gated by the two boundaries upstream.
    Reporter is written only here, so its total is self-tracked to apply turnover
    without a new input port."""
    config_schema = {"k_prod": _f(0.4), "k_deg": _f(0.1)}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._r = 0.0

    def inputs(self):
        return {"substrate": "concentration"}

    def outputs(self):
        return {"reporter": "concentration"}

    def update(self, state, interval):
        s = float(state.get("substrate", 0.0))
        c = self.config
        d_r = (c["k_prod"] * s - c["k_deg"] * self._r) * interval
        self._r += d_r
        return {"reporter": d_r}
