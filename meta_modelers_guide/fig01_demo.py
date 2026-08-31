"""Fig 1 · what a process bigraph IS — a MINIMAL executable demonstration.

Fig 1 is the definitional figure: a *process bigraph* is Milner's place graph
(a nesting of stores/nodes) with **processes** wired to those nodes through
typed ports, replacing the link graph's hyperedges. The published Fig 1b draws
that structure statically (nodes ``n1..n6`` + draft ``BigraphLink`` processes p1,
p2, p3 — signatures with no dynamics).

This module supplies the smallest honest bit of *dynamics* behind that picture:
a single real process wired to two scalar stores. Running it shows the claim the
figure makes — a process bigraph is an **executable** place-graph-plus-processes:
give a process an update rule and the wired stores evolve over time.

``StoreTransfer`` is a first-order (mass-action) transfer from a source store to
a sink store::

    dA/dt = -k·A       dB/dt = +k·A

so source ``A`` decays exponentially, sink ``B`` fills, and the total ``A+B`` is
conserved to round-off. That is a complete, if tiny, process bigraph: two
place-graph nodes (the stores) and one process connecting them through an ``in``
port (reads ``A``) and two ``out`` ports (writes both), making the shared state
and the dependency between the two nodes explicit and — now — runnable.

Auto-registered at ``local:StoreTransfer`` by ``build_core`` (top-level module).
"""
from __future__ import annotations

from process_bigraph import Process


class StoreTransfer(Process):
    """First-order transfer of a scalar quantity from a source store to a sink
    store: ``dsource/dt = -k·source``, ``dsink/dt = +k·source`` (total conserved).

    The minimal executable process bigraph: one process wired to two place-graph
    nodes through typed ports. ``source`` is read and written (it drains);
    ``sink`` is written (it fills). With ``rate`` (k) > 0 the source decays
    exponentially into the sink while their sum stays fixed.
    """

    config_schema = {"rate": {"_type": "float", "_default": 0.15}}

    def inputs(self):
        return {"source": "float"}

    def outputs(self):
        return {"source": "float", "sink": "float"}

    def update(self, state, interval):
        flux = self.config["rate"] * float(state["source"]) * interval
        return {"source": -flux, "sink": +flux}
