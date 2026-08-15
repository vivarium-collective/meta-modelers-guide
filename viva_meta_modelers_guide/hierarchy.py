"""Fig 8 draft processes — molecular compositions as nested hierarchies.

Fig 8b of *A meta-modeler's guide to the cellular interface* draws molecular
structure as a **nested place-graph**: matter is organized across scales, from
proteins up through complexes, organelles, compartments, and the extracellular
matrix. A composite process shows draft processes acting on NESTED stores that
stand in for those compartments and structures.

These are *draft* processes — typed, unit-bearing ports plus a **behavior**
contract that says what each process senses, affects, and keeps in bounds,
**without committing to a mechanism** (no rate law, no update dynamics). Each is
wired to leaves deep inside the nested place-graph so the topology reads like
Fig 8b, and all are auto-registered at ``local:<ClassName>`` by ``build_core``.

Contract convention used throughout the guide:

* ``summary``     — one line: what the process is.
* ``behavior``    — what it does, described functionally (no equations).
* ``senses``      — the interface variables it reads.
* ``affects``     — the interface variables it writes / controls.
* ``constraints`` — conservation laws / viability bounds it must respect.
* ``ports``       — every port with its biological unit.
"""
from __future__ import annotations

from process_bigraph import DraftProcess, draft_process


# ─────────────────────────────────────────────────────────────────────────────
# Fig 8b — draft processes acting across the nested molecular hierarchy.
# Each process reads/writes leaves deep inside the place-graph (membrane,
# nucleus→chromosome→chromatin→nucleosome→DNA, organelles→ribosomal_complex …).
# ─────────────────────────────────────────────────────────────────────────────
@draft_process(
    name="TransmembraneTransport",
    inputs={
        "nutrients_ext": "concentration",
        "transporters": "concentration",
    },
    outputs={
        "nutrients": "concentration",
        "metabolites": "concentration",
        "flux": "chemical_flux",
    },
    contract={
        "summary": "Transmembrane transport — matter moved across the membrane.",
        "behavior": "Moves matter across the membrane in both directions — takes "
                    "up extracellular nutrients into the cytoplasm and exports "
                    "metabolites/secretions — using the membrane's transporter "
                    "proteins as the conduit.",
        "senses": "external nutrient concentration and the membrane transporter "
                  "pool.",
        "affects": "the cytoplasmic nutrient and metabolite pools via a directed "
                   "transmembrane flux.",
        "constraints": "mass is conserved across the membrane; flux is bounded by "
                       "transporter capacity.",
        "ports": {
            "nutrients_ext": "extracellular nutrient concentration (mol·L⁻¹)",
            "transporters": "membrane transporter concentration (mol·L⁻¹)",
            "nutrients": "cytoplasmic nutrient concentration (mol·L⁻¹)",
            "metabolites": "cytoplasmic/exported metabolite concentration (mol·L⁻¹)",
            "flux": "transmembrane exchange flux (mol·s⁻¹)",
        },
    },
)
class TransmembraneTransport(DraftProcess):
    pass


@draft_process(
    name="ReplicationAndRepair",
    inputs={
        "dna": "concentration",
        "genes": "concentration",
    },
    outputs={
        "dna": "concentration",
    },
    contract={
        "summary": "Replication & repair — DNA is copied and maintained.",
        "behavior": "Reads the chromosomal DNA in the nucleus and its gene "
                    "content, then copies (replication) and corrects (repair) it, "
                    "restoring the DNA store toward an intact template.",
        "senses": "the nuclear DNA pool, gene content, and accumulated damage.",
        "affects": "the nuclear DNA pool (amount and integrity).",
        "constraints": "the copied sequence is conserved (fidelity); nucleotide "
                       "mass balance holds.",
        "ports": {
            "dna": "chromosomal DNA concentration (mol·L⁻¹)",
            "genes": "gene-locus concentration on the chromosome (mol·L⁻¹)",
        },
    },
)
class ReplicationAndRepair(DraftProcess):
    pass


@draft_process(
    name="CellMetabolism",
    inputs={
        "nutrients": "concentration",
        "enzymes": "concentration",
    },
    outputs={
        "metabolites": "concentration",
        "energy": "energy",
    },
    contract={
        "summary": "Cell metabolism — nutrients converted to metabolites + energy.",
        "behavior": "Uses cytoplasmic enzymes to convert incoming nutrients into "
                    "metabolic intermediates and free energy, supplying the "
                    "building blocks and fuel for the rest of the cell.",
        "senses": "the cytoplasmic nutrient and enzyme pools.",
        "affects": "the cytoplasmic metabolite pool and available free energy.",
        "constraints": "atom and energy balance across the reaction network; "
                       "concentrations stay non-negative.",
        "ports": {
            "nutrients": "cytoplasmic nutrient concentration (mol·L⁻¹)",
            "enzymes": "cytoplasmic enzyme concentration (mol·L⁻¹)",
            "metabolites": "cytoplasmic metabolite concentration (mol·L⁻¹)",
            "energy": "free energy produced (J)",
        },
    },
)
class CellMetabolism(DraftProcess):
    pass


@draft_process(
    name="Transcription",
    inputs={
        "dna": "concentration",
        "genes": "concentration",
        "regulation": "concentration",
    },
    outputs={
        "rna": "concentration",
    },
    contract={
        "summary": "Transcription — genes read from DNA into RNA.",
        "behavior": "Reads gene loci on the chromosomal DNA, gated by the nuclear "
                    "transcription-regulation complex, and produces RNA transcripts "
                    "that leave the nucleus into the cytoplasm.",
        "senses": "chromosomal DNA, its gene loci, and the regulation complex.",
        "affects": "the cytoplasmic RNA pool.",
        "constraints": "transcript sequence matches the template (fidelity); RNA "
                       "output bounded by gene availability and regulation.",
        "ports": {
            "dna": "chromosomal DNA concentration (mol·L⁻¹)",
            "genes": "transcribed gene-locus concentration (mol·L⁻¹)",
            "regulation": "transcription-regulation complex concentration (mol·L⁻¹)",
            "rna": "cytoplasmic RNA concentration (mol·L⁻¹)",
        },
    },
)
class Transcription(DraftProcess):
    pass


@draft_process(
    name="Translation",
    inputs={
        "rna": "concentration",
        "metabolites": "concentration",
        "ribosome": "count",
    },
    outputs={
        "proteins": "concentration",
    },
    contract={
        "summary": "Translation — RNA read on ribosomes into protein.",
        "behavior": "Reads cytoplasmic RNA on ribosomal complexes, consuming "
                    "amino-acid metabolites, to synthesize new proteins into the "
                    "cytoplasmic protein pool.",
        "senses": "cytoplasmic RNA, the metabolite (amino-acid) pool, and the "
                  "available ribosome count.",
        "affects": "the cytoplasmic protein pool.",
        "constraints": "protein sequence matches the transcript (fidelity); mass "
                       "balance on consumed amino acids.",
        "ports": {
            "rna": "cytoplasmic RNA concentration (mol·L⁻¹)",
            "metabolites": "amino-acid metabolite concentration (mol·L⁻¹)",
            "ribosome": "assembled ribosome count (molecules)",
            "proteins": "cytoplasmic protein concentration (mol·L⁻¹)",
        },
    },
)
class Translation(DraftProcess):
    pass


@draft_process(
    name="SubunitAssembly",
    inputs={
        "proteins": "concentration",
        "ribosomal_subunits": "count",
    },
    outputs={
        "ribosome": "count",
    },
    contract={
        "summary": "Subunit assembly — subunits assembled into complexes.",
        "behavior": "Assembles cytoplasmic proteins and ribosomal subunits into "
                    "higher-order structures — the ribosomal complex in particular — "
                    "building the machinery the rest of the hierarchy depends on.",
        "senses": "the cytoplasmic protein pool and the free ribosomal-subunit "
                  "count.",
        "affects": "the assembled ribosome count in the ribosomal complex.",
        "constraints": "subunit stoichiometry is respected; components are "
                       "conserved through assembly (no matter created).",
        "ports": {
            "proteins": "cytoplasmic protein concentration (mol·L⁻¹)",
            "ribosomal_subunits": "free ribosomal-subunit count (molecules)",
            "ribosome": "assembled ribosome count (molecules)",
        },
    },
)
class SubunitAssembly(DraftProcess):
    pass
