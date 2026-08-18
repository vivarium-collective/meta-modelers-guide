"""Toy-real handlers for Fig 9b — the minimal cell composition.

Executable ``Process`` implementations of the six draft-process effect
signatures wired in ``composites/fig09b-minimal-cell.composite.json``. Each
handler exposes the EXACT draft port names (so the semantic composite's wiring
transfers verbatim under :func:`compile_composite`) and has a genuine ``update``
built from coupled ODE / mass-action dynamics — no fabricated constants, every
rate lives in ``config_schema``.

The six handlers form a mutually-producing cell: gene expression makes the
enzymes metabolism needs and the proteins the cell is built from; metabolism
makes the energy replication spends and the metabolites everything draws on;
replication grows the gene pool (spending energy) and returns nucleic-acid
building blocks; reactions interconvert building blocks (amino acids +
nucleic acids → proteins, turning over the nucleic-acid pool); containment
assembles membrane area from lipids; diffusion turns the metabolite pool over.
Because they share component stores, no process runs alone — enzymes start at
zero and must be MADE by expression before metabolism can flux, which is the
minimal expression of autopoietic closure.

Handlers are auto-registered at ``local:<ClassName>`` by ``build_core`` (this is
a top-level module). Ports are declared config-independently so conformance can
be checked before instantiation. Mirrors ``handlers.py`` (the Fig 6 exemplar).
"""
from __future__ import annotations

from process_bigraph import Process


def _f(default):  # a float config field
    return {"_type": "float", "_default": default}


# ── containment · lipids → membrane ──────────────────────────────────────────
# signature MinimalCellContainment: in {lipids: concentration} out {membrane: area}
class ContainmentODE(Process):
    """Assemble membrane area from the lipid pool: dA/dt = k · lipids. Lipids act
    as the supply driver (held by the environment), so membrane area grows first
    order in available lipid concentration."""
    config_schema = {"assembly_rate": _f(0.15)}

    def inputs(self):
        return {"lipids": "concentration"}

    def outputs(self):
        return {"membrane": "area"}

    def update(self, state, interval):
        lipids = float(state.get("lipids", 0.0))
        return {"membrane": self.config["assembly_rate"] * lipids * interval}


# ── metabolism · enzymes + nutrients → metabolites + energy ──────────────────
# signature MinimalCellMetabolism:
#   in {enzymes: concentration, nutrients: concentration}
#   out {metabolites: concentration, energy: energy}
class MetabolismLinear(Process):
    """Enzyme-catalysed conversion of nutrients into metabolites and free energy.
    Flux = k · enzymes · nutrients (enzymes catalytic, not consumed); metabolites
    and energy are produced at fixed yields on that flux. Enzymes start at zero,
    so metabolism only fluxes once gene expression has made some — the coupling
    that makes the cell mutually dependent."""
    config_schema = {
        "k_cat": _f(0.2),
        "metabolite_yield": _f(0.6),
        "energy_yield": _f(0.4),
    }

    def inputs(self):
        return {"enzymes": "concentration", "nutrients": "concentration"}

    def outputs(self):
        return {"metabolites": "concentration", "energy": "energy"}

    def update(self, state, interval):
        enzymes = float(state.get("enzymes", 0.0))
        nutrients = float(state.get("nutrients", 0.0))
        c = self.config
        flux = c["k_cat"] * enzymes * nutrients
        return {
            "metabolites": c["metabolite_yield"] * flux * interval,
            "energy": c["energy_yield"] * flux * interval,
        }


# ── gene expression · genes + amino_acids → proteins + enzymes ───────────────
# signature GeneExpression:
#   in {genes: concentration, amino_acids: concentration}
#   out {proteins: concentration, enzymes: concentration}
class GeneExpressionODE(Process):
    """Translate the gene template, drawing on amino-acid building blocks, into
    proteins and enzymes: rate = k · genes · amino_acids, split into a protein
    and an enzyme yield. This is the sole source of the enzyme pool metabolism
    reads, and of the protein pool."""
    config_schema = {
        "k_expr": _f(0.25),
        "protein_yield": _f(0.5),
        "enzyme_yield": _f(0.3),
    }

    def inputs(self):
        return {"genes": "concentration", "amino_acids": "concentration"}

    def outputs(self):
        return {"proteins": "concentration", "enzymes": "concentration"}

    def update(self, state, interval):
        genes = float(state.get("genes", 0.0))
        amino_acids = float(state.get("amino_acids", 0.0))
        c = self.config
        rate = c["k_expr"] * genes * amino_acids
        return {
            "proteins": c["protein_yield"] * rate * interval,
            "enzymes": c["enzyme_yield"] * rate * interval,
        }


# ── replication · genes + energy → genes + nucleic_acids ─────────────────────
# signature MinimalCellReplication:
#   in {genes: concentration, energy: energy}
#   out {genes: concentration, nucleic_acids: concentration}
class ReplicationODE(Process):
    """Copy the gene pool by spending free energy: rate = k · genes · energy.
    Gene copies are added back to the gene store (autocatalytic growth) and
    nucleic-acid building blocks are returned as a byproduct of copying. Energy
    is the driver supplied by metabolism."""
    config_schema = {
        "k_rep": _f(0.1),
        "gene_yield": _f(0.5),
        "nucleic_yield": _f(0.4),
    }

    def inputs(self):
        return {"genes": "concentration", "energy": "energy"}

    def outputs(self):
        return {"genes": "concentration", "nucleic_acids": "concentration"}

    def update(self, state, interval):
        genes = float(state.get("genes", 0.0))
        energy = float(state.get("energy", 0.0))
        c = self.config
        rate = c["k_rep"] * genes * energy
        return {
            "genes": c["gene_yield"] * rate * interval,
            "nucleic_acids": c["nucleic_yield"] * rate * interval,
        }


# ── diffusion · metabolites → metabolites ────────────────────────────────────
# signature Diffusion: in {metabolites: concentration} out {metabolites: concentration}
class DiffusionRelax(Process):
    """Diffusion over a SINGLE lumped metabolite store cannot relax to a spatial
    mean (there is no neighbouring cell to exchange with), so this handler stands
    in for transport loss with a mild first-order turnover:
    d[metabolites]/dt = -d · metabolites. It removes metabolites at a rate
    proportional to their concentration, opposing metabolism's production so the
    shared pool reaches a moving balance rather than growing without bound."""
    config_schema = {"turnover_rate": _f(0.05)}

    def inputs(self):
        return {"metabolites": "concentration"}

    def outputs(self):
        return {"metabolites": "concentration"}

    def update(self, state, interval):
        metabolites = float(state.get("metabolites", 0.0))
        return {"metabolites": -self.config["turnover_rate"] * metabolites * interval}


# ── reactions · amino_acids + nucleic_acids → proteins + nucleic_acids ────────
# signature Reactions:
#   in {amino_acids: concentration, nucleic_acids: concentration}
#   out {proteins: concentration, nucleic_acids: concentration}
class MassActionReactions(Process):
    """Generic mass-action interconversion of building blocks: reaction rate
    r = k · amino_acids · nucleic_acids assembles proteins (protein_yield · r)
    and turns over the nucleic-acid pool (consumes nucleic_turnover · r of it).
    Replication feeds nucleic acids in; these reactions draw them back down —
    the interconversion loop that keeps the building-block stores balanced."""
    config_schema = {
        "k_react": _f(0.15),
        "protein_yield": _f(0.4),
        "nucleic_turnover": _f(0.2),
    }

    def inputs(self):
        return {"amino_acids": "concentration", "nucleic_acids": "concentration"}

    def outputs(self):
        return {"proteins": "concentration", "nucleic_acids": "concentration"}

    def update(self, state, interval):
        amino_acids = float(state.get("amino_acids", 0.0))
        nucleic_acids = float(state.get("nucleic_acids", 0.0))
        c = self.config
        r = c["k_react"] * amino_acids * nucleic_acids
        return {
            "proteins": c["protein_yield"] * r * interval,
            "nucleic_acids": -c["nucleic_turnover"] * r * interval,
        }


# ── handler environment ⟦fig09b⟧_H ───────────────────────────────────────────
# Assigns each draft signature a handler + rate config, and supplies the driver
# pools as initial store values so the cell actually evolves. NOTE the compiler's
# ``init`` sets a leaf's ``_default`` (realize IGNORES ``_value``), and it MERGES
# every entry's ``init`` across the env — so the drivers below all take effect
# even though they are declared on a single entry.
ENV: dict[str, dict] = {
    "MinimalCellContainment": {
        "handler": "ContainmentODE",
        "config": {"assembly_rate": 0.15},
        "init": {
            # driver pools (env-supplied); products start at 0 and must be MADE
            "nutrients.concentration": 1.0,
            "genes.concentration": 1.0,
            "lipids.concentration": 1.0,
            "amino_acids.concentration": 1.0,
            "energy.energy": 1.0,
        },
    },
    "MinimalCellMetabolism": {
        "handler": "MetabolismLinear",
        "config": {"k_cat": 0.2, "metabolite_yield": 0.6, "energy_yield": 0.4},
    },
    "GeneExpression": {
        "handler": "GeneExpressionODE",
        "config": {"k_expr": 0.25, "protein_yield": 0.5, "enzyme_yield": 0.3},
    },
    "MinimalCellReplication": {
        "handler": "ReplicationODE",
        "config": {"k_rep": 0.1, "gene_yield": 0.5, "nucleic_yield": 0.4},
    },
    "Diffusion": {
        "handler": "DiffusionRelax",
        "config": {"turnover_rate": 0.05},
    },
    "Reactions": {
        "handler": "MassActionReactions",
        "config": {"k_react": 0.15, "protein_yield": 0.4, "nucleic_turnover": 0.2},
    },
}
