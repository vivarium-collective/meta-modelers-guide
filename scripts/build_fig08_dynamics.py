#!/usr/bin/env python
"""Render Fig 8's time-series demonstration: the minimal cell is an autopoietic closure.

Fig 8b's principle is autopoiesis — containment, metabolism, gene-expression and
replication MUTUALLY PRODUCE the components (membrane, metabolites, proteins/enzymes,
genes) that sustain each other. This RUNS the runnable composite
(meta_modelers_guide.composites.fig08-runnable): the six coupled ODE handlers wired
over FLAT scalar building-block pools (the form the handlers actually integrate).

Because the processes share those pools none stands alone — gene expression makes the
enzymes metabolism needs, metabolism makes the energy replication spends, replication
grows the gene template. Run it forward and the closure holds a self-sustaining balance:

  * the catalytic / template pools (genes, energy, metabolites, nucleic acids) settle to
    a SUSTAINED steady level — produced and consumed/turned-over at a matched rate;
  * the cell's structural material (membrane, proteins, enzymes) ACCUMULATES steadily —
    the closure drives net production of cell stuff;
  * nothing collapses to zero and nothing explodes — the hallmark of autopoietic closure.

It writes a two-panel time-series PNG to the fig-08 study visualizations and asserts the
load-bearing claims: every pool stays positive and bounded over the run, and the
template/catalytic pools hold a steady balance while structural pools grow. Re-run
whenever the fig08 dynamics or the runnable composite change.

    python scripts/build_fig08_dynamics.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core

ROOT = Path(__file__).resolve().parent.parent
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig08-runnable.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-08" / "visualizations" / "fig08-dynamics.png"

# palette (matches the study figures' teal / accent family)
C_GENES, C_ENERGY, C_METAB, C_NUCLEIC = "#4b5bd6", "#b4531f", "#0b7a75", "#8a6d1f"
C_MEMBRANE, C_PROTEINS, C_ENZYMES = "#1c7a77", "#9c3d6a", "#3a7d3a"


def _run():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def main() -> None:
    rows = _run()
    t = [float(r["time"]) for r in rows]
    P = {k: [float(r[k]) for r in rows]
         for k in ("membrane", "metabolites", "enzymes", "proteins",
                   "genes", "energy", "nucleic_acids")}

    # ── load-bearing claims: sustained, positive, bounded closure ─────────────
    for k, series in P.items():
        assert min(series) > 0.0, f"{k} collapsed to (or below) zero — closure broke"
        assert max(series) < 1e3, f"{k} blew up — closure not bounded"
    # template/catalytic pools hold a steady balance (small relative drift)...
    for k in ("genes", "energy", "metabolites", "nucleic_acids"):
        s = P[k]
        rel = abs(s[-1] - s[len(s) // 2]) / max(s[len(s) // 2], 1e-9)
        assert rel < 0.25, f"{k} did not hold a steady balance (rel drift {rel:.2f})"
    # ...while structural material is net-produced (the cell grows).
    assert P["membrane"][-1] > P["membrane"][0]
    assert P["proteins"][-1] > P["proteins"][0]

    # ── figure ────────────────────────────────────────────────────────────────
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(12, 5.2), sharex=True)
    fig.suptitle("Fig 8 — the minimal cell sustains itself: autopoietic closure",
                 fontsize=15, fontweight="bold")
    fig.text(0.5, 0.9,
             "Containment, metabolism, gene-expression & replication mutually produce the "
             "pools that sustain each other — the closure holds a self-sustaining balance.",
             ha="center", fontsize=10, color="#444")

    # left: catalytic / template pools hold a SUSTAINED steady balance
    axL.plot(t, P["genes"], color=C_GENES, lw=2.2, marker="o", ms=3, label="genes (template)")
    axL.plot(t, P["energy"], color=C_ENERGY, lw=2.2, marker="o", ms=3, label="energy")
    axL.plot(t, P["metabolites"], color=C_METAB, lw=2.2, marker="o", ms=3, label="metabolites")
    axL.plot(t, P["nucleic_acids"], color=C_NUCLEIC, lw=2.2, marker="o", ms=3, label="nucleic acids")
    axL.set_title("Catalytic / template pools — held at a sustained balance", fontsize=11)
    axL.set_ylabel("pool level")
    axL.set_xlabel("time")
    axL.set_ylim(bottom=0)
    axL.legend(fontsize=8, loc="center right")
    axL.grid(alpha=0.25)

    # right: structural material accumulates — the closure builds the cell
    axR.plot(t, P["membrane"], color=C_MEMBRANE, lw=2.2, marker="o", ms=3, label="membrane (area)")
    axR.plot(t, P["proteins"], color=C_PROTEINS, lw=2.2, marker="o", ms=3, label="proteins")
    axR.plot(t, P["enzymes"], color=C_ENZYMES, lw=2.2, marker="o", ms=3, label="enzymes")
    axR.set_title("Structural material — net-produced (the cell grows)", fontsize=11)
    axR.set_ylabel("pool level")
    axR.set_xlabel("time")
    axR.set_ylim(bottom=0)
    axR.legend(fontsize=8, loc="upper left")
    axR.grid(alpha=0.25)

    fig.tight_layout(rect=(0, 0, 1, 0.88))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150)
    plt.close(fig)
    print(f"wrote {OUT.relative_to(ROOT)}")
    for k in ("membrane", "metabolites", "enzymes", "proteins", "genes", "energy", "nucleic_acids"):
        print(f"  {k:14s} {P[k][0]:.4f} -> {P[k][-1]:.4f}")


if __name__ == "__main__":
    main()
