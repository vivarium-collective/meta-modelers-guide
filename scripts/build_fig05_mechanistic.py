#!/usr/bin/env python
"""Render Fig 5's MECHANISTIC demonstration: an adaptive multiscale cell that refines
its grain when a quantified model-inadequacy signal crosses tolerance — with the
biological damage state shown SEPARATELY from the algorithmic grain change.

Runs the fig05-mechanistic composite in all three modes (adaptive / always-coarse /
always-fine) and writes a six-panel decisive figure to the fig-05 visualizations:

  A  biological damage state (soluble + aggregated misfolded protein) — the biology,
     grain-independent, with the adaptive switch marked
  B  the ALGORITHMIC trigger: inadequacy estimator vs tolerance, and the active grain
     (coarse→fine) — separate from the biology in A
  C  biomass: adaptive vs always-coarse vs always-fine (what refinement recovers)
  D  viability: the aggregation collapse the fine grain resolves and coarse MISSES
  E  handover conservation: biomass continuous across the switch, handover_error ≈ 0
  F  prediction divergence vs the always-fine reference: coarse diverges, adaptive tracks

Asserts the load-bearing claims before plotting. Re-run whenever the fig05 mechanistic
model or composite changes.

    python scripts/build_fig05_mechanistic.py
"""
from __future__ import annotations

import copy
import json
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
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig05-mechanistic.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-05" / "visualizations" / "fig05-mechanistic-dynamics.png"

C_SOL, C_AGG, C_TOT, C_ADA, C_CO, C_FI, C_GRAIN, C_INAD, C_TOL = (
    "#4b5bd6", "#c0392b", "#111", "#0b7a75", "#b4531f", "#7a5195", "#555", "#b4531f", "#999")


def run(mode):
    spec = json.loads(COMPOSITE.read_text())
    spec["state"]["cell"]["config"]["mode"] = mode
    sim = Composite({"state": spec["state"]}, core=build_core())
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter", )]


def col(rows, k):
    return np.array([float(r[k]) for r in rows])


def main() -> None:
    a, co, fi = run("adaptive"), run("coarse"), run("fine")
    t = col(a, "time")
    sw = next((t[i] for i in range(len(t)) if float(a[i]["active_grain"]) > 0.5), None)

    # ── assertions ───────────────────────────────────────────────────────────
    assert float(co[-1]["viability"]) > 0.5 > float(fi[-1]["viability"]), "coarse should miss the collapse fine sees"
    assert float(co[-1]["m_agg"]) < 1e-9 < float(fi[-1]["m_agg"]), "only the fine grain forms aggregates"
    div_af = np.abs(col(a, "biomass") - col(fi, "biomass")).max()
    div_cf = np.abs(col(co, "biomass") - col(fi, "biomass")).max()
    assert div_af < 0.2 * div_cf, "adaptive should track fine far better than coarse"
    assert np.abs(col(a, "handover_error")).max() < 1e-12

    fig, axes = plt.subplots(2, 3, figsize=(15, 8.4))
    fig.suptitle("Fig 5 (mechanistic) · adaptive grain refinement on a quantified inadequacy signal — "
                 "biology (A) separated from the algorithmic grain (B)", fontsize=12.5, y=0.99)

    def mark(ax):
        if sw is not None:
            ax.axvline(sw, color=C_GRAIN, ls=":", lw=1.3)

    # A — biological damage state (grain-independent biology), adaptive run
    ax = axes[0, 0]
    ax.plot(t, col(a, "m_sol"), color=C_SOL, lw=2, label="soluble misfolded")
    ax.plot(t, col(a, "m_agg"), color=C_AGG, lw=2, label="aggregated (toxic)")
    ax.plot(t, col(a, "damage"), color=C_TOT, lw=1.5, ls="--", label="total damage")
    mark(ax)
    ax.set_title("A · Biological damage state (the biology)")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("misfolded protein (conc)")
    ax.legend(fontsize=8)

    # B — algorithmic trigger (separate from biology)
    ax = axes[0, 1]
    ax.plot(t, col(a, "inadequacy"), color=C_INAD, lw=2, label="inadequacy estimate")
    ax.axhline(0.20, color=C_TOL, ls="--", lw=1.2, label="tolerance")
    mark(ax)
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("neglected-term fraction", color=C_INAD)
    ax.tick_params(axis="y", labelcolor=C_INAD)
    ax.set_title("B · Algorithmic trigger: inadequacy → refine (not wall-clock)")
    ax2 = ax.twinx()
    ax2.plot(t, col(a, "active_grain"), color=C_GRAIN, lw=2, drawstyle="steps-post", label="active grain")
    ax2.set_ylabel("active grain (0=coarse, 1=fine)", color=C_GRAIN)
    ax2.set_yticks([0, 1]); ax2.tick_params(axis="y", labelcolor=C_GRAIN)
    ax.legend(fontsize=7.5, loc="center right")

    # C — biomass across the three modes
    ax = axes[0, 2]
    ax.plot(t, col(fi, "biomass"), color=C_FI, lw=2.4, label="always-fine (reference)")
    ax.plot(t, col(a, "biomass"), color=C_ADA, lw=1.8, ls="--", label="adaptive")
    ax.plot(t, col(co, "biomass"), color=C_CO, lw=1.8, label="always-coarse")
    mark(ax)
    ax.set_title("C · Biomass — refinement recovers the fine prediction")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("biomass")
    ax.legend(fontsize=8)

    # D — viability collapse coarse misses
    ax = axes[1, 0]
    ax.plot(t, col(fi, "viability"), color=C_FI, lw=2.4, label="always-fine")
    ax.plot(t, col(a, "viability"), color=C_ADA, lw=1.8, ls="--", label="adaptive")
    ax.plot(t, col(co, "viability"), color=C_CO, lw=1.8, label="always-coarse")
    mark(ax)
    ax.set_title("D · Viability — aggregation collapse the coarse grain MISSES")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("viability (0–1)")
    ax.legend(fontsize=8)

    # E — handover conservation
    ax = axes[1, 1]
    dbm = np.abs(np.diff(col(a, "biomass"), prepend=col(a, "biomass")[0]))
    ax.plot(t, dbm, color=C_ADA, lw=1.8, label="|Δ biomass| per tick")
    ax.plot(t, np.abs(col(a, "handover_error")), color=C_AGG, lw=2, label="handover error")
    mark(ax)
    ax.set_title("E · Conserving handover — no artificial jump (err ≈ 0)")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("magnitude")
    ax.legend(fontsize=8)
    ax.annotate("biomass continuous across\nthe grain switch; handover_error = 0",
                (0.5, 0.9), xycoords="axes fraction", fontsize=7.5, va="top", color="#555")

    # F — prediction divergence vs always-fine
    ax = axes[1, 2]
    ax.plot(t, np.abs(col(co, "biomass") - col(fi, "biomass")), color=C_CO, lw=2, label="|coarse − fine|")
    ax.plot(t, np.abs(col(a, "biomass") - col(fi, "biomass")), color=C_ADA, lw=2, ls="--", label="|adaptive − fine|")
    mark(ax)
    ax.set_title("F · Prediction divergence from the fine reference")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("|Δ biomass|")
    ax.legend(fontsize=8)

    for ax in axes.flat:
        ax.grid(True, alpha=0.2, lw=0.5)
        ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    print(f"  switch t={sw}; final viability coarse {float(co[-1]['viability']):.2f} vs fine "
          f"{float(fi[-1]['viability']):.2f}; divergence coarse {div_cf:.2f} vs adaptive {div_af:.3f}; "
          f"handover_error {np.abs(col(a,'handover_error')).max():.1e}")


if __name__ == "__main__":
    main()
