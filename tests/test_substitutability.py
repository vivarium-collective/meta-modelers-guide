# tests/test_substitutability.py
"""Interface substitutability -- the paper's central thesis, run.

Paper (section 2 / Cellular interface): "This substitutability is not only a
software convenience. It allows *the interface itself to become the object of
comparison: different mechanisms may realize the same externally observable
relation*." And: "different internal organizations may sometimes be represented
through the same coarse-grained interface when they preserve the interaction
variables relevant to that description."

Here we demonstrate exactly that. The flagship cell's INTERNAL metabolism is
swapped from constraint-based dynamic-FBA (cobra e_coli_core, O2-capped) to a
lumped Michaelis-Menten / Monod metabolism (no cobra) BEHIND THE IDENTICAL
`CpmCellField` ports. The MM params are tuned to preserve the interaction
variables, and we assert the interface-level observables -- final biomass, total
acetate secreted, CPM volume/growth, net glucose depletion -- agree within a
stated tolerance. Two different internal organizations, one coarse-grained
cell<->field interface.

The MM path needs no cobra, so `test_mm_mechanism_runs_without_cobra` exercises
substitutability's payoff (the box runs where the original could not). The
head-to-head comparison additionally needs the dFBA baseline, so it importorskips
cobra and compares only where both are available.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pytest
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

pytest.importorskip("cpm")           # the CPM engine (absent from base CI)
pytest.importorskip("spatio_flux")   # the diffusion-advection field framework

COMP_DIR = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
COMP_DFBA = COMP_DIR / "single-cell-in-a-field.composite.json"
COMP_MM = COMP_DIR / "single-cell-in-a-field-mm.composite.json"


def _run(comp_path, ticks=20):
    """Run a flagship-family composite; return the interface-level observables that
    define the coarse-grained cell<->field relation (the ports are identical across
    mechanisms, so these are the SAME observables for both)."""
    core = build_core()
    state = json.loads(comp_path.read_text())["state"]
    comp = Composite({"state": state}, core=core)
    glc0 = float(np.asarray(comp.state["fields"]["glucose"]).sum())
    comp.run(ticks)
    obs = comp.state["obs"]
    return {
        "biomass": float(obs["biomass"]),
        "volume": float(obs["volume"]),
        "acetate": float(np.asarray(comp.state["fields"]["acetate"]).sum()),
        "glc_depleted": glc0 - float(np.asarray(comp.state["fields"]["glucose"]).sum()),
    }


def test_mm_mechanism_runs_without_cobra():
    """The MM mechanism realizes the same cell<->field interface with NO cobra: the
    cell still grows (biomass + CPM volume), secretes acetate, and depletes glucose
    -- the qualitative interface behavior the dFBA flagship produces. This is the
    substitutability payoff: the same ports, a different (cobra-free) internal box."""
    r = _run(COMP_MM)
    assert r["biomass"] > 0.1        # metabolized and grew (biomass0 = 0.1)
    assert r["volume"] > 40.0        # CPM cell grew in lattice pixels
    assert r["acetate"] > 1.0        # secreted an acetate plume (overflow)
    assert r["glc_depleted"] > 0.0   # acted as a net glucose sink


def test_interface_observables_substitutable():
    """The paper's thesis, asserted: two different internal organizations (dFBA vs
    MM) realize the SAME coarse-grained cell<->field interface. Directional match
    (both grow, secrete, deplete) plus quantitative agreement of every interface-level
    observable within tolerance -- the MM params were tuned to preserve the interaction
    variables, so this is 'same coarse-grained relation', not identical internals."""
    pytest.importorskip("cobra")  # the dFBA baseline needs cobra; compare only if present
    dfba = _run(COMP_DFBA)
    mm = _run(COMP_MM)

    # Directional / qualitative: both mechanisms drive the same interface regime.
    for r in (dfba, mm):
        assert r["biomass"] > 0.1
        assert r["volume"] > 40.0
        assert r["acetate"] > 1.0
        assert r["glc_depleted"] > 0.0

    # Quantitative: each interface observable agrees within tolerance. Observed
    # divergences at the tuned params are ~7-10% (biomass/volume) with acetate near
    # exact and glucose depletion ~6%; a 30% band leaves honest headroom.
    TOL = 0.30
    for key in ("biomass", "volume", "acetate", "glc_depleted"):
        a, b = dfba[key], mm[key]
        rel = abs(a - b) / abs(a)
        assert rel < TOL, (
            f"interface observable {key!r} diverges {rel:.0%} "
            f"(dFBA={a:.4g}, MM={b:.4g}) -- exceeds substitutability tolerance {TOL:.0%}")
