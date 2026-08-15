"""Biological interface types + units for the meta-modeler's-guide draft figures.

The paper (*A meta-modeler's guide to the cellular interface*) draws every port
with a **unit** — chemical flux in mol·s⁻¹, mechanical force in kg·m·s⁻² (N),
electrical current in C·s⁻¹ (A), heat transfer in J·s⁻¹ (W), growth in hr⁻¹, and
so on (Figs 4, 7). We reproduce that here as *named* scalar types so the rendered
bigraph shows a biological quantity (``chemical_flux``) on each store/port rather
than a bare ``float``.

process-bigraph 1.8.3 does **not** resolve a ``_units`` key on a scalar type
(it did in 1.4.x), so the unit itself is not carried in the type schema. Instead:

* the **type name** encodes the quantity (``chemical_flux``, ``force`` …), and
* the human-readable **unit string** lives in :data:`UNITS` and is quoted in
  every draft process's contract port description (e.g.
  ``"nutrient_uptake": "chemical flux (mol·s⁻¹)"``).

Each type inherits ``float`` so it resolves cleanly and still displays its own
name in the viewer. String-valued interface variables (structural identifiers
such as PDB/SMILES, sequences) use the base ``string`` type.
"""
from __future__ import annotations

# quantity name -> human-readable unit (SI where the paper gives one).
UNITS: dict[str, str] = {
    # physical exchange ports (Fig 4b, Fig 7b)
    "chemical_flux":   "mol·s⁻¹",
    "concentration":   "mol·L⁻¹",
    "mass":            "kg",
    "force":           "kg·m·s⁻² (N)",
    "current":         "C·s⁻¹ (A)",
    "voltage":         "V",
    "heat_flux":       "J·s⁻¹ (W)",
    "temperature":     "°C",
    "energy":          "J",
    "ph":              "pH",
    # higher-level cellular ports (Fig 4b)
    "growth_rate":     "hr⁻¹",
    "area":            "m²",
    "volume":          "m³",
    "signaling_rate":  "bits·s⁻¹",
    "objective":       "dimensionless",
    "viability":       "0–1 (in-bounds fraction)",
    # counts / dimensionless bookkeeping
    "count":           "molecules",
    "cell_count":      "cells",
    "fraction":        "dimensionless",
    "rate":            "s⁻¹",
}

# structural/string interface variables (no numeric unit).
STRING_TYPES: tuple[str, ...] = ("structure", "sequence", "identity")

# every numeric quantity resolves as a named float.
_SCALAR_SCHEMA = {"_inherit": "float"}


def type_schemas() -> dict:
    """Return the ``{name: schema}`` dict of all guide interface types."""
    schemas = {name: dict(_SCALAR_SCHEMA) for name in UNITS}
    schemas.update({name: {"_inherit": "string"} for name in STRING_TYPES})
    return schemas


def register_types(core):
    """Register the guide's biological interface types on ``core`` (idempotent).

    Uses the plural ``core.register_types({...})`` API — the singular
    ``register_type`` loop registers a name for ``access`` but NOT for the
    ``realize`` path a ``Composite`` build walks, so custom-typed store leaves
    (``{"_type": "concentration"}``) fail to resolve. The plural form registers
    on both paths. Safe to call repeatedly.
    """
    core.register_types(type_schemas())
    return core


def unit(quantity: str) -> str:
    """Return the unit string for a quantity name (``""`` if dimensionless/unknown)."""
    return UNITS.get(quantity, "")


def with_unit(quantity: str, label: str) -> str:
    """Format a contract port description as ``"<label> (<unit>)"``.

    Example: ``with_unit("chemical_flux", "nutrient uptake")`` ->
    ``"nutrient uptake (mol·s⁻¹)"``.
    """
    u = unit(quantity)
    return f"{label} ({u})" if u else label
