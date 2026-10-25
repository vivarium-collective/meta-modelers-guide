#!/usr/bin/env python
"""Render Fig 10's MECHANISTIC demonstration: a spatially-emergent biofilm.

Unlike the baseline (which reorganizes the place graph on a wall clock), here
motile cells aggregate by LOCAL adhesion and the biofilm forms only once a quorum
sits in proximity for several sustained ticks — an emergent place-graph rewrite —
after which ECM binds the community. This runs the fig10-mechanistic composite plus
matched-null controls (adhesion off, ECM off — via an EPSILON) and writes a
six-panel decisive figure to the fig-10 study visualizations:

  A  spatial snapshots: dispersed → aggregating → formed biofilm (cells + hull)
  B  cell trajectories (2-D paths, time-coloured) converging to the colony
  C  cluster radius over time — full vs no-adhesion vs no-ECM (aggregation + persistence)
  D  ECM and cohesion over time, with the emergent formation tick marked
  E  the dynamic bigraph: N free cells  →  one biofilm node nesting N cells
  F  matched-null controls: did it form? final cluster radius per condition

Distances are in LATTICE units. Re-run whenever the fig10 mechanistic model
changes.

    python scripts/build_fig10_mechanistic.py
"""
from __future__ import annotations

import copy
import json
import math
import warnings
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig10-mechanistic.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-10" / "visualizations" / "fig10-mechanistic-dynamics.png"
N = 6
EPS = 1e-9
C_CELL, C_ECM, C_COH, C_FULL, C_NOADH, C_NOECM = "#0b7a75", "#b4531f", "#4b5bd6", "#0b7a75", "#c0392b", "#b4531f"


def run(cfg_over=None):
    spec = json.loads(COMPOSITE.read_text())
    steps = spec["default_n_steps"]
    if cfg_over:
        spec["state"]["colony_dynamics"]["config"].update(cfg_over)
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(steps)
    rows = gather_emitter_results(sim)[("emitter",)]
    # parallel stepped sim to snapshot positions each tick
    sim2 = Composite({"state": copy.deepcopy(spec)["state"]}, core=build_core())
    xs_hist = [[float(sim2.state["xs"][str(i)]) for i in range(N)]]
    ys_hist = [[float(sim2.state["ys"][str(i)]) for i in range(N)]]
    for _ in range(steps):
        sim2.run(1)
        xs_hist.append([float(sim2.state["xs"][str(i)]) for i in range(N)])
        ys_hist.append([float(sim2.state["ys"][str(i)]) for i in range(N)])
    return rows, np.array(xs_hist), np.array(ys_hist), steps


def _ftime(rows):
    f = [int(float(r["formed"])) for r in rows]
    return next((i for i, x in enumerate(f) if x == 1), None)


def main() -> None:
    rows, xs, ys, steps = run()
    rows_na, xs_na, ys_na, _ = run({"adhesion": EPS})
    rows_ne, xs_ne, ys_ne, _ = run({"ecm_rate": EPS})
    t = np.arange(steps + 1)
    ft = _ftime(rows)
    cr = np.array([float(r["cluster_radius"]) for r in rows])
    cr_na = np.array([float(r["cluster_radius"]) for r in rows_na])
    cr_ne = np.array([float(r["cluster_radius"]) for r in rows_ne])
    ecm = np.array([float(r["ecm_total"]) for r in rows])
    coh = np.array([float(r["cohesion"]) for r in rows])

    assert ft is not None, "biofilm did not form in the full run"
    assert _ftime(rows_na) is None, "control: no-adhesion should not form"
    assert cr_ne[-1] > cr[-1] + 3.0, "control: no-ECM should disperse"

    fig, axes = plt.subplots(2, 3, figsize=(15, 8.6))
    fig.suptitle("Fig 10 (mechanistic) · biofilm formation EMERGES from spatial aggregation — "
                 "not a wall clock", fontsize=12.5, y=0.99)

    # A — spatial snapshots
    ax = axes[0, 0]
    snaps = [0, max(1, ft - 2), min(steps, ft + 6)]
    labels = [f"t={snaps[0]} dispersed", f"t={snaps[1]} aggregating", f"t={snaps[2]} biofilm"]
    cols = ["#bbbbbb", "#5aa9a4", C_CELL]
    for s, lab, col in zip(snaps, labels, cols):
        ax.scatter(xs[s], ys[s], s=90, color=col, edgecolor="white", lw=1, label=lab, zorder=3)
    ax.set_title("A · Spatial snapshots: dispersed → aggregated")
    ax.set_xlabel("x (lattice)"); ax.set_ylabel("y (lattice)")
    ax.legend(fontsize=7.5, loc="upper right"); ax.set_aspect("equal", "box")

    # B — trajectories
    ax = axes[0, 1]
    for i in range(N):
        ax.plot(xs[:, i], ys[:, i], color=C_CELL, alpha=0.5, lw=1)
        ax.scatter(xs[0, i], ys[0, i], color="#bbb", s=40, zorder=3)
        ax.scatter(xs[-1, i], ys[-1, i], color=C_CELL, s=55, edgecolor="white", lw=1, zorder=4)
    ax.set_title("B · Cell trajectories converge to the colony")
    ax.set_xlabel("x (lattice)"); ax.set_ylabel("y (lattice)")
    ax.set_aspect("equal", "box")

    # C — cluster radius: full vs controls
    ax = axes[0, 2]
    ax.plot(t, cr, color=C_FULL, lw=2.2, label="full")
    ax.plot(t, cr_na, color=C_NOADH, lw=2, ls="--", label="no-adhesion")
    ax.plot(t, cr_ne, color=C_NOECM, lw=2, ls=":", label="no-ECM")
    ax.axvline(ft, color="#555", ls=":", lw=1.1)
    ax.annotate("forms", (ft, ax.get_ylim()[1] * 0.9), fontsize=8, color="#555")
    ax.set_title("C · Cluster radius — aggregation & persistence")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("cluster radius (lattice)")
    ax.legend(fontsize=8)

    # D — ECM + cohesion
    ax = axes[1, 0]
    ax.plot(t, ecm, color=C_ECM, lw=2, label="ECM (matrix)")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("ECM", color=C_ECM)
    ax.tick_params(axis="y", labelcolor=C_ECM)
    ax.axvline(ft, color="#555", ls=":", lw=1.1)
    ax.set_title("D · ECM secreted & cohesion — only after organization")
    ax2 = ax.twinx()
    ax2.plot(t, coh, color=C_COH, lw=2, ls="--", label="cohesion")
    ax2.set_ylabel("cohesion (0–1)", color=C_COH); ax2.tick_params(axis="y", labelcolor=C_COH)
    ax2.set_ylim(-0.05, 1.05)

    # E — dynamic bigraph before/after
    ax = axes[1, 1]; ax.axis("off")
    ax.set_title("E · Dynamic place-graph rewrite (identity preserved)")
    # before: N free cells
    for i in range(N):
        ax.add_patch(plt.Circle((0.08 + 0.14 * i, 0.72), 0.045, color=C_CELL, ec="white"))
    ax.text(0.5, 0.86, f"before:  {N} free cells (top level)", ha="center", fontsize=9)
    ax.annotate("", (0.5, 0.52), (0.5, 0.62), arrowprops=dict(arrowstyle="->", lw=1.5))
    ax.text(0.62, 0.57, "proximity + sustained contact", fontsize=7.5, color="#555")
    # after: biofilm node nesting N cells
    ax.add_patch(plt.Rectangle((0.12, 0.12), 0.76, 0.32, fill=False, ec=C_ECM, lw=2))
    ax.text(0.5, 0.40, "biofilm (collective node)", ha="center", fontsize=9, color=C_ECM)
    for i in range(N):
        ax.add_patch(plt.Circle((0.2 + 0.11 * i, 0.24), 0.04, color=C_CELL, ec="white"))
    ax.text(0.5, 0.03, "after:  same 6 cells nested + biomass preserved", ha="center", fontsize=9)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    # F — controls
    ax = axes[1, 2]
    conds = ["full", "no-adhesion", "no-ECM"]
    formed = [1 if _ftime(r) is not None else 0 for r in (rows, rows_na, rows_ne)]
    finalr = [cr[-1], cr_na[-1], cr_ne[-1]]
    x = np.arange(len(conds)); w = 0.38
    ax.bar(x - w / 2, formed, w, color="#4b5bd6", label="formed? (1/0)")
    ax.bar(x + w / 2, np.array(finalr) / max(finalr), w, color=C_ECM, label="final radius (norm.)")
    ax.set_xticks(x); ax.set_xticklabels(conds, fontsize=8.5)
    ax.set_title("F · Controls: adhesion needed to form, ECM to persist")
    ax.legend(fontsize=8)
    ax.annotate("no-adhesion: never forms\nno-ECM: forms then disperses",
                (0.02, 0.97), xycoords="axes fraction", fontsize=7.5, va="top", color="#555")

    for ax in [axes[0, 2], axes[1, 0], axes[1, 2]]:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(True, alpha=0.2, lw=0.5)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    print(f"  formed@t={ft}; full radius→{cr[-1]:.2f}, no-adhesion→{cr_na[-1]:.2f} (never forms), "
          f"no-ECM→{cr_ne[-1]:.2f} (disperses); cohesion_end={coh[-1]:.2f}")


if __name__ == "__main__":
    main()
