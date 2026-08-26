"""Fig 9 · division as a place-graph rewrite, asserted from the trajectory.

The runnable fig09-rewrite composite (driven via build_fig10_division, the same
builder the fig-09 snapshot script uses — cycle=3, the composite's default) runs a
repeating cell cycle over a colony `tree[node]`: a cell replicates its chromosome,
then divides into two daughters, and repeats. This test asserts the figure's
principle FROM THE EMITTED TRAJECTORY:

  (a) the cell count increases over the run — division actually happened;
  (b) replication precedes division — the chromosome count doubles before the cell
      count does (DNA is copied, then partitioned to daughters).

Mirrors the trajectory-driven style of tests/test_fig10_topology.py.
"""
from __future__ import annotations

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.fig10_rewrite import build_fig10_division

CYCLE, N_STEPS = 3.0, 12  # matches fig09-rewrite.composite.json


def _colony_counts(colony: dict):
    """(#cells, #chromosomes, total dna) for one emitted colony frame."""
    n_cells = n_chrom = 0
    dna = 0.0
    for ck, cell in colony.items():
        if ck.startswith("_") or not isinstance(cell, dict) or cell.get("_control") != "cell":
            continue
        n_cells += 1
        contents = cell.get("contents", cell)
        for v in contents.values():
            if isinstance(v, dict) and v.get("_control") == "chromosome":
                n_chrom += 1
                dc = v.get("contents", {})
                dna += float(dc.get("dna", 0.0)) if isinstance(dc, dict) else 0.0
    return n_cells, n_chrom, dna


def _trajectory():
    core = build_core()
    sim = Composite(build_fig10_division(cycle=CYCLE, interval=1.0), core=core)
    sim.run(N_STEPS)
    rows = gather_emitter_results(sim)[("emitter",)]
    return [(_colony_counts(r["colony"]), float(r["time"])) for r in rows]


def test_cell_count_increases_division_happened():
    traj = _trajectory()
    cells = [c[0][0] for c in traj]
    assert cells[0] == 1                       # one founder cell
    assert cells[-1] > cells[0]                 # division occurred
    assert cells[-1] >= 4                       # 1 → 2 → 4 over two cycles
    # cells are only ADDED by division — the count never falls.
    assert cells == sorted(cells)


def test_replication_precedes_division():
    traj = _trajectory()
    cells = [c[0][0] for c in traj]
    chrom = [c[0][1] for c in traj]
    # the chromosome count first doubles (replication) while the cell count is still 1,
    # i.e. DNA is copied BEFORE the cell partitions it into two daughters.
    first_replicate = next(i for i in range(len(chrom)) if chrom[i] > chrom[0])
    first_divide = next(i for i in range(len(cells)) if cells[i] > cells[0])
    assert first_replicate < first_divide
    assert cells[first_replicate] == 1          # cell hasn't divided yet at replication


def test_total_dna_doubles_at_replication():
    traj = _trajectory()
    dna = [c[0][2] for c in traj]
    assert dna[0] == 1.0
    assert max(dna) >= 4.0                       # doubles each replication: 1 → 2 → 4
