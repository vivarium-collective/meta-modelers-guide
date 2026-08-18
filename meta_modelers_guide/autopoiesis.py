"""Fig 9 draft processes — self-organization, coarse-graining, and autopoiesis.

These are *draft* processes: typed, unit-bearing ports plus a **behavior**
contract that says what the process senses, affects, and must keep in bounds —
**without committing to a mechanism** (no rate law, no update dynamics). They
render in the bigraph as the three functional columns of autopoiesis described
at several grains (Fig 9a) or as the wired composition of a minimal cell
(Fig 9b), and are auto-registered at ``local:<ClassName>`` by ``build_core``.

Contract convention used throughout the guide:

* ``summary``     — one line: what the process is.
* ``behavior``    — what it does, described functionally (no equations).
* ``senses``      — the interface variables it reads.
* ``affects``     — the interface variables it writes / controls.
* ``constraints`` — conservation laws / viability bounds it must respect.
* ``ports``       — every port with its biological unit.

``grain`` names where a process sits on the coarse-graining ladder
(coarse-grained closure ⇄ self-organized ⇄ molecular) where the paper draws one.
"""
from __future__ import annotations

from process_bigraph import DraftProcess, draft_process


# ─────────────────────────────────────────────────────────────────────────────
# Fig 9a — Self-organized processes, coarse-graining, and autopoiesis.
# Three functional COLUMNS — metabolism, containment, replication — each drawn at
# several GRAINS. A coarse-grained *closure* process (top of a column) is exactly
# what you get when the finer self-organized / molecular processes below it are
# lumped. The mutual closure of the three columns — each producing and sustaining
# the conditions the others need — is autopoiesis.
# ─────────────────────────────────────────────────────────────────────────────

# ── metabolism column ────────────────────────────────────────────────────────
@draft_process(
    name="MetabolismClosure",
    inputs={"nutrients": "chemical_flux", "energy": "energy"},
    outputs={"metabolites": "concentration", "entropy": "entropy"},
    contract={
        "summary": "Metabolism closure — sustains chemical stores far from equilibrium.",
        "behavior": "The coarse-grained metabolic column: draws on nutrient flux and "
                    "free energy to keep the internal pool of metabolites stocked far "
                    "from thermodynamic equilibrium, dissipating entropy in the "
                    "process — without resolving the reactions that do it.",
        "senses": "incoming nutrient flux and available free energy.",
        "affects": "the internal metabolite pool and the entropy exported to the "
                   "surroundings.",
        "constraints": "mass and energy conserved across the lumped boundary; entropy "
                       "production ≥ 0 (second law); the pool is maintained only while "
                       "energy is supplied.",
        "grain": "coarse-grained closure — lumps the self-organized reaction set below.",
        "ports": {
            "nutrients": "nutrient uptake flux, into cell (mol·s⁻¹)",
            "energy": "free energy driving the pool from equilibrium (J)",
            "metabolites": "sustained internal metabolite pool (mol·L⁻¹)",
            "entropy": "entropy produced / exported (J·K⁻¹·s⁻¹)",
        },
    },
)
class MetabolismClosure(DraftProcess):
    pass


@draft_process(
    name="Autocatalysis",
    inputs={"substrates": "concentration"},
    outputs={"products": "concentration", "catalysts": "concentration"},
    contract={
        "summary": "Autocatalysis — a self-reinforcing reaction set.",
        "behavior": "The self-organized grain beneath metabolism closure: a reaction "
                    "set whose own products include the catalysts that accelerate it, "
                    "so the network reproduces its own catalytic machinery from "
                    "available substrates.",
        "senses": "the available substrate concentrations.",
        "affects": "product concentrations and the catalyst pool that feeds back on "
                   "the same reactions.",
        "constraints": "atoms conserved reaction by reaction; concentrations stay "
                       "non-negative; net production requires substrate supply.",
        "grain": "self-organized — lump its closed catalytic loop to get metabolism "
                 "closure.",
        "ports": {
            "substrates": "substrate concentrations consumed (mol·L⁻¹)",
            "products": "product concentrations formed (mol·L⁻¹)",
            "catalysts": "self-produced catalyst concentrations (mol·L⁻¹)",
        },
    },
)
class Autocatalysis(DraftProcess):
    pass


# ── containment column ───────────────────────────────────────────────────────
@draft_process(
    name="ContainmentClosure",
    inputs={"lipids": "concentration"},
    outputs={"boundary": "area", "permeability": "fraction"},
    contract={
        "summary": "Containment closure — maintains a boundary that defines inside/outside.",
        "behavior": "The coarse-grained containment column: consumes lipids to "
                    "maintain a boundary that constrains diffusion and separates an "
                    "inside from an outside, setting how selectively matter crosses — "
                    "without resolving how the boundary self-assembles.",
        "senses": "the available lipid concentration.",
        "affects": "the boundary area and its permeability.",
        "constraints": "boundary area ≥ 0 and bounded by lipid supply; permeability "
                       "in 0–1; the inside is defined only while the boundary holds.",
        "grain": "coarse-grained closure — lumps the self-assembly below.",
        "ports": {
            "lipids": "lipid concentration available (mol·L⁻¹)",
            "boundary": "maintained boundary area (m²)",
            "permeability": "boundary permeability, 0 = sealed, 1 = open (0–1)",
        },
    },
)
class ContainmentClosure(DraftProcess):
    pass


@draft_process(
    name="MembraneSelfAssembly",
    inputs={"lipids": "concentration"},
    outputs={"membrane": "area"},
    contract={
        "summary": "Membrane self-assembly — amphiphiles assemble into a bilayer.",
        "behavior": "The self-organized grain beneath containment closure: amphiphilic "
                    "lipids spontaneously assemble into a bilayer membrane, growing the "
                    "enclosing surface from a dispersed lipid pool.",
        "senses": "the lipid concentration available to assemble.",
        "affects": "the assembled membrane area.",
        "constraints": "membrane area bounded by lipid supply; assembly is favored "
                       "only above a critical amphiphile concentration.",
        "grain": "self-organized — lump the bilayer it forms to get containment closure.",
        "ports": {
            "lipids": "lipid concentration available (mol·L⁻¹)",
            "membrane": "assembled bilayer membrane area (m²)",
        },
    },
)
class MembraneSelfAssembly(DraftProcess):
    pass


@draft_process(
    name="LipidAggregation",
    inputs={"lipid_monomers": "concentration"},
    outputs={"aggregate": "count"},
    contract={
        "summary": "Lipid aggregation — lipid monomers aggregate.",
        "behavior": "The molecular grain beneath membrane self-assembly: individual "
                    "lipid monomers associate into micelles / aggregates, the "
                    "elementary clustering step from which a bilayer later assembles.",
        "senses": "the lipid-monomer concentration.",
        "affects": "the number of lipid aggregates formed.",
        "constraints": "monomers conserved (aggregation redistributes, does not "
                       "create matter); aggregate count ≥ 0.",
        "grain": "molecular — the elementary step under membrane self-assembly.",
        "ports": {
            "lipid_monomers": "free lipid-monomer concentration (mol·L⁻¹)",
            "aggregate": "number of lipid aggregates formed (molecules)",
        },
    },
)
class LipidAggregation(DraftProcess):
    pass


# ── replication column ───────────────────────────────────────────────────────
@draft_process(
    name="ReplicationClosure",
    inputs={"template": "sequence", "energy": "energy"},
    outputs={"template": "sequence", "copies": "count"},
    contract={
        "summary": "Replication closure — maintains and copies template information.",
        "behavior": "The coarse-grained replication column: uses free energy to "
                    "maintain a template's information and produce copies of it, "
                    "preserving the sequence across copying — without resolving how "
                    "the template is read and polymerized.",
        "senses": "the template sequence and the available free energy.",
        "affects": "the maintained template sequence and the number of copies made.",
        "constraints": "information is preserved (copies match the template up to "
                       "error); copying is bounded by energy supply; copies ≥ 0.",
        "grain": "coarse-grained closure — lumps template-directed synthesis below.",
        "ports": {
            "template": "information-bearing template sequence (nt/aa string)",
            "energy": "free energy driving copying (J)",
            "copies": "number of template copies produced (molecules)",
        },
    },
)
class ReplicationClosure(DraftProcess):
    pass


@draft_process(
    name="TemplateReplication",
    inputs={"template": "sequence"},
    outputs={"copies": "count"},
    contract={
        "summary": "Template replication — a template directs its own copying.",
        "behavior": "The self-organized grain beneath replication closure: a template "
                    "sequence directs the assembly of complementary copies of itself, "
                    "the autocatalytic core of heredity.",
        "senses": "the template sequence.",
        "affects": "the number of copies templated from it.",
        "constraints": "copies inherit the template sequence; copy count ≥ 0 and "
                       "bounded by monomer and energy availability.",
        "grain": "self-organized — lump its self-copying to get replication closure.",
        "ports": {
            "template": "self-copying template sequence (nt/aa string)",
            "copies": "number of copies templated (molecules)",
        },
    },
)
class TemplateReplication(DraftProcess):
    pass


@draft_process(
    name="TemplateDirectedSynthesis",
    inputs={"monomers": "concentration", "template": "sequence"},
    outputs={"polymer": "sequence"},
    contract={
        "summary": "Template-directed synthesis — monomers polymerize along a template.",
        "behavior": "The molecular grain beneath template replication: activated "
                    "monomers are added one by one along a template strand, "
                    "polymerizing a new sequence whose order is dictated by the "
                    "template.",
        "senses": "the monomer concentration and the template sequence.",
        "affects": "the newly polymerized sequence.",
        "constraints": "monomers conserved into the polymer; the product sequence is "
                       "determined by the template (base/residue pairing).",
        "grain": "molecular — the elementary step under template replication.",
        "ports": {
            "monomers": "activated monomer concentration (mol·L⁻¹)",
            "template": "directing template sequence (nt/aa string)",
            "polymer": "polymerized product sequence (nt/aa string)",
        },
    },
)
class TemplateDirectedSynthesis(DraftProcess):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Fig 9b — Minimal cell composition.
# The three functional columns realized as a WIRED composite: four processes —
# containment, metabolism, gene expression, replication — that support one
# another through SHARED component stores (membrane, metabolites, enzymes, genes,
# lipids) and the molecular building blocks (proteins, nucleic acids, amino
# acids) that generic diffusion and reactions keep supplied. Mutual dependence
# through shared components is the minimal expression of autopoietic closure.
# ─────────────────────────────────────────────────────────────────────────────
@draft_process(
    name="MinimalCellContainment",
    inputs={"lipids": "concentration"},
    outputs={"membrane": "area"},
    contract={
        "summary": "Minimal-cell containment — maintains the membrane from lipids.",
        "behavior": "Consumes lipids to build and maintain the membrane that bounds "
                    "the minimal cell, keeping the compartment that all the other "
                    "processes operate inside.",
        "senses": "the lipid pool.",
        "affects": "the membrane surface.",
        "constraints": "membrane area bounded by lipid supply; the compartment exists "
                       "only while the membrane is maintained.",
        "ports": {
            "lipids": "lipid concentration consumed (mol·L⁻¹)",
            "membrane": "maintained membrane area (m²)",
        },
    },
)
class MinimalCellContainment(DraftProcess):
    pass


@draft_process(
    name="MinimalCellMetabolism",
    inputs={"enzymes": "concentration", "nutrients": "concentration"},
    outputs={"metabolites": "concentration", "energy": "energy"},
    contract={
        "summary": "Minimal-cell metabolism — enzymes turn nutrients into metabolites and energy.",
        "behavior": "Uses the enzyme pool to convert nutrients into metabolites and "
                    "free energy, supplying the precursors and energy the rest of the "
                    "cell depends on. The enzymes it needs are themselves made by "
                    "gene expression.",
        "senses": "the enzyme pool and the available nutrients.",
        "affects": "the metabolite pool and the free-energy pool.",
        "constraints": "mass and energy conserved; enzymes act catalytically (not "
                       "consumed); output bounded by nutrient supply.",
        "ports": {
            "enzymes": "catalytic enzyme concentration (mol·L⁻¹)",
            "nutrients": "nutrient concentration consumed (mol·L⁻¹)",
            "metabolites": "metabolite pool produced (mol·L⁻¹)",
            "energy": "free energy produced (J)",
        },
    },
)
class MinimalCellMetabolism(DraftProcess):
    pass


@draft_process(
    name="GeneExpression",
    inputs={"genes": "concentration", "amino_acids": "concentration"},
    outputs={"proteins": "concentration", "enzymes": "concentration"},
    contract={
        "summary": "Gene expression — reads genes and makes proteins/enzymes.",
        "behavior": "Reads the gene pool and, drawing on amino-acid building blocks, "
                    "synthesizes proteins — including the enzymes metabolism needs — "
                    "translating stored information into functional machinery.",
        "senses": "the gene pool and the amino-acid building-block pool.",
        "affects": "the protein pool and the enzyme pool.",
        "constraints": "amino acids conserved into proteins; product amount bounded "
                       "by gene template and building-block supply.",
        "ports": {
            "genes": "gene template concentration read (mol·L⁻¹)",
            "amino_acids": "amino-acid building-block concentration (mol·L⁻¹)",
            "proteins": "protein pool produced (mol·L⁻¹)",
            "enzymes": "enzyme pool produced (mol·L⁻¹)",
        },
    },
)
class GeneExpression(DraftProcess):
    pass


@draft_process(
    name="MinimalCellReplication",
    inputs={"genes": "concentration", "energy": "energy"},
    outputs={"genes": "concentration", "nucleic_acids": "concentration"},
    contract={
        "summary": "Minimal-cell replication — copies the gene pool using energy.",
        "behavior": "Uses free energy to copy the gene pool, drawing on and returning "
                    "nucleic-acid building blocks, so the cell's stored information is "
                    "reproduced ahead of division.",
        "senses": "the gene pool and the available free energy.",
        "affects": "the gene pool (copies) and the nucleic-acid building-block pool.",
        "constraints": "nucleic acids conserved into gene copies; copying bounded by "
                       "energy and building-block supply; sequence preserved.",
        "ports": {
            "genes": "gene concentration copied (mol·L⁻¹)",
            "energy": "free energy driving copying (J)",
            "nucleic_acids": "nucleic-acid building-block concentration (mol·L⁻¹)",
        },
    },
)
class MinimalCellReplication(DraftProcess):
    pass


@draft_process(
    name="Diffusion",
    inputs={"metabolites": "concentration"},
    outputs={"metabolites": "concentration"},
    contract={
        "summary": "Diffusion — relaxes metabolite gradients.",
        "behavior": "Spreads metabolites through the cell interior, relaxing spatial "
                    "gradients so the shared metabolite pool the other processes read "
                    "and write stays well-mixed.",
        "senses": "the metabolite concentration field.",
        "affects": "the same metabolite field (smoothing).",
        "constraints": "total metabolite mass conserved (transport, not reaction); "
                       "concentrations stay non-negative.",
        "ports": {
            "metabolites": "metabolite concentration field (mol·L⁻¹)",
        },
    },
)
class Diffusion(DraftProcess):
    pass


@draft_process(
    name="Reactions",
    inputs={"amino_acids": "concentration", "nucleic_acids": "concentration"},
    outputs={"proteins": "concentration", "nucleic_acids": "concentration"},
    contract={
        "summary": "Reactions — generic molecular reactions among building blocks.",
        "behavior": "The generic reaction layer that interconverts molecular building "
                    "blocks — assembling amino acids into proteins and turning over "
                    "the nucleic-acid pool — keeping the shared building-block stores "
                    "that containment, metabolism, expression, and replication all "
                    "draw on supplied.",
        "senses": "the amino-acid and nucleic-acid building-block pools.",
        "affects": "the protein pool and the nucleic-acid pool.",
        "constraints": "atoms conserved reaction by reaction; concentrations stay "
                       "non-negative.",
        "ports": {
            "amino_acids": "amino-acid building-block concentration (mol·L⁻¹)",
            "nucleic_acids": "nucleic-acid building-block concentration (mol·L⁻¹)",
            "proteins": "protein pool produced (mol·L⁻¹)",
        },
    },
)
class Reactions(DraftProcess):
    pass
