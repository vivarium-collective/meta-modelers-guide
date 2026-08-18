"""Fig 10 draft processes — growth, division, development, and evolution.

Fig 10 of the guide reframes the classic hallmarks of life as operations on the
compositional structure itself, not merely as values changing inside a fixed
interface. Three panels, three composites:

* **10.1 Division** — a *compositional rewrite* that partitions one cell's state
  (DNA, biomass) into two daughters, each re-coupling its interface to the shared
  environment.
* **10.2 Development (biofilm)** — a *hierarchical reorganization* where
  individual cells become part of a collective composite (cells + ECM + surface
  embedded in a biofilm interface).
* **10.3 Evolution** — *variation, selection, and new interface ports*: new
  capabilities arise through the ADDITION of ports, expanding the space of
  possible interactions.

These are *draft* processes: typed, unit-bearing ports plus a **behavior**
contract that says what the process senses, affects, and must keep in bounds —
**without committing to a mechanism** (no rate law, no update dynamics). Where the
biology is an event-driven graph rewrite (division, driving events) that is
stated in the contract as a rewrite, not implemented. Auto-registered at
``local:<ClassName>`` by ``build_core``.

Contract convention (as elsewhere in the guide):

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
# Fig 10.1 — Division (panel b): division as a compositional rewrite
# Prokaryotic division: replicate DNA, segregate chromosomes, and split one cell
# into two daughters, partitioning state (DNA, biomass) between them.
# ─────────────────────────────────────────────────────────────────────────────
@draft_process(
    name="DNAReplication",
    inputs={"dna": "concentration", "energy": "energy"},
    outputs={"dna": "concentration"},
    contract={
        "summary": "DNA replication — duplicates the chromosome before division.",
        "behavior": "Copies the chromosome so each future daughter can inherit a "
                    "complete genome, consuming free energy to build the second "
                    "copy prior to the division rewrite.",
        "senses": "current chromosomal DNA content; available free energy.",
        "affects": "the replicated DNA pool (roughly doubled before segregation).",
        "constraints": "energy is consumed, not created; replication completes "
                       "before the cell is licensed to divide (checkpoint).",
        "ports": {
            "dna": "chromosomal DNA content (mol·L⁻¹)",
            "energy": "free energy consumed by replication (J)",
        },
    },
)
class DNAReplication(DraftProcess):
    pass


@draft_process(
    name="SegregateChromosome",
    inputs={"dna": "concentration"},
    outputs={"dna_1": "concentration", "dna_2": "concentration"},
    contract={
        "summary": "Chromosome segregation — partitions replicated DNA to the poles.",
        "behavior": "Moves the two replicated chromosomes toward opposite poles so "
                    "that the impending division rewrite delivers one genome to "
                    "each daughter.",
        "senses": "the replicated (roughly doubled) DNA pool.",
        "affects": "two pole-localized DNA pools destined for the two daughters.",
        "constraints": "DNA is conserved across the split (dna ≈ dna_1 + dna_2); "
                       "each daughter must receive one complete genome.",
        "ports": {
            "dna": "replicated chromosomal DNA content (mol·L⁻¹)",
            "dna_1": "DNA partitioned toward daughter 1 (mol·L⁻¹)",
            "dna_2": "DNA partitioned toward daughter 2 (mol·L⁻¹)",
        },
    },
)
class SegregateChromosome(DraftProcess):
    pass


@draft_process(
    name="Divide",
    inputs={"biomass": "mass"},
    outputs={
        "biomass_1": "mass",
        "biomass_2": "mass",
        "cell_count": "cell_count",
    },
    contract={
        "summary": "Division — the event-driven rewrite splitting one cell into two.",
        "behavior": "Forms a septum and separates one cell into two daughters, "
                    "partitioning biomass between them and incrementing the cell "
                    "count. This is an event-driven GRAPH REWRITE of the composite "
                    "(a new cell node appears), not a continuous update — the draft "
                    "process only declares the interface of that rewrite.",
        "senses": "the parent cell's biomass.",
        "affects": "two daughter biomass pools and the population cell count.",
        "constraints": "biomass is conserved across the split "
                       "(biomass ≈ biomass_1 + biomass_2); cell_count increments by "
                       "one; each daughter must remain viable (above a minimum "
                       "size) for the rewrite to be admissible.",
        "ports": {
            "biomass": "parent cell biomass (kg)",
            "biomass_1": "biomass partitioned to daughter 1 (kg)",
            "biomass_2": "biomass partitioned to daughter 2 (kg)",
            "cell_count": "population cell count, incremented by division (cells)",
        },
    },
)
class Divide(DraftProcess):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Fig 10.2 — Development / biofilm (panels c/d): hierarchical reorganization
# Individual cells attach, secrete matrix, and grow into a structured community —
# cellular interfaces embedded in a collective (biofilm) interface.
# ─────────────────────────────────────────────────────────────────────────────
@draft_process(
    name="SurfaceAttachment",
    inputs={"cells": "cell_count", "surface": "area"},
    outputs={"attached": "cell_count", "adhesion": "force"},
    contract={
        "summary": "Surface attachment — cells adhere to a surface.",
        "behavior": "Planktonic cells encounter a surface and adhere to it, "
                    "converting free-swimming cells into an attached founding "
                    "population and generating adhesive force that anchors them.",
        "senses": "the free-cell population; the available surface area.",
        "affects": "the attached-cell population and the adhesion force.",
        "constraints": "attached cells ≤ available cells; adhesion is bounded by "
                       "surface area and adhesin availability.",
        "ports": {
            "cells": "free (planktonic) cell population (cells)",
            "surface": "available attachment surface area (m²)",
            "attached": "surface-attached cell population (cells)",
            "adhesion": "adhesive force anchoring cells to the surface (kg·m·s⁻², N)",
        },
    },
)
class SurfaceAttachment(DraftProcess):
    pass


@draft_process(
    name="ECMSecretion",
    inputs={"cells": "cell_count", "metabolites": "concentration"},
    outputs={"ecm": "concentration"},
    contract={
        "summary": "ECM secretion — attached cells build the extracellular matrix.",
        "behavior": "Attached cells consume metabolites to synthesize and secrete "
                    "extracellular polymeric substances, the shared matrix that "
                    "binds the community into a biofilm.",
        "senses": "the attached-cell population; the metabolite pool.",
        "affects": "the extracellular-matrix concentration.",
        "constraints": "matrix production is bounded by cell number and metabolite "
                       "supply; mass drawn from metabolites is conserved into ECM.",
        "ports": {
            "cells": "attached cell population secreting matrix (cells)",
            "metabolites": "metabolite pool consumed for synthesis (mol·L⁻¹)",
            "ecm": "extracellular-matrix concentration (mol·L⁻¹)",
        },
    },
)
class ECMSecretion(DraftProcess):
    pass


@draft_process(
    name="BiofilmGrowth",
    inputs={
        "cells": "cell_count",
        "ecm": "concentration",
        "nutrients": "concentration",
    },
    outputs={"biofilm_mass": "mass", "cells": "cell_count"},
    contract={
        "summary": "Biofilm growth — the community grows into a structured biofilm.",
        "behavior": "Matrix-embedded cells take up nutrients and proliferate, "
                    "expanding the biofilm's mass and cell number into a structured, "
                    "three-dimensional community — a collective composite with its "
                    "own interface to the surrounding environment.",
        "senses": "the embedded-cell population; the matrix; nutrient availability.",
        "affects": "the total biofilm biomass and the embedded-cell population.",
        "constraints": "growth is bounded by nutrient supply and matrix capacity; "
                       "biomass gain respects mass balance; cell_count ≥ 0.",
        "ports": {
            "cells": "matrix-embedded cell population (cells)",
            "ecm": "extracellular-matrix concentration (mol·L⁻¹)",
            "nutrients": "nutrient concentration available to the community (mol·L⁻¹)",
            "biofilm_mass": "total biofilm biomass (kg)",
        },
    },
)
class BiofilmGrowth(DraftProcess):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Fig 10.3 — Evolution (panels e/f): variation, selection, and new ports
# Evolution reshapes the composition itself: discrete driving events introduce
# variation, selection favors viable interfaces, and NEW interface capabilities
# arise through the ADDITION of ports (cell^ecoli → cell^O157).
# ─────────────────────────────────────────────────────────────────────────────
@draft_process(
    name="Variation",
    inputs={"genome": "sequence"},
    outputs={"genome": "sequence", "variant": "identity"},
    contract={
        "summary": "Variation — discrete driving events expand functional diversity.",
        "behavior": "Mutation, recombination, and horizontal transfer alter the "
                    "genome, producing new variants. These are discrete DRIVING "
                    "EVENTS (graph rewrites of the sequence/composition), not a "
                    "continuous update — the draft process only declares the "
                    "interface across which variation enters.",
        "senses": "the current genome sequence.",
        "affects": "the (altered) genome sequence and a new variant identity.",
        "constraints": "variation is discrete and heritable; the variant must "
                       "still specify a buildable, viable interface to persist.",
        "ports": {
            "genome": "genomic sequence subject to variation (nucleotide sequence)",
            "variant": "identity label of the generated variant (identifier)",
        },
    },
)
class Variation(DraftProcess):
    pass


@draft_process(
    name="Selection",
    inputs={"viability": "viability", "fitness": "objective"},
    outputs={"cell_count": "cell_count"},
    contract={
        "summary": "Selection — favors viable interfaces, eliminates those that fail.",
        "behavior": "Differential survival and reproduction: interfaces that "
                    "sustain viability and score well on the fitness objective "
                    "under the given conditions increase in the population, while "
                    "those that fail are eliminated.",
        "senses": "each variant's viability and its fitness objective value.",
        "affects": "the per-variant cell count (population representation).",
        "constraints": "cell_count ≥ 0; variants below the viability bound are "
                       "driven toward extinction; selection acts on existing "
                       "variation, it does not create it.",
        "ports": {
            "viability": "in-bounds fraction; 1 = viable, 0 = non-viable (0–1)",
            "fitness": "fitness objective value under current conditions (dimensionless)",
            "cell_count": "population count of the selected variant (cells)",
        },
    },
)
class Selection(DraftProcess):
    pass


@draft_process(
    name="PortAddition",
    inputs={"genome": "sequence"},
    outputs={"new_port": "chemical_flux", "identity": "identity"},
    contract={
        "summary": "Port addition — a compositional innovation adding an interface port.",
        "behavior": "A driving event (e.g. horizontal gene transfer) endows the "
                    "cell with a genuinely NEW interface capability: it ADDS a port "
                    "to the interface — a new channel of interaction with the "
                    "environment that did not exist before (e.g. cell^ecoli → "
                    "cell^O157 gaining a toxin-secretion port). This changes the "
                    "SHAPE of the interface, not merely the value on an existing "
                    "port — a rewrite that grows the composition.",
        "senses": "the genome sequence encoding the new capability.",
        "affects": "adds a new interface port (a new interaction modality) and a "
                   "new organismal identity.",
        "constraints": "the added port must be typed and unit-consistent with the "
                       "environment it couples to; the expanded interface must "
                       "remain viable; this is an ADDITION of structure, not a "
                       "value change on an existing port.",
        "ports": {
            "genome": "genomic sequence encoding the new capability (nucleotide sequence)",
            "new_port": "the newly added interface port — a new interaction flux (mol·s⁻¹)",
            "identity": "the new organismal identity carrying the added port (identifier)",
        },
    },
)
class PortAddition(DraftProcess):
    pass
