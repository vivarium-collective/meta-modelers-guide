#!/usr/bin/env python
"""Render Fig 8's MECHANISTIC demonstration: a self-maintaining cell with a real
boundary, turnover, ATP-costed repair and viability — persistence, component
replacement, recovery after injury, and collapse when operational closure breaks.

Runs the fig08-mechanistic composite (self-maintaining cell on a replenished medium,
membrane injured at tick 45) plus matched-null controls (repair off; each mechanism
knocked out; medium not replenished — all via epsilon). Writes a six-panel decisive
figure to the fig-08 study visualizations:

  A  the cell at three times (healthy → injured → recovered): membrane ring ∝ area, fill ∝ viability
  B  aligned state curves (membrane, enzymes, energy, viability) with the injury marked
  C  maintenance fluxes (import, metabolism, repair) — repair surges to rebuild after injury
  D  component replacement: membrane held by repair vs decaying when repair is off (turnover)
  E  the operational-closure / dependency graph (each component made by processes that need it)
  F  controls: final viability for full vs mechanism knockouts vs a non-replenished medium

    python scripts/build_fig08_mechanistic.py
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig08-mechanistic.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-08" / "visualizations" / "fig08-mechanistic-dynamics.png"
EPS = 1e-9
PERTURB = 45

C_MEM, C_ENZ, C_ENG, C_VIAB = "#4b5bd6", "#7a5195", "#b4531f", "#0b7a75"
C_IMP, C_MET, C_REP = "#0b7a75", "#7a5195", "#c0392b"


def run(cell_over=None, reservoir_over=None):
    spec = json.loads(COMPOSITE.read_text())
    if cell_over:
        spec["state"]["cell"]["config"].update(cell_over)
    if reservoir_over:
        spec["state"]["reservoir"]["config"].update(reservoir_over)
    sim = Composite({"state": spec["state"]}, core=build_core())
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def ser(rows, k):
    return np.array([float(r[k]) for r in rows])


def draw_cell(ax, membrane, viability, title):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.set_title(title, fontsize=9)
    r = 0.12 + 0.26 * min(membrane / 4.0, 1.0)          # radius ∝ membrane area
    lw = 2 + 10 * min(membrane / 4.0, 1.0)               # ring thickness ∝ membrane area
    fill = plt.cm.RdYlGn(0.15 + 0.7 * max(0.0, min(viability, 1.0)))
    ax.add_patch(Circle((0.5, 0.52), r, facecolor=fill, edgecolor=C_MEM, lw=lw, alpha=0.9))
    ax.text(0.5, 0.52, f"viab\n{viability:.2f}", ha="center", va="center", fontsize=8)
    ax.text(0.5, 0.06, f"membrane {membrane:.2f}", ha="center", fontsize=7.5, color=C_MEM)


def draw_closure_graph(ax):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.set_title("E · Operational-closure loop (each made by what needs it)", fontsize=9.5)
    nodes = {
        "membrane": (0.5, 0.88), "import": (0.86, 0.6), "metabolism": (0.72, 0.2),
        "ATP+precursor": (0.28, 0.2), "repair + enzymes": (0.14, 0.6),
    }
    for name, (x, y) in nodes.items():
        ax.add_patch(FancyBboxPatch((x - 0.13, y - 0.055), 0.26, 0.11,
                     boxstyle="round,pad=0.01", facecolor="#eef0fb", edgecolor=C_MEM, lw=1.3))
        ax.text(x, y, name, ha="center", va="center", fontsize=7.8)
    edges = [("membrane", "import", "gates"), ("import", "metabolism", "feeds"),
             ("metabolism", "ATP+precursor", "makes"), ("ATP+precursor", "repair + enzymes", "spent on"),
             ("repair + enzymes", "membrane", "rebuilds")]
    order = ["membrane", "import", "metabolism", "ATP+precursor", "repair + enzymes"]
    for a, b, lab in edges:
        xa, ya = nodes[a]; xb, yb = nodes[b]
        ax.add_patch(FancyArrowPatch((xa, ya), (xb, yb), arrowstyle="-|>", mutation_scale=13,
                     color="#888", lw=1.4, connectionstyle="arc3,rad=0.18",
                     shrinkA=20, shrinkB=20))
    ax.text(0.5, 0.5, "closed loop →\nbreak any edge\n= collapse", ha="center", va="center",
            fontsize=8, color="#c0392b", style="italic")


def main():
    rows = run()
    t = np.arange(len(rows))
    mem, enz, eng, viab = ser(rows, "membrane"), ser(rows, "enzymes"), ser(rows, "energy"), ser(rows, "viability")
    imp, met, rep = ser(rows, "import_flux"), ser(rows, "metabolic_flux"), ser(rows, "repair_flux")

    mem_norepair = ser(run(cell_over={"perturb_at": -1.0, "k_repair": EPS}), "membrane")
    mem_steady = ser(run(cell_over={"perturb_at": -1.0}), "membrane")

    controls = {"full": viab[-1]}
    for ko in ["k_transport", "k_met", "k_expr", "k_repair"]:
        controls[ko.replace("k_", "KO ")] = ser(run(cell_over={ko: EPS, "perturb_at": -1.0}), "viability")[-1]
    controls["closed medium"] = ser(run(reservoir_over={"replenish": EPS}, cell_over={"perturb_at": -1.0}), "viability")[-1]

    # assertions
    assert mem[PERTURB] < 0.6 * mem[PERTURB - 1], "injury not visible"
    assert mem[-1] > 0.9 * mem[PERTURB - 1], "no recovery"
    assert mem_norepair[-1] < 0.3 * mem_steady[-1], "repair-off should decay"

    fig = plt.figure(figsize=(15, 8.6))
    fig.suptitle("Fig 8 (mechanistic) · a self-maintaining cell — persistence, component replacement, "
                 "repair & recovery, and collapse when closure breaks", fontsize=12.5, y=0.99)
    gs = fig.add_gridspec(2, 3)

    # A — cell cartoons at three times
    gsa = gs[0, 0].subgridspec(1, 3, wspace=0.1)
    dip = PERTURB + int(np.argmin(viab[PERTURB:PERTURB + 18]))   # where viability bottoms out
    draw_cell(fig.add_subplot(gsa[0]), mem[PERTURB - 1], viab[PERTURB - 1], "healthy (t44)")
    draw_cell(fig.add_subplot(gsa[1]), mem[dip], viab[dip], f"injured (t{dip})")
    draw_cell(fig.add_subplot(gsa[2]), mem[-1], viab[-1], "recovered (t90)")

    # B — aligned state curves
    ax = fig.add_subplot(gs[0, 1])
    ax.axvline(PERTURB, color="#c0392b", ls=":", lw=1.3)
    ax.axvspan(PERTURB, PERTURB + 18, color="#c0392b", alpha=0.05)
    ax.plot(t, mem, color=C_MEM, lw=2, label="membrane (area)")
    ax.plot(t, enz, color=C_ENZ, lw=1.6, label="enzymes")
    ax.plot(t, eng, color=C_ENG, lw=1.6, label="energy (ATP)")
    ax.plot(t, viab * mem.max(), color=C_VIAB, lw=1.8, ls="--", label="viability (×scale)")
    ax.set_title("B · Growth → steady state → injury → recovery")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("pool level")
    ax.annotate("injury −60%", (PERTURB, mem[PERTURB]), fontsize=8, color="#c0392b")
    ax.legend(fontsize=7.5, loc="lower right")

    # C — maintenance fluxes
    ax = fig.add_subplot(gs[0, 2])
    ax.axvline(PERTURB, color="#c0392b", ls=":", lw=1.3)
    ax.plot(t, imp, color=C_IMP, lw=1.8, label="import flux")
    ax.plot(t, met, color=C_MET, lw=1.8, label="metabolic flux")
    ax.plot(t, rep, color=C_REP, lw=1.8, label="repair flux")
    ax.set_title("C · Maintenance throughput (repair surges to rebuild)")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("flux")
    ax.legend(fontsize=7.5, loc="upper right")

    # D — component replacement (repair vs turnover)
    ax = fig.add_subplot(gs[1, 0])
    ax.plot(t, mem_steady, color=C_MEM, lw=2, label="repair on (held)")
    ax.plot(t, mem_norepair, color="#c0392b", lw=2, ls="--", label="repair off (decays)")
    ax.set_title("D · Turnover needs replacement: membrane held vs decaying")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("membrane area")
    ax.legend(fontsize=8)

    # E — closure graph
    draw_closure_graph(fig.add_subplot(gs[1, 1]))

    # F — controls
    ax = fig.add_subplot(gs[1, 2])
    labels = list(controls.keys()); vals = [controls[k] for k in labels]
    colors = ["#0b7a75"] + ["#c0392b"] * (len(labels) - 1)
    ax.barh(range(len(labels)), vals, color=colors)
    ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, 1); ax.set_xlabel("final viability")
    ax.set_title("F · Break any closure edge → viability collapses")
    for i, v in enumerate(vals):
        ax.annotate(f"{v:.2f}", (v, i), va="center", fontsize=7.5,
                    xytext=(3, 0), textcoords="offset points")

    for ax in fig.axes:
        if ax.get_title().startswith(("B ", "C ", "D ")):
            ax.spines[["top", "right"]].set_visible(False)
            ax.grid(True, alpha=0.2, lw=0.5)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    print(f"  injury t45 mem {mem[PERTURB-1]:.2f}→{mem[PERTURB]:.2f}, recovered→{mem[-1]:.2f}; "
          f"viab dip {min(viab[PERTURB:PERTURB+18]):.2f}→{viab[-1]:.2f}; "
          f"controls viab={ {k: round(v,2) for k,v in controls.items()} }")


if __name__ == "__main__":
    main()
