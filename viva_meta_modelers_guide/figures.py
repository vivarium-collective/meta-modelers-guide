"""Curated biological icon set for loom node figures (`_figure`).

Loom renders an inline-SVG ``_figure`` on any composite node (store or process).
This module holds a small library of hand-drawn biological line-art glyphs and a
resolver that maps a node's name / type / process-class to the right glyph, so
every store and process in the figure composites carries a recognizable
illustration — in the spirit of the paper's BioRender panels.

Usage (see scripts/add_figures.py):

    from viva_meta_modelers_guide.figures import figure_for_store, figure_for_process
    svg = figure_for_store("DNA", "concentration")      # -> "<svg …double helix…/>"
    svg = figure_for_process("Transcription")           # -> "<svg …polymerase…/>"
"""
from __future__ import annotations

STORE_INK = "#0b7a75"      # teal — matches loom's green store border
PROC_INK = "#4b5bd6"       # indigo — matches loom's blue process border


def _svg(body: str, color: str) -> str:
    return (
        f'<svg viewBox="0 0 24 24" width="26" height="26" fill="none" '
        f'stroke="{color}" stroke-width="1.5" stroke-linecap="round" '
        f'stroke-linejoin="round">{body}</svg>'
    )


# ── glyph bodies (inner markup; drawn on a 24×24 grid) ───────────────────────
_G: dict[str, str] = {
    # nucleic acids / genome
    "dna": '<path d="M8 3c0 4 8 5 8 9s-8 5-8 9"/><path d="M16 3c0 4-8 5-8 9s8 5 8 9"/>'
           '<path d="M9 7h6M8.5 12h7M9 17h6"/>',
    "rna": '<path d="M4 14c2-4 4 4 6 0s4-8 6-4 4 6 4 6"/><circle cx="19" cy="9" r="0.8" fill="'+ "currentColor" +'"/>',
    "sequence": '<path d="M5 8h14M5 12h14M5 16h9"/>',
    "chromosome": '<path d="M8 4l8 16M16 4L8 20"/><ellipse cx="12" cy="12" rx="2.2" ry="3"/>',
    # proteins / enzymes
    "protein": '<path d="M7 9c-2 2-1 6 2 6s3-3 5-3 3 3 5 1 1-6-2-7-4 2-6 2-4-1-4-1z"/>',
    "ribosome": '<ellipse cx="12" cy="9" rx="6" ry="4"/><ellipse cx="12" cy="15" rx="4.5" ry="3"/>',
    "enzyme": '<path d="M6 8a6 6 0 1 0 6 6"/><path d="M12 14l3-3 3 1-1 3-3 1z"/>',
    # membranes / lipids
    "membrane": '<path d="M3 9h18M3 15h18"/>'
                '<circle cx="6" cy="9" r="1.1"/><circle cx="12" cy="9" r="1.1"/><circle cx="18" cy="9" r="1.1"/>'
                '<circle cx="9" cy="15" r="1.1"/><circle cx="15" cy="15" r="1.1"/>'
                '<path d="M6 10v2M12 10v2M18 10v2M9 14v-2M15 14v-2"/>',
    "channel": '<path d="M3 8h5M16 8h5M3 16h5M16 16h5"/><rect x="8" y="5" width="3.5" height="14" rx="1"/>'
               '<rect x="12.5" y="5" width="3.5" height="14" rx="1"/><path d="M12 9v6"/>',
    # organelles / compartments
    "nucleus": '<circle cx="12" cy="12" r="8"/><circle cx="13" cy="11" r="2.4"/>',
    "mitochondria": '<ellipse cx="12" cy="12" rx="9" ry="5"/><path d="M6 10c2 3 2 3 0 4M10 9c2 3 2 5 0 6M14 9c2 3 2 5 0 6M18 10c-2 3-2 3 0 4"/>',
    "cell": '<path d="M12 3a9 8 0 1 0 0.1 0z"/><circle cx="13" cy="13" r="2.5"/>',
    "colony": '<circle cx="8" cy="9" r="3"/><circle cx="15" cy="8" r="2.6"/><circle cx="12" cy="15" r="3.2"/><circle cx="17" cy="15" r="2.3"/>',
    "cytoplasm": '<rect x="3" y="4" width="18" height="16" rx="7"/><circle cx="9" cy="10" r="1.3"/><circle cx="15" cy="14" r="1.6"/>',
    # ECM / fibers
    "fiber": '<path d="M3 7l18 3M3 12l18 3M3 17l18-3M7 4l-2 16M14 4l2 16"/>',
    "surface": '<path d="M3 15h18"/><path d="M5 15l-2 4M9 15l-2 4M13 15l-2 4M17 15l-2 4M21 15l-2 4"/>',
    # small molecules / metabolism
    "molecule": '<circle cx="7" cy="8" r="2.4"/><circle cx="16" cy="7" r="2"/><circle cx="12" cy="16" r="2.6"/>'
                '<path d="M9 9l5 5M14.5 8.5L13 14"/>',
    "reaction": '<path d="M5 9a7 7 0 0 1 13-1"/><path d="M18 4v4h-4"/><path d="M19 15a7 7 0 0 1-13 1"/><path d="M6 20v-4h4"/>',
    "metabolism": '<circle cx="12" cy="12" r="2.5"/>'
                  '<path d="M12 9.5V4M12 14.5V20M9.5 12H4M14.5 12H20M10 10L6 6M14 14l4 4M14 10l4-4M10 14l-4 4"/>',
    "diffusion": '<circle cx="7" cy="12" r="1.4" fill="currentColor" stroke="none"/>'
                 '<circle cx="12" cy="9" r="1.1" fill="currentColor" stroke="none"/>'
                 '<circle cx="12" cy="15" r="1.1" fill="currentColor" stroke="none"/>'
                 '<circle cx="17" cy="12" r="0.9" fill="currentColor" stroke="none"/>'
                 '<path d="M9 12h3M9 12h11" stroke-dasharray="1 2"/><path d="M18 10l2 2-2 2"/>',
    "transport": '<path d="M6 6v12M18 6v12"/><path d="M8 10h8M14 7l3 3-3 3"/><path d="M16 15H8m3 3-3-3 3-3"/>',
    "entropy": '<path d="M4 18c3 0 3-4 6-4s3 4 6 4"/><circle cx="16" cy="6" r="1" fill="currentColor" stroke="none"/>'
               '<circle cx="19" cy="9" r="1" fill="currentColor" stroke="none"/><circle cx="14" cy="9" r="1" fill="currentColor" stroke="none"/>',
    "droplet": '<path d="M12 3s6 7 6 11a6 6 0 0 1-12 0c0-4 6-11 6-11z"/>',
    # physical channels
    "energy": '<path d="M13 2L5 13h6l-2 9 9-12h-6z" fill="currentColor" stroke="none"/>',
    "electrical": '<path d="M4 12h4l2-5 3 10 2-5h5"/>',
    "signal": '<circle cx="6" cy="12" r="1.4" fill="currentColor" stroke="none"/>'
              '<path d="M10 8a6 6 0 0 1 0 8M13 5a10 10 0 0 1 0 14"/>',
    "force": '<path d="M4 12h13"/><path d="M12 6l6 6-6 6"/>',
    "thermal": '<path d="M12 3a2 2 0 0 1 2 2v9a4 4 0 1 1-4 0V5a2 2 0 0 1 2-2z"/><circle cx="12" cy="18" r="2" fill="currentColor" stroke="none"/>',
    # cell-level descriptors
    "growth": '<path d="M12 21V8"/><path d="M12 12C9 12 6 10 6 6c4 0 6 2 6 6z"/><path d="M12 10c3 0 6-2 6-6-4 0-6 2-6 6z"/>',
    "mass": '<path d="M7 8h10l2 12H5z"/><path d="M9 8a3 3 0 0 1 6 0"/>',
    "shape": '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 3v18M4 7.5l8 4.5 8-4.5"/>',
    "area": '<rect x="4" y="4" width="16" height="16" rx="1" stroke-dasharray="3 2"/>',
    "volume": '<path d="M5 8l7-4 7 4v8l-7 4-7-4z"/><path d="M5 8l7 4 7-4M12 12v8"/>',
    "viability": '<path d="M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.5A4 4 0 0 1 19 10c0 5.5-7 10-7 10z"/>',
    "objective": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/>',
    "structure": '<path d="M12 3l7 4v10l-7 4-7-4V7z"/><circle cx="12" cy="12" r="2.5"/>',
    "counter": '<ellipse cx="12" cy="6" rx="7" ry="2.5"/><path d="M5 6v6c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V6"/><path d="M5 12v6c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-6"/>',
    "gauge": '<path d="M4 16a8 8 0 0 1 16 0"/><path d="M12 16l4-4"/><circle cx="12" cy="16" r="1" fill="currentColor" stroke="none"/>',
    "barrier": '<path d="M3 6h18M3 12h18M3 18h18M8 6v6M16 6v6M12 12v6"/>',
    "port": '<circle cx="7" cy="12" r="3"/><path d="M10 12h6M16 9v6"/><path d="M19 10v4"/>',
    # process actions
    "replication": '<path d="M12 5v14"/><path d="M12 9c-3 0-5 1.5-5 4M12 9c3 0 5 1.5 5 4"/>'
                   '<circle cx="7" cy="15" r="2.2"/><circle cx="17" cy="15" r="2.2"/>',
    "divide": '<circle cx="8" cy="12" r="4.5"/><circle cx="16" cy="12" r="4.5"/>',
    "assembly": '<rect x="3" y="10" width="6" height="6" rx="1"/><rect x="15" y="10" width="6" height="6" rx="1"/>'
                '<rect x="9" y="5" width="6" height="6" rx="1"/><path d="M9 13h6"/>',
    "mutation": '<path d="M5 20V6M5 12h5a4 4 0 0 0 4-4V4M14 16h2a3 3 0 0 0 3-3"/>'
                '<circle cx="5" cy="4" r="1.4" fill="currentColor" stroke="none"/><circle cx="19" cy="13" r="1.4"/>',
    "selection": '<path d="M3 5h18l-7 8v6l-4-2v-4z"/>',
    "expression": '<path d="M4 8h6M4 12h4"/><path d="M13 6l7 6-7 6"/><circle cx="19" cy="12" r="0"/>',
    "secretion": '<circle cx="8" cy="12" r="5"/><path d="M14 12h6M16 9l3 3-3 3" stroke-dasharray="0"/>'
                 '<circle cx="18" cy="7" r="0.9" fill="currentColor" stroke="none"/><circle cx="18" cy="17" r="0.9" fill="currentColor" stroke="none"/>',
    "adhesion": '<circle cx="9" cy="8" r="4"/><path d="M3 18h18"/><path d="M7 12v6M11 12v6"/>',
    "generic": '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M6 6l2 2M16 16l2 2M18 6l-2 2M8 16l-2 2"/>',
}


# ── name/type → glyph keyword resolvers ──────────────────────────────────────
# order matters: first substring hit wins
_STORE_RULES: list[tuple[tuple[str, ...], str]] = [
    # --- specific compound names FIRST (avoid substring traps like
    #     "extraCELLular" -> cell, "MEMBRANE_potential" -> membrane) ---
    (("membrane_potential", "bioelectric"), "electrical"),
    (("interstitial_matrix", "basement_matrix", "extracellular_matrix", "ecm",
      "collagen", "fibronectin", "fiber"), "fiber"),
    (("transmembrane_transporter", "transporter", "channel"), "channel"),
    # --- nucleic acids / genome ---
    (("nucleosome", "chromatin", "histone", "dna", "genome", "genes", "gene"), "dna"),
    (("chromosome",), "chromosome"),
    (("rna", "mrna", "transcript"), "rna"),
    (("template", "polymer", "copies", "sequence"), "sequence"),
    (("ribosom",), "ribosome"),
    (("enzyme", "catalyst", "cofactor"), "enzyme"),
    (("protein", "amino_acid", "nucleic_acid"), "protein"),
    (("uptake", "transport"), "channel"),
    (("membrane", "lipid", "boundary"), "membrane"),
    (("mitochond",), "mitochondria"),
    (("nucleus",), "nucleus"),
    (("secretory_organelle", "organelle"), "mitochondria"),
    (("cytoplasm",), "cytoplasm"),
    (("biofilm", "colony", "community", "cells"), "colony"),
    (("cell_o157", "cell_ecoli", "daughter", "variant", "single_cell", "cell"), "cell"),
    (("environ",), "cell"),
    (("surface",), "surface"),
    (("metabolite", "nutrient", "substrate", "product", "monomer", "aggregate",
      "chemical_exchange"), "molecule"),
    (("entropy",), "entropy"),
    (("concentration_field", "chemical_field"), "droplet"),
    (("chemical",), "molecule"),
    (("energy",), "energy"),
    (("voltage", "current", "electrical"), "electrical"),
    (("signal",), "signal"),
    (("thermal", "temperature", "heat"), "thermal"),
    (("barrier",), "barrier"),
    (("motility", "force", "traction", "adhesion", "mechanical"), "force"),
    (("biomass", "biofilm_mass", "mass"), "mass"),
    (("shape", "volume", "location"), "shape"),
    (("growth_rate", "growth"), "growth"),
    (("viability",), "viability"),
    (("objective", "fitness"), "objective"),
    (("structure",), "structure"),
    (("identity", "new_port", "port", "subport", "interface"), "port"),
    (("permeability", "fraction"), "gauge"),
    (("count", "population"), "counter"),
    (("area",), "area"),
    (("containment", "coarse", "selforg", "molecular", "metabolism", "replication",
      "attached"), "molecule"),
]

_TYPE_FALLBACK: dict[str, str] = {
    "concentration": "droplet", "chemical_flux": "molecule", "mass": "mass",
    "force": "force", "current": "electrical", "voltage": "electrical",
    "heat_flux": "thermal", "temperature": "thermal", "energy": "energy",
    "entropy": "entropy", "growth_rate": "growth", "area": "area", "volume": "shape",
    "signaling_rate": "signal", "objective": "objective", "viability": "viability",
    "count": "counter", "cell_count": "counter", "fraction": "gauge",
    "structure": "structure", "sequence": "sequence", "identity": "port",
}

_PROCESS_RULES: list[tuple[tuple[str, ...], str]] = [
    (("Transcription",), "dna"),
    (("Translation",), "ribosome"),
    (("SubunitAssembly", "Assembly"), "assembly"),
    (("DNAReplication", "ReplicationAndRepair", "TemplateReplication",
      "TemplateDirectedSynthesis", "ReplicationClosure", "MinimalCellReplication",
      "SegregateChromosome"), "replication"),
    (("Divide",), "divide"),
    (("GeneExpression", "Expression"), "expression"),
    (("Metabolism", "CatalyzedReactionNetwork"), "metabolism"),
    (("Autocatalysis", "Reactions", "Reaction"), "reaction"),
    (("Diffusion", "ReactionDiffusion"), "diffusion"),
    (("ProductionDegradation",), "reaction"),
    (("TransmembraneTransport", "NutrientExchange"), "transport"),
    (("MembraneSelfAssembly", "LipidAggregation", "Containment"), "membrane"),
    (("MechanicalStress", "MotileForce"), "force"),
    (("ElectricalSignaling",), "electrical"),
    (("BiofilmGrowth", "Growth"), "growth"),
    (("SurfaceAttachment",), "adhesion"),
    (("ECMSecretion", "Secretion"), "secretion"),
    (("Variation",), "mutation"),
    (("Selection",), "selection"),
    (("PortAddition",), "port"),
    (("CellularInterface", "SingleCellProcesses"), "cell"),
    (("MolecularMechanism",), "molecule"),
]


def figure_for_store(name: str, vtype: str = "") -> str:
    n = (name or "").lower()
    for keys, glyph in _STORE_RULES:
        if any(k in n for k in keys):
            return _svg(_G[glyph], STORE_INK)
    if vtype in _TYPE_FALLBACK:
        return _svg(_G[_TYPE_FALLBACK[vtype]], STORE_INK)
    return _svg(_G["molecule"], STORE_INK)


def figure_for_process(cls: str) -> str:
    for keys, glyph in _PROCESS_RULES:
        if any(k in cls for k in keys):
            return _svg(_G[glyph], PROC_INK)
    return _svg(_G["generic"], PROC_INK)
