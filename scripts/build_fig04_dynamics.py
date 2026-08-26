#!/usr/bin/env python
"""Render Fig 4's time-series demonstration: the environment drives the interface ports.

Fig 4b's principle is cell↔environment coupling — the environment's fields DRIVE the
cell's interface ports. This RUNS the runnable composite
(meta_modelers_guide.composites.fig04-runnable): a real length-9 diffusing chemical
grid seeded as a nutrient gradient (low at index 0, high at index 8), with the single
cell at interior index 4. Over the run the cell senses its LOCAL field through one
typed interface and acts back on the shared environment:

  * local sensed field   — the chemical concentration at the cell's grid index;
  * uptake flux           — chemical taken up per step, which TRACKS the local field;
  * accumulated mass       — grows under supply (biomass yield on uptake);
  * cell location          — drifts UP-gradient (chemotaxis) toward the high-nutrient side.

It writes a four-panel time-series PNG to the fig-04 study visualizations and asserts
the load-bearing claim: per-step uptake tracks the local sensed field (they rise/fall
together). Re-run whenever the fig04 dynamics or the runnable composite change.

    python scripts/build_fig04_dynamics.py
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
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig04-runnable.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-04" / "visualizations" / "fig04-dynamics.png"

CELL_INDEX = 4  # matches single_cell_processes.config.cell_index in the composite

# palette (matches the study figures' teal / accent family)
C_FIELD, C_UPTAKE, C_MASS, C_LOC = "#0b7a75", "#b4531f", "#1c7a77", "#4b5bd6"


def _run():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def _corr(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a) ** 0.5
    vb = sum((y - mb) ** 2 for y in b) ** 0.5
    return cov / (va * vb) if va and vb else 0.0


def main() -> None:
    rows = _run()
    t = [float(r["time"]) for r in rows]
    local = [float(r["chemical_field"][str(CELL_INDEX)]) for r in rows]
    cum_uptake = [float(r["uptake_flux"]) for r in rows]
    mass = [float(r["mass"]) for r in rows]
    loc = [float(r["location"]) for r in rows]

    # per-step uptake is the increment of the cumulative uptake_flux the interface
    # wrote back to the environment each tick (the instantaneous flux through the port).
    step_uptake = [0.0] + [cum_uptake[i] - cum_uptake[i - 1] for i in range(1, len(cum_uptake))]

    # ── the load-bearing claim: uptake TRACKS the local sensed field ──────────
    # compare on the active window (skip t=0 where nothing has been taken up yet).
    r = _corr(local[1:], step_uptake[1:])
    assert r > 0.99, f"per-step uptake should track the local field (corr={r:.3f})"
    assert mass[-1] > mass[0], "mass should accumulate under nutrient supply"
    assert loc[-1] > loc[0], "cell should drift up-gradient (chemotaxis)"

    # ── figure ────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
    fig.suptitle("Fig 4 — the environment's fields drive the cell's interface ports",
                 fontsize=15, fontweight="bold")
    fig.text(0.5, 0.925,
             "A single cell at grid index 4 senses its LOCAL nutrient field through one typed "
             "interface, then acts back on the shared environment.",
             ha="center", fontsize=10, color="#444")

    ax = axes[0][0]
    ax.plot(t, local, color=C_FIELD, lw=2.2, marker="o", ms=3)
    ax.set_title("Local sensed chemical field  (environment → cell)", fontsize=11)
    ax.set_ylabel(f"field at cell index {CELL_INDEX}")
    ax.grid(alpha=0.25)

    ax = axes[0][1]
    ax.plot(t, step_uptake, color=C_UPTAKE, lw=2.2, marker="o", ms=3)
    ax.set_title(f"Uptake flux per step  (tracks local field, r={r:.3f})", fontsize=11)
    ax.set_ylabel("uptake flux / step")
    ax.grid(alpha=0.25)

    ax = axes[1][0]
    ax.plot(t, mass, color=C_MASS, lw=2.2, marker="o", ms=3)
    ax.set_title("Accumulated mass  (grows on uptake)", fontsize=11)
    ax.set_ylabel("cell mass")
    ax.set_xlabel("time")
    ax.grid(alpha=0.25)

    ax = axes[1][1]
    ax.plot(t, loc, color=C_LOC, lw=2.2, marker="o", ms=3)
    ax.axhline(CELL_INDEX, color="#999", ls="--", lw=1, label="start (index 4)")
    ax.set_title("Cell location  (chemotactic drift UP-gradient →)", fontsize=11)
    ax.set_ylabel("grid location")
    ax.set_xlabel("time")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.25)

    fig.tight_layout(rect=(0, 0, 1, 0.9))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150)
    plt.close(fig)
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  local field  {local[0]:.4f} → {local[-1]:.4f}")
    print(f"  uptake/step  {step_uptake[1]:.4f} → {step_uptake[-1]:.4f}  (corr with local = {r:.3f})")
    print(f"  mass         {mass[0]:.4f} → {mass[-1]:.4f}")
    print(f"  location     {loc[0]:.4f} → {loc[-1]:.4f}  (up-gradient drift +{loc[-1]-loc[0]:.4f})")


if __name__ == "__main__":
    main()
