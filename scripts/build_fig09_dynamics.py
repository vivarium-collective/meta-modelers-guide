#!/usr/bin/env python
"""Render Fig 9's time-series demonstration: division as quantities over time.

Fig 9b's principle is that cell division is a genuine runtime place-graph rewrite:
a cell replicates its chromosome, then divides into two daughters, and repeats. The
fig-09 snapshot sequence shows the TOPOLOGY at three stages; this shows the same
rewrite as QUANTITIES OVER TIME. It RUNS the runnable fig09-rewrite composite (via
meta_modelers_guide.fig10_rewrite.build_fig10_division — the same builder the fig-09
snapshot script drives, cycle=3, the composite's default) for the composite's
default_n_steps and gathers the whole-colony trajectory from the emitter:

  * cell count          — steps up 1 → 2 → 4 as each cell divides;
  * chromosome count    — doubles at each replication (before the following division);
  * total DNA           — the summed dna over all chromosomes, tracking replication.

The signature reads as a staircase: DNA/chromosomes double at replication, THEN the
cell count doubles one half-cycle later at division — replication precedes division,
over and over. Writes a labelled two-panel PNG to the fig-09 study visualizations.

    python scripts/build_fig09_dynamics.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.fig10_rewrite import build_fig10_division

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "workspace" / "studies" / "fig-09" / "visualizations" / "fig09-dynamics.png"

CYCLE, N_STEPS = 3.0, 12  # matches fig09-rewrite.composite.json (cycle default, default_n_steps)

# palette (matches the study figures' teal / accent family)
C_CELLS, C_CHROM, C_DNA = "#0b7a75", "#b4531f", "#4b5bd6"


def _colony_counts(colony: dict):
    """(#cells, #chromosomes, total dna) for one emitted colony frame."""
    n_cells = n_chrom = 0
    dna = 0.0
    for ck, cell in colony.items():
        if ck.startswith("_") or not isinstance(cell, dict) or cell.get("_control") != "cell":
            continue
        n_cells += 1
        contents = cell.get("contents", cell)
        for k, v in contents.items():
            if isinstance(v, dict) and v.get("_control") == "chromosome":
                n_chrom += 1
                dc = v.get("contents", {})
                dna += float(dc.get("dna", 0.0)) if isinstance(dc, dict) else 0.0
    return n_cells, n_chrom, dna


def _run():
    core = build_core()
    sim = Composite(build_fig10_division(cycle=CYCLE, interval=1.0), core=core)
    sim.run(N_STEPS)
    return gather_emitter_results(sim)[("emitter",)]


def main() -> None:
    rows = _run()
    t = [float(r["time"]) for r in rows]
    counts = [_colony_counts(r["colony"]) for r in rows]
    cells = [c[0] for c in counts]
    chrom = [c[1] for c in counts]
    dna = [c[2] for c in counts]

    # ── the load-bearing claim: division happened — the cell count grew ─────────
    assert cells[-1] > cells[0], "cell count should increase (division occurred)"
    assert max(chrom) > chrom[0], "chromosomes should replicate before division"

    # ── figure ──────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 1, figsize=(10, 7.5), sharex=True)
    fig.suptitle("Fig 9 — division as a place-graph rewrite, over time",
                 fontsize=15, fontweight="bold")
    fig.text(0.5, 0.925,
             "One cell replicates its chromosome (DNA doubles), THEN divides into two "
             "daughters (cell count doubles) — a repeating cell cycle.",
             ha="center", fontsize=10, color="#444")

    ax = axes[0]
    ax.step(t, cells, where="post", color=C_CELLS, lw=2.6, marker="o", ms=5)
    ax.set_title("Cell count  (doubles at each division: 1 → 2 → 4)", fontsize=11)
    ax.set_ylabel("number of cells")
    ax.set_yticks(sorted(set(cells)))
    ax.grid(alpha=0.25)

    ax = axes[1]
    ax.step(t, chrom, where="post", color=C_CHROM, lw=2.4, marker="s", ms=4,
            label="chromosome count")
    ax.plot(t, dna, color=C_DNA, lw=2.0, marker="o", ms=3, ls="--",
            label="total DNA (summed over chromosomes)")
    ax.set_title("Chromosome replication  (doubles ~one half-cycle BEFORE each division)",
                 fontsize=11)
    ax.set_ylabel("count / DNA")
    ax.set_xlabel("time")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.25)

    fig.tight_layout(rect=(0, 0, 1, 0.9))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150)
    plt.close(fig)
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  cells       {cells[0]} → {cells[-1]}")
    print(f"  chromosomes {chrom[0]} → {max(chrom)} (peak)")
    print(f"  total DNA   {dna[0]:.1f} → {max(dna):.1f} (peak)")


if __name__ == "__main__":
    main()
