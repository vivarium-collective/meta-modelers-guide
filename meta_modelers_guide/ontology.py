"""Phase 5 · ontology-typed interfaces + provenance.

The paper repeatedly points the interface vocabulary at existing ontologies — the
Cell Behavior Ontology (CBO) for cellular behaviours, SBO for reactions/parameters,
GO and ChEBI for molecular species — and argues that a model may occupy a process
role only when its meaning is made explicit. This module binds the workspace's
unit-bearing interface types and process kinds to ontology terms, so:

* every interface quantity carries an ontology reference (MIRIAM-style
  ``resource:term``), and every handler/draft resolves to a biological-process
  term (a keyword resolver, so we don't hand-map all ~42 drafts);
* conformance can be made ontology-aware — two differently-named types that denote
  the same ontology term are compatible (see compile.py ``_type_compatible``);
* each executable carries a provenance block (which figure, which process terms).

Term IDs below are limited to standard GO/PATO classes we are confident about; the
rest are given as ``ontology + label`` references (honest MIRIAM annotations without
a fabricated numeric id).

SCOPE (honest): this is a **curated annotation map** — a keyword→term lookup and a
hand-listed synonym table for type compatibility. It is NOT ontology *reasoning*:
it does not fetch term definitions, resolve identifiers, or check subsumption. It
records which curated ontology term each interface quantity / process kind is
*labelled* with; it does not verify that labelling against an ontology service.
"""
from __future__ import annotations

# ── interface quantities → ontology references ────────────────────────────────
# Physical quantities lean on PATO/UO/QUDT; cellular behaviours on GO/CBO.
QUANTITY_TERMS: dict[str, dict] = {
    "chemical_flux":  {"ontology": "UO",   "label": "flux (mol per second)"},
    "concentration":  {"ontology": "PATO", "label": "concentration", "id": "PATO:0000033"},
    "mass":           {"ontology": "PATO", "label": "mass", "id": "PATO:0000125"},
    "force":          {"ontology": "PATO", "label": "force"},
    "torque":         {"ontology": "PATO", "label": "torque"},
    "current":        {"ontology": "UO",   "label": "electric current (ampere)"},
    "voltage":        {"ontology": "PATO", "label": "electric potential"},
    "heat_flux":      {"ontology": "UO",   "label": "power (watt)"},
    "temperature":    {"ontology": "PATO", "label": "temperature", "id": "PATO:0000146"},
    "energy":         {"ontology": "PATO", "label": "energy", "id": "PATO:0001021"},
    "ph":             {"ontology": "PATO", "label": "acidity", "id": "PATO:0001842"},
    "growth_rate":    {"ontology": "GO",   "label": "growth", "id": "GO:0040007"},
    "area":           {"ontology": "PATO", "label": "area", "id": "PATO:0001323"},
    "volume":         {"ontology": "PATO", "label": "volume", "id": "PATO:0000918"},
    "signaling_rate": {"ontology": "GO",   "label": "signal transduction", "id": "GO:0007165"},
    "objective":      {"ontology": "CBO",  "label": "cell objective / fitness"},
    "viability":      {"ontology": "CBO",  "label": "cell viability"},
    "count":          {"ontology": "UO",   "label": "count"},
    "cell_count":     {"ontology": "CBO",  "label": "cell population size"},
    "cells":          {"ontology": "CBO",  "label": "cell population size"},
    "copies":         {"ontology": "SO",   "label": "copy number"},
    "quantity":       {"ontology": "PATO", "label": "amount"},
    "phase":          {"ontology": "PATO", "label": "phase"},
    "fraction":       {"ontology": "UO",   "label": "dimensionless fraction"},
    "rate":           {"ontology": "UO",   "label": "rate (per second)"},
    "length":         {"ontology": "PATO", "label": "length", "id": "PATO:0000122"},
    "time":           {"ontology": "UO",   "label": "time (second)"},
    "entropy":        {"ontology": "PATO", "label": "entropy"},
    "information":    {"ontology": "UO",   "label": "information (bit)"},
    "structure":      {"ontology": "PDB",  "label": "molecular structure"},
    "sequence":       {"ontology": "GO",   "label": "nucleotide/peptide sequence"},
    "identity":       {"ontology": "MIRIAM", "label": "entity identity"},
}

# ── process kinds → biological-process terms (keyword resolver) ────────────────
# ordered: first keyword found in the draft/handler name wins. IDs are standard GO.
PROCESS_KEYWORDS: list[tuple[str, dict]] = [
    ("transcription", {"ontology": "GO", "label": "transcription, DNA-templated", "id": "GO:0006351"}),
    ("translation",   {"ontology": "GO", "label": "translation", "id": "GO:0006412"}),
    ("replication",   {"ontology": "GO", "label": "DNA replication", "id": "GO:0006260"}),
    ("dnareplication",{"ontology": "GO", "label": "DNA replication", "id": "GO:0006260"}),
    ("segregate",     {"ontology": "GO", "label": "chromosome segregation", "id": "GO:0007059"}),
    ("divi",          {"ontology": "GO", "label": "cell division", "id": "GO:0051301"}),
    ("metabolism",    {"ontology": "GO", "label": "metabolic process", "id": "GO:0008152"}),
    ("transport",     {"ontology": "GO", "label": "transmembrane transport", "id": "GO:0055085"}),
    ("transmembrane", {"ontology": "GO", "label": "transmembrane transport", "id": "GO:0055085"}),
    ("diffusion",     {"ontology": "GO", "label": "transport", "id": "GO:0006810"}),
    ("membrane",      {"ontology": "GO", "label": "membrane organization", "id": "GO:0016044"}),
    ("containment",   {"ontology": "GO", "label": "membrane organization", "id": "GO:0016044"}),
    ("lipid",         {"ontology": "GO", "label": "lipid biosynthetic process", "id": "GO:0008610"}),
    ("subunit",       {"ontology": "GO", "label": "ribosome assembly", "id": "GO:0042255"}),
    ("assembly",      {"ontology": "GO", "label": "cellular component assembly", "id": "GO:0022607"}),
    ("autocatalysis", {"ontology": "GO", "label": "catalytic activity", "id": "GO:0003824"}),
    ("reaction",      {"ontology": "SBO", "label": "biochemical reaction"}),
    ("expression",    {"ontology": "GO", "label": "gene expression", "id": "GO:0010467"}),
    ("template",      {"ontology": "GO", "label": "template-directed synthesis"}),
    ("synthesis",     {"ontology": "GO", "label": "biosynthetic process", "id": "GO:0009058"}),
    ("surface",       {"ontology": "GO", "label": "cell adhesion", "id": "GO:0007155"}),
    ("attachment",    {"ontology": "GO", "label": "cell adhesion", "id": "GO:0007155"}),
    ("ecm",           {"ontology": "GO", "label": "extracellular matrix organization", "id": "GO:0030198"}),
    ("biofilm",       {"ontology": "GO", "label": "biofilm formation", "id": "GO:0042710"}),
    ("variation",     {"ontology": "GO", "label": "mutagenesis / variation", "id": "GO:0006281"}),
    ("selection",     {"ontology": "CBO", "label": "natural selection"}),
    ("port",          {"ontology": "CBO", "label": "interface capability"}),
    ("viability",     {"ontology": "CBO", "label": "cell viability"}),
    ("disintegr",     {"ontology": "CBO", "label": "cell disintegration / death"}),
    ("interface",     {"ontology": "CBO", "label": "cellular interface"}),
    ("molecular",     {"ontology": "SBO", "label": "molecular mechanism"}),
    ("uptake",        {"ontology": "GO", "label": "transmembrane transport", "id": "GO:0055085"}),
    ("nutrient",      {"ontology": "GO", "label": "response to nutrient levels", "id": "GO:0031667"}),
    ("environment",   {"ontology": "SBO", "label": "environmental process"}),
    ("thermal",       {"ontology": "PATO", "label": "temperature"}),
    ("production",    {"ontology": "GO", "label": "biosynthetic process", "id": "GO:0009058"}),
    ("degradation",   {"ontology": "GO", "label": "catabolic process", "id": "GO:0009056"}),
    ("mechanical",    {"ontology": "GO", "label": "response to mechanical stimulus", "id": "GO:0009612"}),
    ("stress",        {"ontology": "GO", "label": "response to stress", "id": "GO:0006950"}),
    # late generic fallback: any remaining cell process.
    ("cell",          {"ontology": "CBO", "label": "cellular process"}),
]


def interface_term(quantity: str) -> dict | None:
    """Ontology reference for an interface quantity type (``None`` if unmapped)."""
    return QUANTITY_TERMS.get(quantity)


def process_term(name: str) -> dict | None:
    """Resolve a draft/handler class name to a biological-process ontology term by
    keyword (first match wins). Returns ``None`` if nothing matches."""
    low = name.lower()
    for kw, term in PROCESS_KEYWORDS:
        if kw in low:
            return term
    return None


def term_ref(term: dict | None) -> str:
    """Render a term as a MIRIAM-style reference: the ``id`` itself when present
    (it already carries its ``ONTOLOGY:number`` prefix), else ``ontology:label``."""
    if not term:
        return ""
    if term.get("id"):
        return term["id"]
    return f"{term['ontology']}:{term['label']}"


def ontology_compatible(t1: str, t2: str) -> bool:
    """Two interface quantity types are ontology-compatible iff they denote the
    same ontology term — a differently-named type that means the same thing."""
    a, b = QUANTITY_TERMS.get(t1), QUANTITY_TERMS.get(t2)
    if not a or not b:
        return False
    return term_ref(a) == term_ref(b) and term_ref(a) != ""


def figure_provenance(env: dict) -> dict:
    """Provenance block for a compiled figure: each handled draft's process term."""
    return {draft: {"handler": spec["handler"],
                    "process_term": term_ref(process_term(draft))}
            for draft, spec in env.items()}
