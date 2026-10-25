"""Fig 9 mechanistic variant — growth-, energy- and size-gated cell cycle with
nucleotide-accounted replication. The baseline (fig09-rewrite) divides on a clock
and conjures the duplicated chromosome's DNA from nowhere; here division is an
outcome of physiology and DNA is drawn from a precursor pool.

Classified by the reviewer's evidence kind (pass_if.kind). Starvation controls use
substrate ≈ 0 (the environment pool, not a float config, so the is_empty(0.0)=True
gotcha does not apply here — but we still use a tiny value for clarity).
"""
from __future__ import annotations

import copy
import json
import warnings
from pathlib import Path

import pytest
from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.handlers_fig09_mech import (
    GrowthDivisionColony, _cells, _cell_dna, _chrom,
)

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig09-mechanistic.composite.json"


def _one_cell(volume=1.0, energy=1.0, nucleotides=2.0, biomass=1.0, chromosomes=1, dna=1.0):
    contents = {}
    if chromosomes == 1:
        contents = {"chromosome": _chrom(dna)}
    else:
        contents = {f"chromosome_{i}": _chrom(dna) for i in range(chromosomes)}
    return {"_type": "tree[node]", "cell": {
        "_control": "cell", "volume": volume, "energy": energy,
        "nucleotides": nucleotides, "biomass": biomass, "generation": 0, "contents": contents}}


def _proc(**over):
    return GrowthDivisionColony(over or None, core=build_core())


def _run_composite(substrate=None, steps=None):
    spec = json.loads(COMPOSITE.read_text())
    if substrate is not None:
        spec["state"]["environment"]["substrate"]["_default"] = substrate
    sim = Composite({"state": spec["state"]}, core=build_core())
    sim.run(steps or spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


# ── structural ────────────────────────────────────────────────────────────────

def test_composite_builds_and_divides():
    """REGRESSION_PIN: fig09-mechanistic builds, runs, and grows 1→16 cells."""
    rows = _run_composite()
    assert len(rows) == 21
    assert float(rows[-1]["cell_count"]) == 16.0


# ── gated division (the core mechanistic claim) ──────────────────────────────

def test_division_is_delayed_under_starvation():
    """MECHANISTIC_ABLATION / PROSPECTIVE_PREDICTION: with no nutrient the cell
    cannot grow past the size checkpoint, so division NEVER fires — it is gated by
    growth, not clocked. Predicted before the run; verified over a long window."""
    rows = _run_composite(substrate=1e-9, steps=40)
    assert float(rows[-1]["cell_count"]) == 1.0
    assert float(rows[-1]["divisions"]) == 0.0


def test_division_requires_energy():
    """MECHANISTIC_ABLATION: a cell that is big enough and fully replicated but has
    energy < div_cost does NOT divide — the checkpoint needs energy, not just size."""
    p = _proc(div_cost=5.0)   # cost above the cell's energy
    colony = _one_cell(volume=2.0, energy=1.0, chromosomes=2)["cell"]
    state = {"colony": {"cell": colony}, "substrate": 1e-9}
    out = p.update(state, 1.0)
    assert len(_cells(out["colony"])) == 1, "divided without enough energy"


def test_division_requires_replication():
    """MECHANISTIC_ABLATION: a cell big enough and with energy but that CANNOT
    replicate (no nucleotide precursors) stays at one chromosome and does not divide
    — S-phase completion gates M-phase, and replication needs precursors."""
    p = _proc()
    colony = _one_cell(volume=2.0, energy=2.0, nucleotides=1e-9, chromosomes=1)["cell"]
    out = p.update({"colony": {"cell": colony}, "substrate": 1e-9}, 1.0)
    cells = _cells(out["colony"])
    assert len(cells) == 1, "divided without replicating"
    assert _cell_dna(cells[0][1]) < 1.5, "replicated despite no nucleotide precursors"


# ── conservation & accounting (invariants) ───────────────────────────────────

def test_replication_draws_dna_from_nucleotide_pool():
    """INVARIANT: DNA is not created from nothing — during replication the DNA
    synthesised equals the nucleotides consumed, so DNA + nucleotides is conserved
    (growth off, so the only change is the replication transfer)."""
    p = _proc()
    cell = _one_cell(volume=1.5, energy=5.0, nucleotides=2.0, chromosomes=1)["cell"]
    dna0 = _cell_dna({"contents": cell["contents"]})
    nuc0 = cell["nucleotides"]
    out = p.update({"colony": {"cell": cell}, "substrate": 1e-9}, 1.0)
    newcell = _cells(out["colony"])[0][1]
    dna1 = _cell_dna(newcell)
    nuc1 = float(newcell["nucleotides"])
    assert dna1 > dna0, "no replication happened"
    assert abs((dna1 - dna0) - (nuc0 - nuc1)) < 1e-9, "DNA made ≠ nucleotides consumed"


def test_division_conserves_every_material_partition():
    """INVARIANT: across the division rewrite, volume / nucleotides / biomass / DNA
    sum over the two daughters equals the parent's, and energy equals the parent's
    minus the one-time division cost. Nothing created or lost (growth off)."""
    p = _proc(div_cost=0.1)
    parent = _one_cell(volume=2.0, energy=2.0, nucleotides=1.6, biomass=1.4, chromosomes=2)["cell"]
    pv, pe, pn, pb = parent["volume"], parent["energy"], parent["nucleotides"], parent["biomass"]
    pdna = _cell_dna(parent)
    out = p.update({"colony": {"cell": parent}, "substrate": 1e-9}, 1.0)
    daughters = [v for _, v in _cells(out["colony"])]
    assert len(daughters) == 2, "did not divide into two"
    assert abs(sum(float(d["volume"]) for d in daughters) - pv) < 1e-9
    assert abs(sum(float(d["nucleotides"]) for d in daughters) - pn) < 1e-9
    assert abs(sum(float(d["biomass"]) for d in daughters) - pb) < 1e-9
    assert abs(sum(_cell_dna(d) for d in daughters) - pdna) < 1e-9
    assert abs(sum(float(d["energy"]) for d in daughters) - (pe - 0.1)) < 1e-9


def test_dna_equipartitions_one_chromosome_each():
    """INVARIANT: each daughter receives exactly one chromosome with equal DNA —
    the bookkeeping the baseline already had, preserved under the gated cycle."""
    p = _proc()
    parent = _one_cell(volume=2.0, energy=2.0, chromosomes=2, dna=1.0)["cell"]
    out = p.update({"colony": {"cell": parent}, "substrate": 1e-9}, 1.0)
    daughters = [v for _, v in _cells(out["colony"])]
    dnas = [_cell_dna(d) for d in daughters]
    assert len(daughters) == 2 and abs(dnas[0] - dnas[1]) < 1e-9 and abs(dnas[0] - 1.0) < 1e-9


def test_daughters_have_independent_ports_and_lineage():
    """INVARIANT: daughters are distinct nodes (unique ids) carrying the parent ref
    and an incremented generation — independent cells wired to the shared nutrient,
    not aliases of one cell."""
    p = _proc()
    parent = _one_cell(volume=2.0, energy=2.0, chromosomes=2)["cell"]
    out = p.update({"colony": {"cell": parent}, "substrate": 1e-9}, 1.0)
    keys = [k for k, _ in _cells(out["colony"])]
    daughters = [v for _, v in _cells(out["colony"])]
    assert len(set(keys)) == 2
    assert all(d.get("parent") == "cell" for d in daughters)
    assert all(int(d.get("generation", 0)) == 1 for d in daughters)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
