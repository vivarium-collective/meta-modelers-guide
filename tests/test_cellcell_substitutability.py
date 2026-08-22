# tests/test_cellcell_substitutability.py
"""Interface substitutability at the CELL-CELL (colony) level -- the paper's central
thesis, run one composition level up from the single-cell flagship.

The flagship study already demonstrates substitutability at the single-cell metabolism
level: `single-cell-in-a-field` (dynamic-FBA) vs `single-cell-in-a-field-mm` (lumped
Michaelis-Menten) behind byte-identical `CpmCellField` ports (tests/test_substitutability.py).
This module lifts that SAME kind of swap to the multi-cell colony interface: the
competition colony `cellcell-compete` (two glucose competitors on one shared field,
each running its own per-cell dFBA on e_coli_core) vs `cellcell-compete-mm` -- the
identical composite with each cell's INTERNAL metabolism swapped from dFBA to a lumped,
cobra-free Michaelis-Menten metabolism (`mechanism: mm`) BEHIND THE BYTE-IDENTICAL
`CpmColonyField` ports.

Each competitor keeps its OWN saturating glucose uptake v = glucose_vmax*glc/(glucose_km+glc)
-- the very kinetics the dFBA path MM-limits its exchange bound with -- so the vmax
10-vs-4 asymmetry that drives competitive exclusion is preserved by construction; growth
becomes a fixed biomass yield (mm_yield*v) and acetate a fixed overflow fraction
(mm_overflow*v). The mm_* params are tuned to preserve the interaction variables, and we
assert the colony's interface-level observables -- per-cell + total biomass, the
competition ratio, total CPM lattice volume, the field's acetate plume and net glucose
depletion -- agree within a stated tolerance. Two different internal organizations per
cell, one coarse-grained colony<->field interface.

The MM path needs no cobra, so `test_mm_colony_runs_without_cobra` exercises
substitutability's payoff (the colony runs where the dFBA original could not -- cobra is
blocked for that test). The head-to-head comparison additionally needs the dFBA baseline,
so it importorskips cobra and compares only where both are available.
"""
from __future__ import annotations
import builtins
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

pytest.importorskip("cpm")           # the CPM engine (absent from base CI)
pytest.importorskip("spatio_flux")   # the diffusion-advection field framework

COMP_DIR = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
COMP_DFBA = COMP_DIR / "cellcell-compete.composite.json"
COMP_MM = COMP_DIR / "cellcell-compete-mm.composite.json"

# Colony-level substitutability tolerance. Observed divergences at the tuned params are
# ~6% or below on every observable (biomass id 1 ~6.1%, ratio ~5.9%, acetate/volume/
# glucose < 1%); a 15% band leaves honest headroom without being loose.
TOL = 0.15


def _run(comp_path, ticks=20):
    """Run a cellcell-colony composite; return the colony interface-level observables
    that define the coarse-grained colony<->field relation (the ports are byte-identical
    across mechanisms, so these are the SAME observables for both)."""
    core = build_core()
    state = json.loads(comp_path.read_text())["state"]
    comp = Composite({"state": state}, core=core)
    glc0 = float(np.asarray(comp.state["fields"]["glucose"]).sum())
    comp.run(ticks)
    obs = comp.state["obs"]
    b1 = float(obs["biomass"]["1"])
    b2 = float(obs["biomass"]["2"])
    v1 = float(obs["volume"]["1"])
    v2 = float(obs["volume"]["2"])
    return {
        "biomass_1": b1,
        "biomass_2": b2,
        "biomass_total": b1 + b2,
        "compete_ratio": b1 / b2,               # the study's headline competition relation
        "volume_total": v1 + v2,                # total CPM lattice volume
        "acetate": float(np.asarray(comp.state["fields"]["acetate"]).sum()),
        "glc_depleted": glc0 - float(np.asarray(comp.state["fields"]["glucose"]).sum()),
    }


def _colony_ports(comp_path):
    """The byte-identical-across-mechanisms interface: the CpmColonyField process's
    declared inputs/outputs wiring in the composite spec."""
    proc = json.loads(comp_path.read_text())["state"]["colony"]
    return proc["inputs"], proc["outputs"]


def test_colony_ports_are_byte_identical():
    """Substitutability's precondition: the dFBA colony and the MM colony expose the
    EXACT same `CpmColonyField` interface (same address, same input/output port wiring)
    -- only the internal mechanism behind the ports differs."""
    dfba_spec = json.loads(COMP_DFBA.read_text())["state"]["colony"]
    mm_spec = json.loads(COMP_MM.read_text())["state"]["colony"]
    assert dfba_spec["address"] == mm_spec["address"] == "local:CpmColonyField"
    assert _colony_ports(COMP_DFBA) == _colony_ports(COMP_MM), (
        "the dFBA and MM colony composites must expose byte-identical CpmColonyField ports")


def test_mm_colony_runs_without_cobra(monkeypatch):
    """The MM colony realizes the same colony<->field interface with NO cobra: both cells
    still grow (per-cell biomass + CPM volume), the field's glucose is drawn down, and an
    acetate plume is secreted -- the qualitative interface behavior the dFBA colony
    produces. This is the substitutability payoff, made genuine by blocking cobra for the
    duration: the same ports, a different (cobra-free) internal box per cell."""
    real_import = builtins.__import__

    def _blocked(name, *args, **kwargs):
        if name == "cobra" or name.startswith("cobra."):
            raise ImportError("cobra is blocked: the MM colony must run cobra-free")
        return real_import(name, *args, **kwargs)

    for mod in [m for m in sys.modules if m == "cobra" or m.startswith("cobra.")]:
        monkeypatch.delitem(sys.modules, mod, raising=False)
    monkeypatch.setattr(builtins, "__import__", _blocked)

    r = _run(COMP_MM)
    assert r["biomass_1"] > 1.25       # faster competitor grew off its 1.25 seed
    assert r["biomass_2"] > 1.25       # slower competitor grew too
    assert r["volume_total"] > 1000.0  # colony claimed a large share of the 3600-px lattice
    assert r["acetate"] > 1.0          # secreted an acetate plume (overflow)
    assert r["glc_depleted"] > 0.0     # the colony is a net glucose sink


def test_colony_interface_observables_substitutable():
    """The paper's thesis, asserted at the colony level: two different internal
    organizations per cell (dFBA vs MM) realize the SAME coarse-grained colony<->field
    interface. Directional match (competition direction preserved, both grow, plume +
    depletion real) plus quantitative agreement of every interface-level observable within
    tolerance -- the mm_* params were tuned to preserve the interaction variables, so this
    is 'same coarse-grained relation', not identical internals."""
    pytest.importorskip("cobra")  # the dFBA baseline needs cobra; compare only if present
    dfba = _run(COMP_DFBA)
    mm = _run(COMP_MM)

    # Directional / qualitative: both mechanisms drive the SAME competition regime --
    # the faster competitor (id 1) wins on biomass, both cells grow, field acted on.
    for r in (dfba, mm):
        assert r["biomass_1"] > r["biomass_2"]   # competition direction preserved
        assert r["compete_ratio"] > 1.5          # decisive margin, both mechanisms
        assert r["biomass_1"] > 1.25 and r["biomass_2"] > 1.25
        assert r["volume_total"] > 1000.0
        assert r["acetate"] > 1.0
        assert r["glc_depleted"] > 0.0

    # Quantitative: each colony interface observable agrees within tolerance.
    for key in ("biomass_1", "biomass_2", "biomass_total", "compete_ratio",
                "volume_total", "acetate", "glc_depleted"):
        a, b = dfba[key], mm[key]
        rel = abs(a - b) / abs(a)
        assert rel < TOL, (
            f"colony interface observable {key!r} diverges {rel:.0%} "
            f"(dFBA={a:.4g}, MM={b:.4g}) -- exceeds substitutability tolerance {TOL:.0%}")
