#!/usr/bin/env python
"""Render Fig 4's (paper Fig 5) MECHANISTIC demonstration: a 1-D reaction–diffusion
nutrient field with a depleting, chemotactic cell — the sense/act loop CLOSED.

Unlike the baseline (whose uptake never touched the field, so an "uptake ∝ field"
readout was true by construction), here the cell's Michaelis–Menten uptake is a
real SINK: it carves a depletion well that diffuses, grows biomass out of it, and
chemotaxes up the local gradient toward an in-domain source. This script runs the
fig04-mechanistic composite plus matched-null controls (uptake off, motility off,
zero gradient — all via an EPSILON, since a float 0.0 config is silently restored
to default) and writes a six-panel decisive figure to the fig-04 study
visualizations:

  A  spatiotemporal field (space × time) with the cell's track overlaid
  B  the cell's FOOTPRINT on the environment: field(with cell) − field(no uptake)
  C  cell trajectory (climbs the gradient) and the nutrient it senses
  D  Michaelis–Menten uptake flux and biomass grown out of it
  E  mass ledger: Σsource − Σdecay − Σuptake = Δfield (closes), biomass = yield·Σuptake
  F  matched-null controls: displacement & growth for full / no-uptake / no-motility / zero-gradient

Distances are in LATTICE units (dx = 1). Re-run whenever the fig04 mechanistic
model or composite changes.

    python scripts/build_fig04_mechanistic.py
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
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig04-mechanistic.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-04" / "visualizations" / "fig04-mechanistic-dynamics.png"
N = 25
EPS = 1e-9

C_TRACK, C_UPT, C_BM, C_SRC, C_DEC, C_LEDG = "#ffffff", "#0b7a75", "#b4531f", "#4b5bd6", "#c0392b", "#555"


def run(cell_over=None, source_over=None, field=None):
    spec = json.loads(COMPOSITE.read_text())
    steps = spec["default_n_steps"]
    if cell_over:
        spec["state"]["cell"]["config"].update(cell_over)
    if source_over:
        spec["state"]["source"]["config"].update(source_over)
    if field is not None:
        g = {"_type": "map", "_value": "float"}
        g.update({str(i): field[i] for i in range(N)})
        spec["state"]["environment"]["chemical_field"] = g
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(steps)
    rows = gather_emitter_results(sim)[("emitter",)]
    sim2 = Composite({"state": copy.deepcopy(spec)["state"]}, core=build_core())
    snaps = [[float(sim2.state["environment"]["chemical_field"][str(i)]) for i in range(N)]]
    for _ in range(steps):
        sim2.run(1)
        snaps.append([float(sim2.state["environment"]["chemical_field"][str(i)]) for i in range(N)])
    return np.array(snaps), rows, steps


def main() -> None:
    full, rows, steps = run()
    nouptake, rows_nu, _ = run(cell_over={"vmax": EPS})
    nomot, rows_nm, _ = run(cell_over={"chemotaxis": EPS})
    _, rows_zg, _ = run(source_over={"source_rate": EPS}, field=[0.5] * N)

    t = np.arange(steps + 1)
    pos = np.array([float(r["position"]) for r in rows])
    bm = np.array([float(r["biomass"]) for r in rows])
    upt = np.array([float(r["uptake"]) for r in rows])
    local = np.array([float(r["local_conc"]) for r in rows])
    last = rows[-1]
    src, dec, upt_tot = float(last["source_total"]), float(last["decay_total"]), float(last["uptake_total"])
    d_field = full[-1].sum() - full[0].sum()

    footprint = full - nouptake  # negative where the cell depleted the field

    # ── assertions ────────────────────────────────────────────────────────────
    assert abs(d_field - (src - dec - upt_tot)) < 1e-9, "mass ledger does not close"
    assert pos[-1] < pos[0] - 5, "cell did not climb the gradient"
    assert footprint.min() < -0.1, "no depletion well — uptake not drawing the field down"

    fig, axes = plt.subplots(2, 3, figsize=(15, 8.4))
    fig.suptitle("Fig 4 (mechanistic) · cell–environment coupling — a depleting, chemotactic cell "
                 "on a reaction–diffusion field (the sense/act loop closed)", fontsize=12.5, y=0.99)

    # A — spatiotemporal field + cell track
    ax = axes[0, 0]
    im = ax.imshow(full.T, aspect="auto", origin="lower", cmap="viridis",
                   extent=[0, steps, -0.5, N - 0.5])
    ax.plot(t, pos, color=C_TRACK, lw=2.2, label="cell position")
    ax.set_title("A · Nutrient field (space × time) + cell track")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("lattice position (dx = 1)")
    ax.legend(fontsize=8, loc="upper right", framealpha=0.6)
    fig.colorbar(im, ax=ax, label="nutrient (field units)", fraction=0.046, pad=0.04)

    # B — footprint (with-cell minus no-uptake)
    ax = axes[0, 1]
    vmax = np.abs(footprint).max()
    im = ax.imshow(footprint.T, aspect="auto", origin="lower", cmap="RdBu",
                   vmin=-vmax, vmax=vmax, extent=[0, steps, -0.5, N - 0.5])
    ax.plot(t, pos, color="#000", lw=1.4, ls=":", label="cell track")
    ax.set_title("B · Cell's footprint on the field (with − without uptake)")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("lattice position")
    ax.legend(fontsize=8, loc="upper right", framealpha=0.6)
    fig.colorbar(im, ax=ax, label="Δ nutrient (depletion < 0)", fraction=0.046, pad=0.04)

    # C — trajectory + sensed nutrient
    ax = axes[0, 2]
    ax.plot(t, pos, color="#4b5bd6", lw=2, label="position (lattice)")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("lattice position", color="#4b5bd6")
    ax.tick_params(axis="y", labelcolor="#4b5bd6")
    ax.set_title("C · Cell climbs the gradient toward the source (cell 0)")
    ax.invert_yaxis()
    ax2 = ax.twinx()
    ax2.plot(t, local, color=C_UPT, lw=2, ls="--", label="sensed nutrient")
    ax2.set_ylabel("local nutrient", color=C_UPT); ax2.tick_params(axis="y", labelcolor=C_UPT)

    # D — uptake + biomass
    ax = axes[1, 0]
    ax.plot(t, upt, color=C_UPT, lw=2, label="uptake flux (MM)")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("uptake (field·tick⁻¹)", color=C_UPT)
    ax.tick_params(axis="y", labelcolor=C_UPT)
    ax.set_title("D · Saturating uptake grows biomass")
    ax2 = ax.twinx()
    ax2.plot(t, bm, color=C_BM, lw=2, ls="--", label="biomass")
    ax2.set_ylabel("biomass", color=C_BM); ax2.tick_params(axis="y", labelcolor=C_BM)

    # E — mass ledger
    ax = axes[1, 1]
    bars = ["Σ source", "−Σ decay", "−Σ uptake", "= Δfield"]
    vals = [src, -dec, -upt_tot, d_field]
    colors = [C_SRC, C_DEC, C_UPT, C_LEDG]
    ax.bar(bars, vals, color=colors)
    ax.axhline(0, color="#999", lw=0.8)
    ax.set_title(f"E · Mass ledger closes (residual {d_field-(src-dec-upt_tot):.1e})")
    ax.set_ylabel("cumulative field mass")
    for i, v in enumerate(vals):
        ax.annotate(f"{v:+.2f}", (i, v), ha="center",
                    va="bottom" if v >= 0 else "top", fontsize=8)

    # F — matched-null controls
    ax = axes[1, 2]
    labels = ["full", "no-uptake", "no-motility", "zero-grad"]
    disp = [abs(pos[0] - pos[-1]),
            abs(float(rows_nu[0]["position"]) - float(rows_nu[-1]["position"])),
            abs(float(rows_nm[0]["position"]) - float(rows_nm[-1]["position"])),
            abs(float(rows_zg[0]["position"]) - float(rows_zg[-1]["position"]))]
    grow = [bm[-1] - bm[0],
            float(rows_nu[-1]["biomass"]) - float(rows_nu[0]["biomass"]),
            float(rows_nm[-1]["biomass"]) - float(rows_nm[0]["biomass"]),
            float(rows_zg[-1]["biomass"]) - float(rows_zg[0]["biomass"])]
    x = np.arange(len(labels)); w = 0.38
    ax.bar(x - w / 2, disp, w, color="#4b5bd6", label="displacement (lattice)")
    ax.bar(x + w / 2, grow, w, color=C_BM, label="biomass gained")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8.5)
    ax.set_title("F · Matched-null controls isolate each arm")
    ax.legend(fontsize=8)
    ax.annotate("no-uptake: no growth\nno-motility: no move\nzero-grad: no drift",
                (0.02, 0.98), xycoords="axes fraction", fontsize=7.5, va="top", color="#555")

    for ax in [axes[0, 2], axes[1, 0], axes[1, 1], axes[1, 2]]:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(True, alpha=0.2, lw=0.5)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    print(f"  cell {pos[0]:.0f}→{pos[-1]:.1f} lattice; biomass {bm[0]:.1f}→{bm[-1]:.1f}; "
          f"well depth {-footprint.min():.3f}; ledger residual {d_field-(src-dec-upt_tot):.1e}")


if __name__ == "__main__":
    main()
