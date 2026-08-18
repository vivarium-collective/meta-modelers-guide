"""Fig 10 · growth → division, development, evolution — executable handlers,
including the atlas's first **event-driven rewrite** handlers.

Fig 10 is where composition stops being a static handler swap. Division partitions
one cell into two (Fig 10b); development embeds cells in a biofilm (Fig 10d);
evolution adds a port (Fig 10f). These are the paper's event-driven graph rewrites
(Fig 3c: divide / engulf / burst).

Most Fig 10 drafts still conform normally — their signatures match their wiring —
so they are ordinary handlers that animate the (pre-declared) daughter/biofilm/
variant subtrees. The one genuine rewrite is :class:`DivisionRewrite`: its draft
signature (``trigger``) is a placeholder, while the composite wires it as
``biomass ⇒ biomass_1, biomass_2, cell_count``. It is marked ``REWRITE = True`` so
the compiler checks its conformance against the *wiring* (law 2′, see compile.py),
and it fires a **discrete division event** at a configured cell-cycle time —
run-to-completion in each step, but a genuine event over the run: the parent's
biomass is partitioned into two daughters and the cell count increments.

Handlers auto-registered at ``local:<ClassName>`` by build_core; ports declared
config-independently. The pre-declared post-structure means ``interface_of`` is
unchanged (law 2 still holds); true runtime node-insertion is a further extension.
"""
from __future__ import annotations

from process_bigraph import Process

from viva_compiler import RewriteHandler  # marker base: conformance vs. wiring (law 2′)


def _f(default):
    return {"_type": "float", "_default": default}


# ── Fig 10-1 · division ───────────────────────────────────────────────────────
class DNAReplicationODE(Process):
    """Autocatalytic DNA replication driven by free energy: d[dna]/dt = k·dna·energy."""
    config_schema = {"k": _f(0.15)}

    def inputs(self):
        return {"dna": "concentration", "energy": "energy"}

    def outputs(self):
        return {"dna": "concentration"}

    def update(self, state, interval):
        dna = float(state.get("dna", 0.0))
        energy = float(state.get("energy", 0.0))
        return {"dna": self.config["k"] * dna * energy * interval}


class SegregateChromosomeProc(Process):
    """Segregate replicated DNA toward the two daughter poles: each daughter's DNA
    accretes a fraction of the parent's DNA per step (dna_1 = dna_2 = seg·dna)."""
    config_schema = {"seg_rate": _f(0.2)}

    def inputs(self):
        return {"dna": "concentration"}

    def outputs(self):
        return {"dna_1": "concentration", "dna_2": "concentration"}

    def update(self, state, interval):
        dna = float(state.get("dna", 0.0))
        s = self.config["seg_rate"] * dna * interval
        return {"dna_1": s, "dna_2": s}


class DivisionRewrite(RewriteHandler):
    """Event-driven division TRIGGERED BY DNA REPLICATION. The cell divides ONCE,
    when its replicated ``dna`` crosses ``dna_threshold`` — not on a wall clock —
    so the event is gated by the cell's own state (``ReplicationProc`` grows
    ``dna``; segregation crosses the threshold; the rewrite fires). At the event
    the parent's biomass is PARTITIONED equally into the two daughters: the parent
    node's biomass is driven to 0 and each daughter receives M/2, so mass is
    conserved (one cell node → two daughter nodes). A discrete structural rewrite
    realised over the run; conformance checked against the wiring (``REWRITE``)."""
    config_schema = {"dna_threshold": _f(2.0)}

    def inputs(self):
        return {"biomass": "mass", "dna": "concentration"}

    def outputs(self):
        # `biomass` writes back to the PARENT (→ 0); the daughters receive the halves.
        return {"biomass": "mass", "biomass_1": "mass", "biomass_2": "mass",
                "cell_count": "cell_count"}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._divided = False

    def update(self, state, interval):
        if self._divided or float(state.get("dna", 0.0)) < self.config["dna_threshold"]:
            return {}
        self._divided = True
        biomass = float(state.get("biomass", 0.0))
        half = biomass / 2.0
        # 1 node → 2 nodes: parent fully partitions, each daughter gets M/2. Conserved.
        return {"biomass": -biomass, "biomass_1": half, "biomass_2": half, "cell_count": 1.0}


# ── Fig 10-2 · development (biofilm) ──────────────────────────────────────────
class SurfaceAttachmentProc(Process):
    """Cells attach to the surface (saturating in surface area) and build adhesion
    force proportional to the attached population."""
    config_schema = {"attach_rate": _f(0.15), "adhesion_coef": _f(0.5)}

    def inputs(self):
        return {"cells": "cell_count", "surface": "area"}

    def outputs(self):
        return {"attached": "cell_count", "adhesion": "force"}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._attached = 0.0
        self._last_adhesion = 0.0

    def update(self, state, interval):
        cells = float(state.get("cells", 0.0))
        surface = float(state.get("surface", 0.0))
        c = self.config
        d_attached = c["attach_rate"] * cells * surface * interval
        self._attached += d_attached
        adhesion = c["adhesion_coef"] * self._attached
        d_adhesion = adhesion - self._last_adhesion
        self._last_adhesion = adhesion
        return {"attached": d_attached, "adhesion": d_adhesion}


class ECMSecretionProc(Process):
    """Attached cells secrete extracellular matrix: d[ecm]/dt = k·cells·metabolites."""
    config_schema = {"k": _f(0.2)}

    def inputs(self):
        return {"cells": "cell_count", "metabolites": "concentration"}

    def outputs(self):
        return {"ecm": "concentration"}

    def update(self, state, interval):
        cells = float(state.get("cells", 0.0))
        met = float(state.get("metabolites", 0.0))
        return {"ecm": self.config["k"] * cells * met * interval}


class BiofilmGrowthProc(Process):
    """Biofilm mass grows on nutrients, and the ECM-embedded population expands:
    d[mass]/dt = k·cells·nutrients ; d[cells]/dt = g·cells·ecm."""
    config_schema = {"mass_rate": _f(0.25), "growth_rate": _f(0.08)}

    def inputs(self):
        return {"cells": "cell_count", "ecm": "concentration", "nutrients": "concentration"}

    def outputs(self):
        return {"biofilm_mass": "mass", "cells": "cell_count"}

    def update(self, state, interval):
        cells = float(state.get("cells", 0.0))
        ecm = float(state.get("ecm", 0.0))
        nut = float(state.get("nutrients", 0.0))
        c = self.config
        return {"biofilm_mass": c["mass_rate"] * cells * nut * interval,
                "cells": c["growth_rate"] * cells * ecm * interval}


# ── Fig 10-3 · evolution ──────────────────────────────────────────────────────
class VariationProc(Process):
    """Genomic variation is structural (sequence/identity strings), so this handler
    has no numeric output — the variation is realised as the new identity in the
    variant compartment; the composite evolves through selection + port addition."""
    config_schema = {}

    def inputs(self):
        return {"genome": "sequence"}

    def outputs(self):
        return {"genome": "sequence", "variant": "identity"}

    def update(self, state, interval):
        return {}


class SelectionProc(Process):
    """Selection expands the population by viability-weighted fitness:
    d[cell_count]/dt = k·viability·fitness."""
    config_schema = {"k": _f(0.3)}

    def inputs(self):
        return {"viability": "viability", "fitness": "objective"}

    def outputs(self):
        return {"cell_count": "cell_count"}

    def update(self, state, interval):
        v = float(state.get("viability", 0.0))
        f = float(state.get("fitness", 0.0))
        return {"cell_count": self.config["k"] * v * f * interval}


class PortAdditionProc(Process):
    """Evolution adds a new interface capability: a previously-silent chemical
    exchange port turns on and ramps to its capacity flux. The new port going from
    zero to nonzero is the executable signature of 'a new port is added' (Fig 10f)."""
    config_schema = {"onset_rate": _f(0.1), "capacity": _f(1.0)}

    def inputs(self):
        return {"genome": "sequence"}

    def outputs(self):
        return {"new_port": "chemical_flux", "identity": "identity"}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._flux = 0.0

    def update(self, state, interval):
        c = self.config
        # first-order ramp toward capacity (the port "switches on")
        d = c["onset_rate"] * (c["capacity"] - self._flux) * interval
        self._flux += d
        return {"new_port": d}


# ── handler environments ⟦Fig10-1/2/3⟧_H ──────────────────────────────────────
ENV_DIVISION = {
    "DNAReplication": {"handler": "DNAReplicationODE", "config": {"k": 0.15},
                       "init": {"environ.cell.dna": 1.0, "environ.cell.energy": 1.0}},
    "SegregateChromosome": {"handler": "SegregateChromosomeProc", "config": {"seg_rate": 0.2}},
    "Divide": {"handler": "DivisionRewrite", "config": {"dna_threshold": 2.0},
               "init": {"environ.cell.biomass": 1.0, "environ.cell_count": 1.0}},
}

ENV_DEVELOPMENT = {
    "SurfaceAttachment": {"handler": "SurfaceAttachmentProc",
                          "config": {"attach_rate": 0.15, "adhesion_coef": 0.5},
                          "init": {"environ.biofilm.cells": 1.0,
                                   "environ.biofilm.surface": 1.0,
                                   "environ.biofilm.metabolites": 1.0,
                                   "environ.biofilm.nutrients": 1.0}},
    "ECMSecretion": {"handler": "ECMSecretionProc", "config": {"k": 0.2}},
    "BiofilmGrowth": {"handler": "BiofilmGrowthProc",
                      "config": {"mass_rate": 0.25, "growth_rate": 0.08}},
}

ENV_EVOLUTION = {
    "Variation": {"handler": "VariationProc", "config": {}},
    "Selection": {"handler": "SelectionProc", "config": {"k": 0.3},
                  "init": {"environ.cell_ecoli.viability": 1.0,
                           "environ.cell_ecoli.fitness": 1.0,
                           "environ.cell_ecoli.cell_count": 1.0}},
    "PortAddition": {"handler": "PortAdditionProc", "config": {"onset_rate": 0.1, "capacity": 1.0}},
}
