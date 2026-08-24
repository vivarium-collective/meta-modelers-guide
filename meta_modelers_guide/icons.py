"""Canonical scientific icon library for the meta-modeler's-guide composites.

Single source of truth for the ``_figure`` glyphs shown on loom store/process
nodes. Each icon is a refined line-drawing (24x24 grid, 1.5 stroke, round
caps/joins) chosen for scientific accuracy — a real double helix, a
phospholipid bilayer, a ribosome's two subunits, a triphosphate nucleotide —
not a generic pictogram.

Colour is applied by ROLE, not baked into the design: stores render teal,
processes render indigo (the loom's existing semantic split). ``{C}`` marks a
fill that should take the role colour.

Usage (see ``scripts/regen_icons.py``): ``figure(node_name, is_process)`` ->
full ``<svg>`` string, or ``None`` when the name has no mapped concept (the
node keeps whatever it had).
"""
from __future__ import annotations

import re

TEAL = "#0b7a75"     # stores
INDIGO = "#4b5bd6"   # processes


def wrap(inner: str, color: str) -> str:
    return (
        '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" '
        'stroke="%s" stroke-width="1.5" stroke-linecap="round" '
        'stroke-linejoin="round">%s</svg>' % (color, inner.replace("{C}", color))
    )


# ── the canonical set: concept -> inner SVG ──────────────────────────────────
ICONS: dict[str, str] = {
    # ---- molecular entities ------------------------------------------------
    "metabolite": '<circle cx="8" cy="9.5" r="2"/><circle cx="15" cy="13.5" r="2"/>'
                  '<path d="M9.7 10.7l3.6 2.1M15 11.7V8.5M15 8.5l1.8-1"/>',
    "glucose": '<path d="M12 5l4.5 2.6v5.2L12 15.4 7.5 12.8V7.6z"/>'
               '<path d="M12 5V3M16.5 7.6l1.8-1M16.5 12.8l1.8 1M7.5 12.8l-1.8 1"/>',
    "chemical": '<circle cx="8" cy="8" r="1"/><circle cx="13" cy="7" r="1"/><circle cx="17" cy="9" r="1"/>'
                '<circle cx="10" cy="13" r="1"/><circle cx="15" cy="14" r="1"/><circle cx="18" cy="16" r="1"/>'
                '<circle cx="7" cy="17" r="1"/><circle cx="12" cy="18" r="1"/>',
    "dna": '<path d="M8 3c0 4 8 5 8 9s-8 5-8 9"/><path d="M16 3c0 4-8 5-8 9s8 5 8 9"/>'
           '<path d="M10.4 6.2h3.2M9.4 8.6h5.2M9.4 15.4h5.2M10.4 17.8h3.2"/>',
    "gene": '<path d="M3 10h12M3 14h12"/><path d="M15 8l4 4-4 4"/>'
            '<path d="M6 10v4M9 10v4"/>',
    "rna": '<path d="M8 3c0 4 6 5 6 9s-6 5-6 9"/>'
           '<path d="M9.5 6h3M8.6 9h4.2M8.6 15h4.2M9.5 18h3"/>',
    "chromatin": '<path d="M3 12h3.5M9.5 12h5M17.5 12H21"/>'
                 '<circle cx="8" cy="12" r="2.3"/><circle cx="16" cy="12" r="2.3"/>'
                 '<path d="M7 11l2 2M9 11l-2 2M15 11l2 2M17 11l-2 2"/>',
    "chromosome": '<path d="M7.5 4C9 8 9 8 7.5 12 6 16 6 16 7.5 20M16.5 4C15 8 15 8 16.5 12 18 16 18 16 16.5 20"/>'
                  '<path d="M9 12h6"/>',
    "protein": '<path d="M9 4.5c-3.2.6-5.2 3.2-4.3 6.2.7 2.3-1 4.6 1.4 6.3 2.3 1.6 6.8 1.7 8.4-1 1.6-2.6 2-6.4-.6-8.4-1.9-1.5-2-3.6-4.9-3.1z"/>'
               '<path d="M9.5 11c1.2-1.2 3.8-1.2 5 0"/><path d="M10 14.5c1-.8 3-.8 4 0"/>',
    "enzyme": '<path d="M15 5A7 7 0 1 0 19 15"/><path d="M14.5 10.5l3-1.2 1.2 3-3 1.2z"/>',
    "amino_acid": '<circle cx="12" cy="12" r="1.7"/><path d="M12 10.3V6.5M7.5 14l3-1.6M16.5 14l-3-1.6"/>'
                  '<path d="M12 6.5h3M5.5 15l-1.5 1.2M18.5 15l1.5 1.2"/>',
    "lipid": '<circle cx="12" cy="6" r="2"/><path d="M11 8v10M13 8v10"/>',
    "membrane": '<circle cx="6" cy="6.2" r="1.35"/><circle cx="12" cy="6.2" r="1.35"/><circle cx="18" cy="6.2" r="1.35"/>'
                '<path d="M5.3 7.5v3.4M6.7 7.5v3.4M11.3 7.5v3.4M12.7 7.5v3.4M17.3 7.5v3.4M18.7 7.5v3.4"/>'
                '<circle cx="6" cy="17.8" r="1.35"/><circle cx="12" cy="17.8" r="1.35"/><circle cx="18" cy="17.8" r="1.35"/>'
                '<path d="M5.3 16.5v-3.4M6.7 16.5v-3.4M11.3 16.5v-3.4M12.7 16.5v-3.4M17.3 16.5v-3.4M18.7 16.5v-3.4"/>',
    "ribosome": '<path d="M4.5 9.2c0-2.7 3.4-4.2 7.5-4.2s7.5 1.5 7.5 4.2-3.4 3.8-7.5 3.8-7.5-1.1-7.5-3.8z"/>'
                '<path d="M6.5 15.4c0-2 2.5-3.1 5.5-3.1s5.5 1.1 5.5 3.1-2.5 3-5.5 3-5.5-1-5.5-3z"/>'
                '<path d="M2.5 12.6h19"/>',
    "mitochondria": '<path d="M4 12a8 5 0 0 0 16 0 8 5 0 0 0-16 0z"/>'
                    '<path d="M7 9.3c2.2 2.7 2.2 2.7 0 5.4M11 8.6c2.2 3.4 2.2 3.4 0 6.8M15 8.6c-2.2 3.4-2.2 3.4 0 6.8"/>',
    "organelle": '<path d="M12 4a8 8 0 1 0 .1 0z"/><circle cx="9.5" cy="10" r="1.3"/><circle cx="14" cy="14" r="1.3"/>',
    "nucleus": '<path d="M12 4a8 8 0 1 0 .1 0z"/><circle cx="12" cy="12" r="2.3"/>'
               '<path d="M12 4v1.6M20 12h-1.6M12 20v-1.6M4 12h1.6"/>',
    "cytoplasm": '<path d="M12 4a8 8 0 1 0 .1 0z"/><circle cx="9" cy="10" r=".9"/><circle cx="14.5" cy="9.5" r=".9"/>'
                 '<circle cx="11" cy="14.5" r=".9"/><circle cx="15.5" cy="14" r=".9"/>',
    "cell": '<path d="M12 3.5a8.5 8 0 1 0 .1 0z"/><circle cx="13" cy="13" r="2.4"/>',
    "transporter": '<path d="M3 8h6M15 8h6M3 16h6M15 16h6"/><path d="M9 6v12M15 6v12"/>'
                   '<path d="M12 7v10M12 7l-1.4 1.6M12 7l1.4 1.6"/>',
    "atp": '<path d="M2.6 12l1.9-1.1 1.9 1.1v2.2l-1.9 1.1-1.9-1.1z"/><path d="M6.4 12h1.3"/>'
           '<path d="M9.2 10.6l1.8 1.3-.7 2.1H8.1l-.7-2.1z"/><path d="M11.2 12.9h1.2"/>'
           '<circle cx="14" cy="12.7" r="1.4"/><path d="M15.4 12.7h1"/><circle cx="17.8" cy="12.7" r="1.4"/>'
           '<path d="M19.2 12.7h1"/><circle cx="21.6" cy="12.7" r="1.4"/>',
    "matrix": '<path d="M3 8c3 1.5 6-1 9 .5s5 1.8 6 .2M3 15c3 1.5 6-1 9 .5s5 1.8 6 .2"/>'
              '<path d="M7 4v16M13 3.5v16.5M18 5v14"/>',
    "biomass": '<circle cx="9" cy="10" r="3.1"/><circle cx="15.5" cy="10.5" r="2.8"/><circle cx="12" cy="15.5" r="3"/>',

    # ---- physical / abstract quantities ------------------------------------
    "mechanical": '<rect x="13" y="8" width="7" height="8" rx="1"/>'
                  '<path d="M3 12h9M9 9l3 3-3 3"/>',
    "electrical": '<path d="M7 4v16M17 4v16"/><path d="M9.4 9h2.2M10.5 7.9v2.2"/>'
                  '<path d="M12.4 15h2.2"/><path d="M12.8 12h3.4M15 10.8l1.4 1.2-1.4 1.2"/>',
    "thermal": '<path d="M12 4a2 2 0 0 1 2 2v8a4 4 0 1 1-4 0V6a2 2 0 0 1 2-2z"/>'
               '<circle cx="12" cy="18" r="2" fill="{C}" stroke="none"/><path d="M12 8v6"/>',
    "signaling": '<circle cx="5" cy="12" r="1.5" fill="{C}" stroke="none"/>'
                 '<path d="M8 12a3 3 0 0 0-3-3M10.2 12a5.2 5.2 0 0 0-5.2-5.2"/>'
                 '<path d="M15 8.5v7M15 8.5a2.4 2.4 0 0 1 4 1.6M15 15.5a2.4 2.4 0 0 0 4-1.6"/>',
    "viability": '<path d="M12 4a7 7 0 1 0 .1 0z"/>'
                 '<path d="M5.4 13.5a7 7 0 0 0 13.2 0z" fill="{C}" stroke="none"/><circle cx="12" cy="9.6" r="1.1"/>',
    "fitness": '<path d="M3 19c2-1 3.2-9 6-9 2.4 0 2.8 5 5 5 2 0 3.5-6 7-7"/>'
               '<path d="M9 10V5M7.6 6.4L9 5l1.4 1.4"/>',
    "entropy": '<path d="M4 7h4M4 11h4M4 15h4"/>'
               '<circle cx="13" cy="7" r=".9"/><circle cx="18" cy="9" r=".9"/><circle cx="14.5" cy="12.5" r=".9"/>'
               '<circle cx="19" cy="15" r=".9"/><circle cx="13" cy="17" r=".9"/>',
    "growth_rate": '<path d="M4 18c3.5 0 4.5-7 8.5-9.5C15.5 6.6 17.5 5.4 20 5"/>'
                   '<path d="M16 5h4v4"/>',
    "shape": '<path d="M6.5 8c-2 3.5 0 8 4 9s9-1.5 8.5-6.5S15 4 11.5 5.2 8 5.5 6.5 8z"/>'
             '<path d="M9 12h6"/>',
    "volume": '<path d="M12 4l7 4v8l-7 4-7-4V8z"/><path d="M12 4v16M5 8l7 4 7-4"/>',
    "area": '<rect x="5" y="5" width="14" height="14" rx="1" stroke-dasharray="2.5 2.5"/>',
    "location": '<path d="M4 12h16M12 4v16"/><circle cx="15" cy="9" r="1.7" fill="{C}" stroke="none"/>',

    # ---- process archetypes -------------------------------------------------
    "metabolism": '<circle cx="12" cy="4.6" r="1.25"/><circle cx="19.4" cy="12" r="1.25"/>'
                  '<circle cx="12" cy="19.4" r="1.25"/><circle cx="4.6" cy="12" r="1.25"/>'
                  '<path d="M13.4 5.4a7.4 7.4 0 0 1 4.7 5"/><path d="M18.3 13.5a7.4 7.4 0 0 1-4.8 4.9"/>'
                  '<path d="M10.5 18.3a7.4 7.4 0 0 1-4.8-4.9"/><path d="M5.7 10.4a7.4 7.4 0 0 1 4.7-5"/>'
                  '<path d="M16.6 9.4l1.5 1.1.1-1.9"/>',
    "transcription": '<path d="M3 17h18M3 15h6M14 15h7"/>'
                     '<path d="M9 15a3.2 3 0 0 1 5 0v2H9z"/><path d="M11.5 14.8c0-3 3-3 3-6.5"/>',
    "translation": '<path d="M3 16h18"/><path d="M7.5 12.5a4 3 0 0 1 8 0v3h-8z"/>'
                   '<path d="M15.5 13c1 1.5 3 1 4 .4"/><circle cx="20" cy="12" r="1"/><circle cx="18" cy="9.5" r="1"/>',
    "replication": '<path d="M3 12h8"/><path d="M11 12c3-2.8 6-2.8 9-4M11 12c3 2.8 6 2.8 9 4"/>'
                   '<path d="M13.5 9h4M13.5 15h4"/>',
    "diffusion": '<circle cx="5" cy="12" r="1.5" fill="{C}" stroke="none"/>'
                 '<circle cx="10" cy="9" r="1.1"/><circle cx="11" cy="15" r="1.1"/>'
                 '<circle cx="15" cy="11" r=".9"/><circle cx="16" cy="16" r=".9"/><circle cx="19" cy="8" r=".7"/><circle cx="20" cy="14" r=".7"/>',
    "reaction": '<circle cx="6" cy="12" r="2.2"/><circle cx="18" cy="12" r="2.2"/>'
                '<path d="M9 12h6M13 10l2 2-2 2"/>',
    "transport": '<path d="M8 4v16M16 4v16"/><circle cx="12" cy="7.5" r="1.6"/>'
                 '<path d="M12 10.5v6M10.4 14l1.6 2.5 1.6-2.5"/>',
    "containment": '<path d="M12 4a8 8 0 1 0 .1 0z"/>'
                   '<circle cx="12" cy="4" r="1.15"/><circle cx="20" cy="12" r="1.15"/><circle cx="12" cy="20" r="1.15"/><circle cx="4" cy="12" r="1.15"/>'
                   '<circle cx="6.3" cy="6.3" r="1.15"/><circle cx="17.7" cy="6.3" r="1.15"/><circle cx="17.7" cy="17.7" r="1.15"/><circle cx="6.3" cy="17.7" r="1.15"/>',
    "division": '<path d="M8.5 12a3.8 3.8 0 1 0 .1 0z"/><path d="M15.5 12a3.8 3.8 0 1 0 .1 0z"/>'
                '<path d="M11.7 9.4c1.1 1.6 1.1 3.6 0 5.2M12.3 9.4c-1.1 1.6-1.1 3.6 0 5.2"/>',
    "mutation": '<path d="M4 12h16"/><path d="M8 10v4M16 10v4"/>'
                '<circle cx="12" cy="12" r="2.4"/><path d="M10.8 10.8l2.4 2.4M13.2 10.8l-2.4 2.4"/>',
    "selection": '<path d="M4 5h16l-6 7v6l-4 2v-8z"/>',
    "toggle": '<rect x="3" y="8" width="18" height="8" rx="4"/><circle cx="16" cy="12" r="2.6" fill="{C}" stroke="none"/>',
    "mechanism": '<circle cx="9" cy="12" r="3"/><circle cx="9" cy="12" r="1"/>'
                 '<path d="M9 8.2V6.6M9 17.4v-1.6M5.2 12H3.6M13 12h1.6M6.4 9.4L5.2 8.2M11.6 9.4l1.2-1.2"/>'
                 '<circle cx="17" cy="15" r="2"/><path d="M17 12.4v-1M17 18v-1"/>',
    "barrier": '<path d="M4 8h16M4 12h16M4 16h16"/><path d="M9 8v4M15 8v4M12 12v4"/>',
    "copies": '<rect x="4" y="7" width="9" height="11" rx="1"/>'
              '<path d="M16 6v9a1 1 0 0 1-1 1H8"/>',
    "port": '<circle cx="6" cy="12" r="2"/><path d="M8 12h9"/><path d="M17 9.5v5"/>',
    "biofilm": '<path d="M3 18h18"/><path d="M7 18a2.4 2.4 0 1 1 4.8 0M12 18a2.4 2.4 0 1 1 4.8 0"/>'
               '<path d="M4.5 18a2 2 0 1 1 4 0M15.2 18a2 2 0 1 1 4 0"/>',
    "surface": '<path d="M3 15h18"/><path d="M5 15l-2 3M9 15l-2 3M13 15l-2 3M17 15l-2 3M21 15l-2 3"/>',

    # ---- environment / ports of the physical world -------------------------
    "environment": '<path d="M12 3a9 9 0 1 0 .1 0z"/><path d="M3.5 10h17M4 15h16M12 3c-3 3-3 15 0 18M12 3c3 3 3 15 0 18"/>',
}


# ── name -> concept resolution (ordered; first hit wins) ─────────────────────
_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r, re.I), c) for r, c in [
        # molecular entities
        (r"chromatin|nucleosome", "chromatin"),
        (r"chromosome", "chromosome"),
        (r"\bdna\b", "dna"),
        (r"gene", "gene"),
        (r"\b(m?rna|transcript)\b", "rna"),
        (r"ribosom|subunit", "ribosome"),
        (r"mitochond", "mitochondria"),
        (r"nucleolus|nucleus|\bnuc\b", "nucleus"),
        (r"cytoplasm|\bcyto\b", "cytoplasm"),
        (r"organelle|secretory|vesicle|\brib\b", "organelle"),
        (r"membrane|bilayer|\bmem\b|boundary|lipid_monomer", "membrane"),
        (r"\blipid", "lipid"),
        (r"chnl|channel", "transporter"),
        (r"transmembrane_transport|transporter|uptake|transport_flux|nutrient_exchange|permeab|\btransport\b", "transporter"),
        (r"amino", "amino_acid"),
        (r"enzyme|catalyst|cofactor", "enzyme"),
        (r"histone|protein|nucleic_acid", "protein"),
        (r"glucose|acetate|\bsugar", "glucose"),
        (r"atp|\benergy\b|adenosine", "atp"),
        (r"ecm_secretion", "reaction"),
        (r"matrix|collagen|fibronectin|\becm\b", "matrix"),
        (r"biomass|\bmass\b|aggregate", "biomass"),
        (r"nutrient|substrate|product|metabolite|monomer|secretion|inflow|outflow", "metabolite"),
        (r"concentration|chemical", "chemical"),
        # physical / abstract
        (r"mechanical|traction|\bforce\b|motil|stress", "mechanical"),
        (r"electric|bioelectric|voltage|current", "electrical"),
        (r"thermal|temperature|\bheat\b", "thermal"),
        (r"signal", "signaling"),
        (r"viability|viable", "viability"),
        (r"fitness|objective", "fitness"),
        (r"entropy", "entropy"),
        (r"growth", "growth_rate"),
        (r"shape|morpholog", "shape"),
        (r"\bvolume\b", "volume"),
        (r"\barea\b", "area"),
        (r"location|position|\bfield\b", "location"),
        # process archetypes
        (r"transcription", "transcription"),
        (r"translation", "translation"),
        (r"replicat|template", "replication"),
        (r"metabol|coarse", "metabolism"),
        (r"reaction_diffusion|diffusion", "diffusion"),
        (r"reaction|autocataly|production_degrad|expression", "reaction"),
        (r"containment|self_assembl|aggregation|assembly", "containment"),
        (r"divide|division", "division"),
        (r"variation|mutation", "mutation"),
        (r"selection", "selection"),
        (r"grain_selector|\bcontrol\b|selector|switch|grain", "toggle"),
        (r"mechanism|fine_process", "mechanism"),
        (r"molecular", "chemical"),
        (r"barrier", "barrier"),
        (r"copies|copy", "copies"),
        (r"interface|port", "port"),
        (r"biofilm|colony", "biofilm"),
        (r"surface|attachment|attached|adhesion", "surface"),
        # cells / environment
        (r"biofilm_mass|\bcells\b|cell_count|cell_population", "biomass"),
        (r"environ", "environment"),
        (r"daughter|cell|protocell", "cell"),
    ]
]


def resolve(name: str) -> str | None:
    for rx, concept in _RULES:
        if rx.search(name or ""):
            return concept
    return None


def figure(node_name: str, is_process: bool) -> str | None:
    """Full ``<svg>`` for a node, coloured by role, or ``None`` if unmapped."""
    concept = resolve(node_name)
    if concept is None or concept not in ICONS:
        return None
    return wrap(ICONS[concept], INDIGO if is_process else TEAL)
