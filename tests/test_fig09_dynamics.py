"""Fig 9 · division as a place-graph rewrite, asserted from the trajectory.

The runnable fig09-rewrite composite (driven via build_fig10_division, the same
builder the fig-09 snapshot script uses — cycle=3, the composite's default) runs a
repeating cell cycle over a colony `tree[node]`: a cell replicates its chromosome,
then divides into two daughters, and repeats. This test asserts the figure's
principle FROM THE EMITTED TRAJECTORY:

  (a) the cell count increases over the run — division actually happened;
  (b) replication precedes division — the chromosome count doubles before the cell
      count does (DNA is copied, then partitioned to daughters);
  (c) division is a CONSERVING, EQUIPARTITIONING rewrite — at each division event
      the boundary count exactly doubles, total DNA is conserved across the split
      (sum over daughters == parent total, no DNA created or destroyed), and each
      daughter inherits exactly half (equipartition of the parent's stores). This
      is the paper's Fig-division-b claim: division "partitions state variables
      such as DNA … into two cells."

The composite is a pure clock-driven place-graph rewrite with NO randomness, so
every value below is deterministic and pinned exactly.

Mirrors the trajectory-driven style of tests/test_fig10_topology.py.
"""
from __future__ import annotations

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.fig10_rewrite import build_fig10_division

CYCLE, N_STEPS = 3.0, 12  # matches fig09-rewrite.composite.json


def _colony_counts(colony: dict):
    """(#cells, #chromosomes, total dna, [per-cell dna]) for one emitted colony frame."""
    n_cells = n_chrom = 0
    dna = 0.0
    per_cell_dna = []
    for ck, cell in colony.items():
        if ck.startswith("_") or not isinstance(cell, dict) or cell.get("_control") != "cell":
            continue
        n_cells += 1
        cell_dna = 0.0
        contents = cell.get("contents", cell)
        for v in contents.values():
            if isinstance(v, dict) and v.get("_control") == "chromosome":
                n_chrom += 1
                dc = v.get("contents", {})
                d = float(dc.get("dna", 0.0)) if isinstance(dc, dict) else 0.0
                dna += d
                cell_dna += d
        per_cell_dna.append(cell_dna)
    return n_cells, n_chrom, dna, per_cell_dna


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


def test_division_conserves_and_equipartitions_dna():
    """At every division event the boundary count exactly DOUBLES, total DNA is
    CONSERVED across the rewrite (nothing created or destroyed), and each daughter
    inherits exactly HALF of a parent cell's DNA — the caption-b claim that
    division "partitions state variables such as DNA … into two cells."
    """
    traj = _trajectory()
    cells = [c[0][0] for c in traj]
    dna = [c[0][2] for c in traj]
    per_cell = [c[0][3] for c in traj]

    division_ticks = [i for i in range(1, len(traj)) if cells[i] > cells[i - 1]]
    assert len(division_ticks) >= 2              # at least two division events (1→2, 2→4)

    for i in division_ticks:
        # one boundary becomes two: the cell count exactly doubles.
        assert cells[i] == 2 * cells[i - 1]
        # conservation: total DNA is unchanged across the division rewrite.
        assert dna[i] == dna[i - 1]
        # equipartition: every daughter carries the same DNA …
        daughters = per_cell[i]
        assert all(d == daughters[0] for d in daughters)
        # … and it is exactly half of a pre-division parent cell's DNA.
        parent_dna = dna[i - 1] / cells[i - 1]
        assert daughters[0] == parent_dna / 2.0
