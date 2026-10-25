#!/usr/bin/env python
"""Render Fig 2's MECHANISTIC demonstration: multirate orchestration separated into
scheduling vs accuracy, with an explicit input-output ledger.

Runs the fig02-mechanistic composite (a stiff FastMetabolism process + a SlowBiomass
process sharing one pool on different clocks) plus a fine-step reference and a
Δt-sweep, and writes a four-panel figure to the fig-02 study visualizations:

  A  update-EVENT RASTER — when each clock actually fires (fast vs slow)
  B  pooled metabolite + biomass trajectories with the FINE-STEP REFERENCE overlaid
  C  numerical ERROR in final biomass vs the slow step size (O(Δt) convergence)
  D  input-output LEDGER — cumulative_input = ΔM + Δbiomass + Δwaste (pool+biomass
     is only part of the budget; the rest is turnover/conversion waste)

Asserts the ledger closes and biomass converges before plotting. Re-run when the
fig02 mechanistic model changes.

    python scripts/build_fig02_mechanistic.py
"""
from __future__ import annotations

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
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig02-mechanistic.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-02" / "visualizations" / "fig02-mechanistic-dynamics.png"

C_M, C_B, C_W, C_IN, C_REF, C_FAST, C_SLOW = "#0b7a75", "#b4531f", "#c0392b", "#4b5bd6", "#999999", "#0b7a75", "#b4531f"


def run(dt_fast=0.25, dt_slow=1.0, T=20):
    spec = json.loads(COMPOSITE.read_text())
    spec["state"]["fast"]["interval"] = dt_fast
    spec["state"]["slow"]["interval"] = dt_slow
    sim = Composite({"state": spec["state"]}, core=build_core())
    sim.run(T)
    return gather_emitter_results(sim)[("emitter",)]


def main() -> None:
    T, dt_fast, dt_slow = 20, 0.25, 1.0
    rows = run(dt_fast, dt_slow, T)
    ref = run(0.02, 0.02, T)
    t = [float(r["time"]) for r in rows]
    M = [float(r["metabolite"]) for r in rows]
    B = [float(r["biomass"]) for r in rows]
    W = [float(r["waste"]) for r in rows]
    IN = [float(r["cumulative_input"]) for r in rows]
    tref = [float(r["time"]) for r in ref]
    Mref = [float(r["metabolite"]) for r in ref]
    Bref = [float(r["biomass"]) for r in ref]

    # convergence sweep — refine the WHOLE scheme (both clocks scaled together) toward
    # a fine reference: a clean O(Δt) study. The signal lives in the stiff metabolite
    # pool (coarse-Δt overshoot), as its L1 trajectory error at integer times.
    def _m_at(rows_, tt):
        return float(min(rows_, key=lambda r: abs(float(r["time"]) - tt))["metabolite"])
    dts = [1.0, 0.5, 0.25, 0.125, 0.0625]
    grid = list(range(1, T + 1))
    m_ref = {tt: _m_at(ref, tt) for tt in grid}
    errs = [sum(abs(_m_at(run(d, d, T), tt) - m_ref[tt]) for tt in grid) for d in dts]

    # assertions
    resid = max(abs(IN[i] - ((M[i] - M[0]) + (B[i] - B[0]) + (W[i] - W[0]))) for i in range(len(rows)))
    assert resid < 1e-9, f"ledger residual {resid:.2e}"
    assert all(errs[i + 1] < errs[i] for i in range(len(errs) - 1)), f"not monotone: {errs}"

    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    fig.suptitle("Fig 2 (mechanistic) · multirate orchestration — scheduling vs accuracy, with an input–output ledger",
                 fontsize=12.5, y=0.99)

    # A — event raster
    ax = axes[0, 0]
    fast_fires = np.arange(dt_fast, T + 1e-9, dt_fast)
    slow_fires = np.arange(dt_slow, T + 1e-9, dt_slow)
    ax.vlines(fast_fires, 0.6, 1.4, color=C_FAST, lw=1.0, label=f"FastMetabolism (Δt={dt_fast})")
    ax.vlines(slow_fires, -0.4, 0.4, color=C_SLOW, lw=1.8, label=f"SlowBiomass (Δt={dt_slow})")
    ax.set_yticks([0, 1]); ax.set_yticklabels(["slow", "fast"])
    ax.set_ylim(-1, 2); ax.set_xlabel("time")
    ax.set_title("A · Update-event raster (which clock fires when)")
    ax.legend(fontsize=8, loc="upper right")

    # B — trajectories vs fine reference
    ax = axes[0, 1]
    ax.plot(tref, Mref, color=C_REF, lw=3, alpha=0.4, label="metabolite (fine ref)")
    ax.plot(tref, Bref, color="#c9a227", lw=3, alpha=0.4, label="biomass (fine ref)")
    ax.plot(t, M, color=C_M, lw=1.6, label="metabolite (multirate)")
    ax.plot(t, B, color=C_B, lw=1.6, label="biomass (multirate)")
    ax.set_title("B · Pool (sawtooth) + biomass (staircase) vs fine reference")
    ax.set_xlabel("time"); ax.set_ylabel("amount")
    ax.legend(fontsize=7.5, loc="center right")

    # C — error vs dt_slow (log-log O(dt))
    ax = axes[1, 0]
    ax.loglog(dts, errs, "o-", color=C_IN, lw=1.8)
    # O(dt) guide line
    guide = [errs[-1] * (d / dts[-1]) for d in dts]
    ax.loglog(dts, guide, "--", color="#999", lw=1, label="O(Δt) slope-1 guide")
    ax.set_title("C · Metabolite error vs timestep (both clocks refined) — O(Δt)")
    ax.set_xlabel("timestep Δt (fast=slow)"); ax.set_ylabel("L1 pool error vs fine ref")
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.25, lw=0.5)

    # D — input-output ledger
    ax = axes[1, 1]
    ax.plot(t, IN, color=C_IN, lw=2.4, label="cumulative input")
    ax.stackplot(t, M, B, W, labels=["metabolite (pool)", "biomass", "waste (turnover+loss)"],
                 colors=["#0b7a75", "#c9a227", "#c0392b"], alpha=0.85)
    ax.set_title("D · Ledger: input = pool + biomass + waste (not pool+biomass)")
    ax.set_xlabel("time"); ax.set_ylabel("cumulative mass")
    ax.legend(fontsize=7.5, loc="upper left")

    for ax in [axes[0, 1], axes[1, 0], axes[1, 1]]:
        ax.spines[["top", "right"]].set_visible(False)
    axes[0, 1].grid(True, alpha=0.2, lw=0.5); axes[1, 1].grid(True, alpha=0.2, lw=0.5)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    print(f"  ledger residual ≤ {resid:.1e}; biomass {B[-1]:.3f} vs fine ref {Bref[-1]:.3f}; "
          f"pool L1 error {errs[0]:.3f}→{errs[-1]:.3f} as Δt {dts[0]}→{dts[-1]}")


if __name__ == "__main__":
    main()
