"""Fig 6 & Fig 7 draft processes — grain-swap equivalence and molecular mechanisms.

These are *draft* processes: typed, unit-bearing ports plus a **behavior**
contract that says what the process senses, affects, and must keep in bounds —
**without committing to a mechanism** (no rate law, no update dynamics). They
render in the bigraph as the two alternative grains of one interface (Fig 6b) or
a molecular interface with typed channels and refined subports (Fig 7b, 7c), and
are auto-registered at ``local:<ClassName>`` by ``build_core``.

Contract convention used throughout the guide:

* ``summary``     — one line: what the process is.
* ``behavior``    — what it does, described functionally (no equations).
* ``senses``      — the interface variables it reads.
* ``affects``     — the interface variables it writes / controls.
* ``constraints`` — conservation laws / viability bounds it must respect.
* ``ports``       — every port with its biological unit.

``subports`` names the refinement of a coarse channel where the paper draws one.
"""
from __future__ import annotations

from process_bigraph import DraftProcess, draft_process


# ─────────────────────────────────────────────────────────────────────────────
# Fig 6b — cell disintegration: a grain-swap equivalence.
# A cell-level metabolism process and a molecular reaction network realize the
# SAME external interface at two different grains of description. Coarse ⇄ fine:
# lump closed catalytic loops → coarse metabolism; disintegrate → reaction network.
# ─────────────────────────────────────────────────────────────────────────────
@draft_process(
    name="CoarseGrainedMetabolism",
    inputs={"nutrients": "chemical_flux"},
    outputs={
        "biomass": "mass",
        "energy": "energy",
        "entropy": "entropy",
        "secretions": "chemical_flux",
    },
    contract={
        "summary": "Coarse-grained metabolism — the whole network as one exchange.",
        "behavior": "Lumps the entire metabolic network into a single coarse "
                    "exchange process: converts nutrient uptake into biomass and "
                    "free energy, releases waste secretions, and produces entropy — "
                    "without resolving the individual reactions inside.",
        "senses": "the incoming nutrient flux delivered across the boundary.",
        "affects": "cell biomass, available free energy, entropy production, and "
                   "the environmental waste pool via secretion flux.",
        "constraints": "mass and energy are conserved across the lumped boundary; "
                       "entropy production ≥ 0 (second law); yields bounded by "
                       "nutrient supply.",
        "ports": {
            "nutrients": "nutrient uptake flux, into cell (mol·s⁻¹)",
            "biomass": "biomass produced (kg)",
            "energy": "free energy captured (J)",
            "entropy": "entropy produced (J·K⁻¹·s⁻¹)",
            "secretions": "waste/secretion flux, out of cell (mol·s⁻¹)",
        },
    },
)
class CoarseGrainedMetabolism(DraftProcess):
    pass


@draft_process(
    name="CatalyzedReactionNetwork",
    inputs={"substrates": "concentration", "catalysts": "concentration"},
    outputs={"products": "concentration"},
    contract={
        "summary": "Catalyzed reaction network — the fine-grained mechanism.",
        "behavior": "Resolves metabolism into explicit enzyme-catalyzed reactions "
                    "that transform substrates into products in the presence of "
                    "catalysts; the coarse metabolism process is exactly what you "
                    "get when closed catalytic loops in this network are identified "
                    "and lumped.",
        "senses": "substrate and catalyst (enzyme) concentrations.",
        "affects": "product concentrations produced by the reactions.",
        "constraints": "atoms conserved reaction by reaction; catalysts are not "
                       "consumed; concentrations stay non-negative.",
        "ports": {
            "substrates": "substrate concentrations (mol·L⁻¹)",
            "catalysts": "catalyst/enzyme concentrations (mol·L⁻¹)",
            "products": "product concentrations (mol·L⁻¹)",
        },
    },
)
class CatalyzedReactionNetwork(DraftProcess):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Fig 7b/7c — molecular mechanisms as processes.
# A molecular process exchanges matter, charge, momentum, and energy through
# local physical channels and is defined over molecular structure — no cell-level
# boundary. The chemical channel refines into substrates/cofactors/catalysts/
# products (Fig 7c).
# ─────────────────────────────────────────────────────────────────────────────
@draft_process(
    name="MolecularMechanism",
    inputs={
        "chemical_in": "chemical_flux",
        "electrical_in": "current",
        "mechanical_in": "force",
        "thermal_in": "heat_flux",
        "structure": "structure",
    },
    outputs={
        "chemical_out": "chemical_flux",
        "electrical_out": "current",
        "mechanical_out": "force",
        "thermal_out": "heat_flux",
    },
    contract={
        "summary": "Molecular mechanism — a process over typed physical channels.",
        "behavior": "A molecular process (reaction, binding, transport, motility, "
                    "conformational change) that exchanges matter, charge, momentum, "
                    "and energy through local physical channels and is defined over "
                    "molecular structure — with no cell-level boundary standing "
                    "between it and its surroundings.",
        "senses": "incoming chemical, electrical, mechanical, and thermal flows, "
                  "read against its molecular structure.",
        "affects": "the outgoing chemical, electrical, mechanical, and thermal "
                   "channels.",
        "constraints": "mass, charge, momentum, and energy are conserved through "
                       "the mechanism; fluxes bounded by molecular kinetics and "
                       "the local physical gradients.",
        "subports": "chemical refines into {substrates, cofactors, catalysts, "
                    "products} (Fig 7c).",
        "ports": {
            "chemical_in": "chemical flux in (mol·s⁻¹)",
            "electrical_in": "electrical current in (C·s⁻¹, A)",
            "mechanical_in": "mechanical force in (kg·m·s⁻², N)",
            "thermal_in": "heat flux in (J·s⁻¹, W)",
            "structure": "molecular structure (PDB / SMILES)",
            "chemical_out": "chemical flux out (mol·s⁻¹)",
            "electrical_out": "electrical current out (C·s⁻¹, A)",
            "mechanical_out": "mechanical force out (kg·m·s⁻², N)",
            "thermal_out": "heat flux out (J·s⁻¹, W)",
        },
    },
)
class MolecularMechanism(DraftProcess):
    pass
