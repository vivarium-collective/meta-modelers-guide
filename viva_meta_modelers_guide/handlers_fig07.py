"""Fig 7 · molecular mechanism — an executable handler for the ``MolecularMechanism``
draft signature.

The Fig 7 draft is a single molecular process that couples the four physical
interaction channels of a molecule — chemical, electrical, mechanical, thermal —
plus a (string) ``structure`` identifier, transforming input channels into output
channels (Fig 7b). This handler realises it as an enzyme-like mechanism: it turns
over the incoming chemical flux into product flux, dissipates part of the reaction
as heat, and passes the electrical and mechanical channels through linear
(Ohmic / elastic) responses. Every constant lives in ``config``.

The four output channels are instantaneous *fluxes*, so they are written with
"set" semantics (each ``update`` returns the delta carrying the additive store to
the freshly-computed rate). ``structure`` is a read-only string identifier
(PDB/SMILES) and does not enter the dynamics.

Handler auto-registered at ``local:MolecularMechanismHandler`` by build_core; ports
are declared config-independently so conformance is checkable before instantiation.
Mirrors handlers_fig04b.py (the set-semantics exemplar).
"""
from __future__ import annotations

from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


class MolecularMechanismHandler(Process):
    """A molecular mechanism as a channel transducer: chemical turnover with heat
    dissipation, plus Ohmic (electrical) and elastic (mechanical) pass-through."""

    config_schema = {
        "catalysis": _f(0.6),       # product flux produced per unit chemical influx
        "dissipation": _f(0.2),     # heat flux released per unit chemical influx
        "conductance": _f(0.3),     # electrical output per unit electrical input
        "coupling": _f(0.4),        # mechanical output per unit mechanical input
    }

    def inputs(self):
        return {"chemical_in": "chemical_flux", "electrical_in": "current",
                "mechanical_in": "force", "thermal_in": "heat_flux",
                "structure": "structure"}

    def outputs(self):
        return {"chemical_out": "chemical_flux", "electrical_out": "current",
                "mechanical_out": "force", "thermal_out": "heat_flux"}

    def _set(self, port, value):
        if not hasattr(self, "_last"):
            self._last = {}
        delta = value - self._last.get(port, 0.0)
        self._last[port] = value
        return delta

    def update(self, state, interval):
        c = self.config
        chem = float(state.get("chemical_in", 0.0))
        elec = float(state.get("electrical_in", 0.0))
        mech = float(state.get("mechanical_in", 0.0))
        therm = float(state.get("thermal_in", 0.0))
        return {
            "chemical_out": self._set("chemical_out", c["catalysis"] * chem),
            "thermal_out": self._set("thermal_out", c["dissipation"] * chem + therm),
            "electrical_out": self._set("electrical_out", c["conductance"] * elec),
            "mechanical_out": self._set("mechanical_out", c["coupling"] * mech),
        }


# ── handler environment ⟦Fig7⟧_H ──────────────────────────────────────────────
# init seeds the four numeric input channels (the ``structure`` string leaf is
# left as-is). init sets a leaf's ``_default`` (realize ignores ``_value``).
ENV = {
    "MolecularMechanism": {
        "handler": "MolecularMechanismHandler",
        "config": {"catalysis": 0.6, "dissipation": 0.2,
                   "conductance": 0.3, "coupling": 0.4},
        "init": {
            "ports.chemical_in": 1.0,
            "ports.electrical_in": 1.0,
            "ports.mechanical_in": 1.0,
            "ports.thermal_in": 0.5,
        },
    },
}
