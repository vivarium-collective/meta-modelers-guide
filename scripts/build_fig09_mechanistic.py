#!/usr/bin/env python
"""Render Fig 9's MECHANISTIC demonstration: a growth-, energy- and size-gated cell
cycle with nucleotide-accounted replication, on the colony tree[node].

Unlike the baseline (which divides on a clock and conjures the duplicated DNA), here
division is an OUTCOME of physiology. This runs the fig09-mechanistic composite for
the aggregate time-series, and steps the process directly to reconstruct the lineage
tree and per-cell trajectories, then writes a six-panel figure:

  A  cell count over time — gated 1→2→4→8→16, full vs STARVED (division delayed)
  B  lineage tree (parent→daughter edges), nodes by generation
  C  conservative-state ledger — total volume / DNA / biomass across every rewrite (no jumps)
  D  nucleotide accounting — ΣDNA rises as ΣNucleotides is drawn down at each replication
  E  one lineage's trajectory — volume growing, chromosome count stepping at replication/division
  F  the cell cycle of one cell — V(t) with the V_rep and V_div checkpoints marked

    python scripts/build_fig09_mechanistic.py
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.handlers_fig09_mech import GrowthDivisionColony, _cells, _cell_dna, _cell_chromosomes

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig09-mechanistic.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-09" / "visualizations" / "fig09-mechanistic-dynamics.png"

C_CELLS, C_DNA, C_NUC, C_VOL, C_BM, C_STARVE = "#0b7a75", "#4b5bd6", "#b4531f", "#7a5195", "#2a9d8f", "#c0392b"


def _run_composite(substrate=None, steps=None):
    spec = json.loads(COMPOSITE.read_text())
    if substrate is not None:
        spec["state"]["environment"]["substrate"]["_default"] = substrate
    sim = Composite({"state": spec["state"]}, core=build_core())
    sim.run(steps or spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def _seed():
    return {"_type": "tree[node]", "cell": {
        "_control": "cell", "volume": 1.0, "energy": 1.0, "nucleotides": 2.0,
        "biomass": 1.0, "generation": 0,
        "contents": {"chromosome": {"_control": "chromosome", "contents": {"dna": 1.0}}}}}


def _step_snapshots(steps=20):
    """Step the process fresh, recording the full colony each tick (for lineage)."""
    cfg = json.loads(COMPOSITE.read_text())["state"]["cell_cycle"]["config"]
    p = GrowthDivisionColony(cfg, core=build_core())
    colony = _seed()
    sub = 200.0

    def norm(colony):
        return {k: {"generation": int(v.get("generation", 0)),
                    "parent": v.get("parent"),
                    "volume": float(v.get("volume", 1.0)),
                    "chromosomes": len(_cell_chromosomes(v))} for k, v in _cells(colony)}

    snaps = [norm(colony)]
    for _ in range(steps):
        out = p.update({"colony": colony, "substrate": sub}, 1.0)
        colony = out["colony"]
        sub += out["substrate"]
        snaps.append(norm(colony))
    return snaps


def main() -> None:
    rows = _run_composite()
    starved = _run_composite(substrate=1e-9, steps=20)
    snaps = _step_snapshots(20)

    t = [float(r["time"]) for r in rows]
    cells = [float(r["cell_count"]) for r in rows]
    dna = [float(r["tot_dna"]) for r in rows]
    nuc = [float(r["tot_nucleotides"]) for r in rows]
    vol = [float(r["tot_volume"]) for r in rows]
    bm = [float(r["tot_biomass"]) for r in rows]
    st_cells = [float(r["cell_count"]) for r in starved]

    assert cells[-1] == 16.0 and st_cells[-1] == 1.0, "gated-division demonstration broken"

    # lineage: birth tick + parent for each cell key
    birth, parent, gen = {}, {}, {}
    for ti, snap in enumerate(snaps):
        for k, v in snap.items():
            if k not in birth:
                birth[k] = ti
                parent[k] = v["parent"]
                gen[k] = v["generation"]
    # y position per cell: spread within its generation by birth order
    bygen = {}
    for k in birth:
        bygen.setdefault(gen[k], []).append(k)
    ypos = {}
    for g, ks in bygen.items():
        ks.sort(key=lambda k: birth[k])
        for i, k in enumerate(ks):
            ypos[k] = (i - (len(ks) - 1) / 2.0)

    fig, axes = plt.subplots(2, 3, figsize=(15, 8.4))
    fig.suptitle("Fig 9 (mechanistic) · growth-, energy- and size-gated cell cycle — "
                 "division is an outcome of physiology, not a clock", fontsize=12.5, y=0.99)

    # A — cell count, full vs starved
    ax = axes[0, 0]
    ax.step(t, cells, where="post", color=C_CELLS, lw=2.2, label="full nutrient")
    ax.step([float(r["time"]) for r in starved], st_cells, where="post",
            color=C_STARVE, lw=2.2, ls="--", label="starved (ε nutrient)")
    ax.set_title("A · Growth-gated division (1→2→4→8→16) vs starvation")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("cell count")
    ax.set_yscale("log", base=2); ax.legend(fontsize=8)

    # B — lineage tree
    ax = axes[0, 1]
    for k in birth:
        p = parent[k]
        if p in birth:
            ax.plot([birth[p], birth[k]], [ypos[p], ypos[k]], color="#bbb", lw=1, zorder=1)
    gens = [gen[k] for k in birth]
    sc = ax.scatter([birth[k] for k in birth], [ypos[k] for k in birth],
                    c=gens, cmap="viridis", s=40, zorder=3)
    ax.set_title("B · Lineage tree (parent→daughter), colored by generation")
    ax.set_xlabel("birth time (ticks)"); ax.set_ylabel("lineage spread")
    ax.set_yticks([]); fig.colorbar(sc, ax=ax, label="generation", fraction=0.046, pad=0.04)

    # C — conservative-state ledger
    ax = axes[1, 0]
    ax.plot(t, vol, color=C_VOL, lw=2, label="Σ volume")
    ax.plot(t, dna, color=C_DNA, lw=2, label="Σ DNA")
    ax.plot(t, bm, color=C_BM, lw=2, label="Σ biomass")
    ax.set_title("C · Conserved-state ledger — smooth across every division rewrite")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("colony total")
    ax.legend(fontsize=8)

    # D — nucleotide accounting
    ax = axes[0, 2]
    ax.plot(t, dna, color=C_DNA, lw=2, label="Σ DNA (chromosomes)")
    ax.plot(t, nuc, color=C_NUC, lw=2, label="Σ nucleotide pool")
    ax.plot(t, [d + n for d, n in zip(dna, nuc)], color="#000", lw=0.9, ls=":", label="Σ (DNA + nucleotides)")
    ax.set_title("D · Replication draws DNA FROM the precursor pool")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("amount")
    ax.legend(fontsize=7.5)

    # E — one lineage's volume + chromosome count
    ax = axes[1, 1]
    # follow cell → cell_1 → cell_... (first daughter each division)
    lineage = []
    cur = "cell"
    while cur is not None:
        lineage.append(cur)
        kids = [k for k in birth if parent.get(k) == cur]
        cur = sorted(kids, key=lambda k: birth[k])[0] if kids else None
    lt, lv, lc = [], [], []
    for ti, snap in enumerate(snaps):
        for k in lineage:
            if k in snap:
                lt.append(ti); lv.append(snap[k]["volume"]); lc.append(snap[k]["chromosomes"]); break
    ax.plot(lt, lv, color=C_VOL, lw=2, label="volume")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("volume", color=C_VOL)
    ax.tick_params(axis="y", labelcolor=C_VOL)
    ax.set_title("E · One lineage: grow → replicate → divide")
    ax2 = ax.twinx()
    ax2.step(lt, lc, where="post", color=C_DNA, lw=1.6, ls="--", label="chromosomes")
    ax2.set_ylabel("chromosomes", color=C_DNA); ax2.tick_params(axis="y", labelcolor=C_DNA)
    ax2.set_yticks([1, 2])

    # F — cell cycle checkpoints for the founder cell
    ax = axes[1, 2]
    v_founder = [snap["cell"]["volume"] for snap in snaps if "cell" in snap]
    tv = list(range(len(v_founder)))
    cfg = json.loads(COMPOSITE.read_text())["state"]["cell_cycle"]["config"]
    ax.plot(tv, v_founder, color=C_VOL, lw=2, marker="o", ms=3)
    ax.axhline(cfg["v_rep"], color=C_DNA, ls="--", lw=1.2, label=f"V_rep={cfg['v_rep']} (replicate)")
    ax.axhline(cfg["v_div"], color=C_STARVE, ls="--", lw=1.2, label=f"V_div={cfg['v_div']} (divide)")
    ax.set_title("F · Founder cell cycle: size checkpoints gate the transitions")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("volume")
    ax.legend(fontsize=7.5)

    for ax in [axes[0, 0], axes[0, 2], axes[1, 0], axes[1, 1], axes[1, 2]]:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(True, alpha=0.2, lw=0.5)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    print(f"  full → {cells[-1]:.0f} cells; starved → {st_cells[-1]:.0f} (delayed); "
          f"ΣDNA tracks cell count; Σ(DNA+Nuc) accounted")


if __name__ == "__main__":
    main()
