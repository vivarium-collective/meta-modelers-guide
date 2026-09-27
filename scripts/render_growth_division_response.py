#!/usr/bin/env python
"""The *growth-and-division* study's "response of the contract" figure.

The §Growth and division draft process (``CpmGrowthDivision``) defines a typed
contract that demands a characteristic relation: metabolism drives a single CPM
cell's volume across ``vol_threshold`` = 80 -> the native CPM engine operation
``divide_cells`` fires -> biomass is partitioned mass-conserved across two
daughters (physical volume reset toward ``reset_target`` = 40) -> the daughters
resume growing and, coupled through ONE shared glucose field, DESYNCHRONIZE. The
compiled executable ``growth-division-spatial`` (one CPM cell on a uniform
abundant 60x60 glucose field, real per-footprint dFBA against ``e_coli_core``,
spatio-flux diffusion) realizes exactly this.

Every curve here is measured off the REAL running compiled executable -- the same
36-tick run the study's behavior tests cite -- not a re-plot of the baked movie.
The composite is stepped one tick at a time and its own ``obs`` state is read each
tick (``n_cells``, per-cell ``volume``, ``generation``/``max_generation``, and the
shared glucose ``fields``); the every-3-ticks staircase reproduces the study's
recorded 1,2,2,2,4,4,5,8,8,11,14,18 exactly.

Panels:
  (A) n_cells staircase over time -- with the 2^floor lockstep reference overlaid,
      the departure from clean powers of two annotated (tick 21: 5 cells).
  (B) per-cell CPM volume sawtooth traces -- bounded growth-cross-reset band,
      division resets visible, band [reset_target, vol_threshold] shaded.
  (C) generation/lineage composition over time -- stacked per-generation cell
      counts, with the count of coexisting generations.
  (D) shared glucose field depletion -- the weak (~3%) nutrient brake, evidence
      the staircase is bounded by lattice crowding, not starvation.

Outputs (into the study's visualizations/):
  growth-and-division-response.svg / .png
Prints the headline numbers.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from process_bigraph import Composite

from meta_modelers_guide.core import build_core

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "meta_modelers_guide" / "composites"
VIZ = ROOT / "workspace" / "studies" / "growth-and-division" / "visualizations"

STEM = "growth-division-spatial"
TOTAL_TICKS = 36
SAMPLE = 3          # the study's canonical sampling cadence (every 3 ticks)
VOL_THRESHOLD = 80.0
RESET_TARGET = 40.0

# Book palette -- the guide's teal family + a warm accent + a cool->warm generation ramp.
INK = "#16211f"
TEAL = "#0d6e6b"
TEAL_L = "#3f9e99"
WARM = "#a5620f"
WARM_L = "#c98a3a"
GRID = "#c9d3d1"
MUTE = "#7a8582"
# per-generation ramp (gen 0 -> gen 4), cool founder to warm youngest
GEN_RAMP = ["#0d3b3a", "#0d6e6b", "#3f9e99", "#c98a3a", "#c2591f"]


def _run_traces(total_ticks=TOTAL_TICKS):
    """Step the compiled executable one tick at a time; read its own ``obs`` state
    each tick. Returns per-tick arrays measured straight off the engine."""
    state = json.loads((COMPOSITES / f"{STEM}.composite.json").read_text())["state"]
    core = build_core()
    sim = Composite({"state": state}, core=core)

    ticks = []
    n_cells = []
    max_gen = []
    glucose_total = []
    per_cell_vol = {}          # cid(int) -> {tick: volume}
    gen_counts = []            # per tick: {generation:int -> count}
    for tick in range(1, total_ticks + 1):
        sim.run(1)
        obs = sim.state["obs"]
        ticks.append(tick)
        n_cells.append(float(obs["n_cells"]))
        max_gen.append(float(obs["max_generation"]))
        for cid, v in dict(obs["volume"]).items():
            per_cell_vol.setdefault(int(cid), {})[tick] = float(v)
        gens = dict(obs["generation"])
        gen_counts.append({int(g): c for g, c in Counter(int(g) for g in gens.values()).items()})
        glucose_total.append(float(np.asarray(sim.state["fields"]["glucose"], dtype=float).sum()))

    return {
        "ticks": np.array(ticks, dtype=float),
        "n_cells": np.array(n_cells),
        "max_gen": np.array(max_gen),
        "glucose_total": np.array(glucose_total),
        "per_cell_vol": per_cell_vol,
        "gen_counts": gen_counts,
    }


def _clean(a):
    for sp in ("top", "right"):
        a.spines[sp].set_visible(False)
    a.grid(True, color=GRID, alpha=0.5, lw=0.6)


def render():
    VIZ.mkdir(parents=True, exist_ok=True)
    d = _run_traces()
    ticks = d["ticks"]
    n = d["n_cells"]

    # --- canonical every-3-ticks staircase (reproduces the study's recorded run) ---
    idx3 = np.arange(SAMPLE - 1, TOTAL_TICKS, SAMPLE)   # ticks 3,6,...,36
    t3 = ticks[idx3]
    n3 = n[idx3]
    ref3 = np.array([2.0 ** math.floor(math.log2(v)) if v >= 1 else 0.0 for v in n3])
    offp2 = ~np.isclose(n3, ref3)                       # samples off a clean power of two
    powers = {1.0, 2.0, 4.0, 8.0, 16.0, 32.0}
    first_off_tick = int(t3[[i for i, v in enumerate(n3) if v not in powers][0]])

    # headline numbers
    all_vols = [v for tr in d["per_cell_vol"].values() for v in tr.values()]
    final_gc = d["gen_counts"][-1]
    glc0, glc1 = float(d["glucose_total"][0]), float(d["glucose_total"][-1])
    head = {
        "final_n_cells": int(n3[-1]),
        "staircase_every3": [int(x) for x in n3],
        "max_generation": int(d["max_gen"][-1]),
        "volume_band_px": [round(min(all_vols), 1), round(max(all_vols), 1)],
        "n_generations_at_end": len(final_gc),
        "generation_composition_at_end": {int(g): int(c) for g, c in sorted(final_gc.items())},
        "desync_tick": first_off_tick,
        "off_power_of_two_samples": [int(x) for x in n3[offp2]],
        "glucose_pct_depletion": round((glc0 - glc1) / glc0 * 100, 2),
    }

    plt.rcParams.update({"font.size": 9, "axes.edgecolor": "#3a4744",
                         "axes.labelcolor": INK, "text.color": INK,
                         "xtick.color": INK, "ytick.color": INK})
    fig, ax = plt.subplots(2, 2, figsize=(12.0, 8.6), dpi=120)

    # (A) n_cells staircase vs the 2^floor lockstep reference ----------------------
    a = ax[0, 0]
    a.step(t3, ref3, where="post", color=MUTE, lw=1.8, ls="--",
           label="2$^{\\lfloor \\log_2 n\\rfloor}$ lockstep reference")
    a.step(t3, n3, where="post", color=TEAL, lw=2.6, label="n_cells (measured)")
    a.plot(t3[~offp2], n3[~offp2], "o", color=TEAL, ms=6, zorder=4)
    a.plot(t3[offp2], n3[offp2], "o", color=WARM, ms=7, zorder=5,
           label="off powers of two (desync)")
    for xi, yi in zip(t3[offp2], n3[offp2]):
        a.annotate(f"{int(yi)}", (xi, yi), (xi - 0.4, yi + 0.7), fontsize=8, color=WARM,
                   ha="center")
    a.axvline(first_off_tick, ls=":", color=WARM, lw=1)
    a.annotate(f"departs 2$^k$\n@ tick {first_off_tick} ({int(n3[list(t3).index(first_off_tick)])} cells)",
               (first_off_tick, 3.0), (first_off_tick + 1.0, 6.5), fontsize=8.5, color=WARM,
               arrowprops=dict(arrowstyle="->", color=WARM, lw=0.9))
    a.set_title(f"population staircase -> {head['final_n_cells']} cells "
                f"(never shrinks)", color=INK, fontsize=10)
    a.set_xlabel("time (ticks)"); a.set_ylabel("n_cells")
    a.legend(frameon=False, fontsize=8, loc="upper left")
    _clean(a)

    # (B) per-cell CPM volume sawtooth traces --------------------------------------
    a = ax[0, 1]
    a.axhspan(RESET_TARGET, VOL_THRESHOLD, color=TEAL_L, alpha=0.12, zorder=0)
    a.axhline(VOL_THRESHOLD, ls="--", color=WARM, lw=1.3)
    a.axhline(RESET_TARGET, ls="--", color=MUTE, lw=1.1)
    a.annotate("vol_threshold = 80  (divide)", (ticks[1], VOL_THRESHOLD),
               (ticks[1], VOL_THRESHOLD + 1.5), fontsize=8, color=WARM)
    a.annotate("reset_target = 40", (ticks[1], RESET_TARGET),
               (ticks[1], RESET_TARGET - 5.5), fontsize=8, color=MUTE)
    for cid, tr in sorted(d["per_cell_vol"].items()):
        xs = np.array(sorted(tr.keys()), dtype=float)
        ys = np.array([tr[int(x)] for x in xs])
        a.plot(xs, ys, color=TEAL, lw=1.1, alpha=0.55)
    vb = head["volume_band_px"]
    a.set_title(f"per-cell volume sawtooth  (bounded {vb[0]:.0f}-{vb[1]:.0f} px, "
                f"no runaway / no phantom)", color=INK, fontsize=10)
    a.set_xlabel("time (ticks)"); a.set_ylabel("CPM volume (lattice px)")
    a.set_ylim(0, VOL_THRESHOLD + 8)
    _clean(a)

    # (C) generation/lineage composition over time (stacked counts) ----------------
    a = ax[1, 0]
    gmax = int(d["max_gen"][-1])
    gens = list(range(gmax + 1))
    stacks = np.zeros((len(gens), len(ticks)))
    for j, gc in enumerate(d["gen_counts"]):
        for g, c in gc.items():
            stacks[g, j] = c
    a.stackplot(ticks, *stacks, labels=[f"gen {g}" for g in gens],
                colors=[GEN_RAMP[g % len(GEN_RAMP)] for g in gens], alpha=0.9)
    # count of coexisting generations, on a twin axis
    a2 = a.twinx()
    n_distinct = np.array([len(gc) for gc in d["gen_counts"]])
    a2.plot(ticks, n_distinct, color=INK, lw=1.8, ls=":", label="distinct generations")
    a2.set_ylabel("# coexisting generations", color=INK)
    a2.set_ylim(0, gmax + 2)
    a2.spines["top"].set_visible(False)
    a.set_title(f"lineage composition -> {head['n_generations_at_end']} generations coexist "
                f"(max_gen {gmax})", color=INK, fontsize=10)
    a.set_xlabel("time (ticks)"); a.set_ylabel("cells by generation")
    a.legend(frameon=False, fontsize=7.5, loc="upper left", ncol=2)
    _clean(a)

    # (D) shared glucose field depletion -- the weak nutrient brake ----------------
    a = ax[1, 1]
    g = d["glucose_total"]
    a.plot(ticks, g, color=TEAL, lw=2.6)
    a.fill_between(ticks, g, g.min(), color=TEAL_L, alpha=0.12)
    pct = head["glucose_pct_depletion"]
    a.annotate(f"only {pct:.1f}% depleted over 36 ticks\n({glc0:.0f} -> {glc1:.0f} field units)\n"
               f"-> staircase bounded by lattice crowding,\n    not starvation",
               (ticks[len(ticks) // 2], g[len(g) // 2]),
               (ticks[3], glc0 - (glc0 - glc1) * 0.55), fontsize=8.5, color="#3a4744")
    a.set_title("shared glucose field -- weak nutrient brake", color=INK, fontsize=10)
    a.set_xlabel("time (ticks)"); a.set_ylabel("field-wide glucose (arb. units)")
    a.ticklabel_format(axis="y", style="plain")
    _clean(a)

    fig.suptitle("Growth and division, exercised -- one cell compounds into a desynchronizing lineage",
                 fontsize=13, color=INK, y=0.996, weight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.975))
    fig.savefig(VIZ / "growth-and-division-response.svg", format="svg")
    fig.savefig(VIZ / "growth-and-division-response.png", format="png")
    plt.close(fig)
    return head


if __name__ == "__main__":
    h = render()
    print(json.dumps(h, indent=2))
    print("\nwrote", VIZ / "growth-and-division-response.svg")
