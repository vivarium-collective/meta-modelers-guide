"""Fig 1 · interfaces & composition — a *mechanistic* reusable transport.

This is the real-mechanism upgrade of ``fig01_demo`` (the one-shot irreversible
``StoreTransfer``, kept as the didactic baseline). It makes the paper's actual
point about composition concrete: ONE reusable process class, wired differently,
gives different dynamics — the topology lives in the WIRING, not in the code.

``CompartmentTransport`` is a REVERSIBLE, first-order, typed transport across a
membrane between two compartments::

    d(source)/dt = -(k_f·source - k_r·sink)
    d(sink)/dt   = +(k_f·source - k_r·sink)

so it conserves ``source + sink`` and relaxes to the equilibrium
``sink/source = k_f/k_r`` (the baseline's irreversible decay is the k_r→0 limit).
The ports are typed ``concentration`` (a named float carrying mol·L⁻¹), so wiring
one to an incompatible store (e.g. a structural string) is a type error the engine
rejects — the negative type-compatibility control.

The SAME class is instantiated on every edge of a THREE-compartment, genuinely
NESTED place graph (cell ▸ outer; cell ▸ inner ▸ B; cell ▸ inner ▸ organelle ▸ C).
Two composites reuse it under different topologies — a linear chain (A↔B↔C) and a
hub/star (A↔B, A↔C) — without touching the process implementation. Conservation of
A+B+C holds in both; the equilibrium distribution differs because the topology does.

Auto-registered at ``local:<ClassName>`` by build_core.
"""
from __future__ import annotations

from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


class CompartmentTransport(Process):
    """A reusable, reversible, typed membrane transport between two compartments.
    Conserves source+sink; equilibrium sink/source = k_forward/k_reverse. Instantiate
    it on any edge — the topology is set by how its ports are WIRED, not by its code."""

    config_schema = {"k_forward": _f(0.2), "k_reverse": _f(0.05)}

    def inputs(self):
        return {"source": "concentration", "sink": "concentration"}

    def outputs(self):
        return {"source": "concentration", "sink": "concentration"}

    def update(self, state, interval):
        s = float(state["source"])
        d = float(state["sink"])
        net = (self.config["k_forward"] * s - self.config["k_reverse"] * d) * interval
        return {"source": -net, "sink": +net}
