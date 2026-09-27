#!/usr/bin/env python
"""The *cell-cell-coupling* study's "response of the contract" figure.

The §Cell-cell coupling pattern (no dedicated paper figure) demands a typed
relation between two real CPM cells sharing ONE diffusing nutrient field through
one N-cell coupling process (``CpmColonyField``), each running its own dynamic-FBA
step at its own lattice footprint. The compiled executables realize two branches
of that relation, and this figure measures every curve off the REAL running
composites — not a re-plot of the baked movie:

  * COMPETITION (``cellcell-compete``) — two glucose competitors differing only in
    uptake capacity (glucose_vmax 10 vs 4) on one shared field; the stronger cell
    excludes the weaker by resource preemption (biomass 237.9 vs 64.5 = 3.69x;
    CPM volume 3511 vs 81 px).
  * CROSS-FEEDING (``cellcell-crossfeed``) — a consumer seeded outside the glucose
    depot (local_glucose == 0) grows on the secretor's diffused acetate plume
    alone (biomass 1.25 -> 3.79; local_acetate -> 1.30). The secretor-KNOCKOUT
    control (``cellcell-crossfeed-knockout``) removes the acetate source and the
    consumer flatlines at its 1.25 seed — the necessity control for the handoff.
  * SUBSTITUTABILITY (``cellcell-compete-mm``) — the SAME colony interface with
    each cell's dFBA metabolism swapped for a cobra-free Michaelis-Menten
    surrogate reproduces the competition ratio within ~6% (3.69x vs 3.47x).

Outputs into the study's visualizations/:
  cell-cell-coupling-response.svg / .png
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "meta_modelers_guide" / "composites"
VIZ = ROOT / "workspace" / "studies" / "cell-cell-coupling" / "visualizations"

# Book palette — the guide's teal family + a warm accent for the second role/mechanism.
INK, TEAL, TEAL_L, WARM, WARM_L, GRID = "#16211f", "#0d6e6b", "#3f9e99", "#a5620f", "#c98a3a", "#c9d3d1"
GREY = "#7a8582"
KO_RED = "#9e2b1f"
TOTAL = 20.0

_CORE = None


def _core():
    global _CORE
    if _CORE is None:
        _CORE = build_core()
    return _CORE


def _run(stem, total_time=TOTAL):
    """Run the pre-compiled executable arm; return its emitter time-series.

    Returns a dict where map[float] leaves (biomass, volume, local_*) come back as
    ``{cell_id: np.array-over-time}``, field arrays (glucose, acetate) reduce to a
    field-wide total array, and ``time`` is the tick array.
    """
    st = json.loads((COMPOSITES / f"{stem}.composite.json").read_text())["state"]
    sim = Composite({"state": st}, core=_core())
    sim.run(total_time)
    rows = gather_emitter_results(sim)[("emitter",)]
    time = np.array([float(r.get("time", i)) for i, r in enumerate(rows)])

    def field_total(key):
        return np.array([float(np.asarray(r[key], dtype=float).sum()) for r in rows])

    def per_cell(key):
        ids = sorted({cid for r in rows for cid in r.get(key, {})})
        out = {}
        for cid in ids:
            out[cid] = np.array([float(r.get(key, {}).get(cid, np.nan)) for r in rows])
        return out

    return {
        "time": time,
        "biomass": per_cell("biomass"),
        "volume": per_cell("volume"),
        "local_glucose": per_cell("local_glucose"),
        "local_acetate": per_cell("local_acetate"),
        "glucose_total": field_total("glucose"),
        "acetate_total": field_total("acetate"),
    }


def render():
    VIZ.mkdir(parents=True, exist_ok=True)
    head = {}

    comp = _run("cellcell-compete")
    xf = _run("cellcell-crossfeed")
    ko = _run("cellcell-crossfeed-knockout")
    mm = _run("cellcell-compete-mm")

    # ── competition headline ──────────────────────────────────────────────────
    cb1, cb2 = comp["biomass"]["1"], comp["biomass"]["2"]
    cv1, cv2 = comp["volume"]["1"], comp["volume"]["2"]
    head["compete_biomass"] = [round(float(cb1[-1]), 1), round(float(cb2[-1]), 1)]
    head["compete_biomass_ratio"] = round(float(cb1[-1] / cb2[-1]), 3)
    head["compete_volume_px"] = [round(float(cv1[-1]), 0), round(float(cv2[-1]), 0)]
    head["compete_loser_vs_seed"] = round(float(cb2[-1] / 1.25), 1)

    # ── cross-feeding + knockout necessity control ─────────────────────────────
    xf_consumer = xf["biomass"]["2"]           # consumer is id 2 in the cross-feed
    xf_acet = xf["local_acetate"]["2"]
    xf_gluc = xf["local_glucose"]["2"]
    ko_consumer = ko["biomass"]["1"]           # consumer is the only cell (id 1) in KO
    seed = float(xf_consumer[np.isfinite(xf_consumer)][0])  # id 2 absent at t=0; first finite = 1.25 seed
    head["crossfeed_consumer_biomass"] = [round(seed, 2), round(float(xf_consumer[-1]), 2)]
    head["crossfeed_consumer_local_acetate"] = round(float(xf_acet[-1]), 2)
    head["crossfeed_consumer_local_glucose"] = round(float(xf_gluc[-1]), 3)
    head["knockout_consumer_biomass_final"] = round(float(ko_consumer[-1]), 3)

    # ── dFBA vs MM colony substitutability ─────────────────────────────────────
    mb1, mb2 = float(mm["biomass"]["1"][-1]), float(mm["biomass"]["2"][-1])
    mm_ratio = mb1 / mb2
    dfba_ratio = float(cb1[-1] / cb2[-1])
    head["mm_biomass"] = [round(mb1, 1), round(mb2, 1)]
    head["mm_ratio"] = round(mm_ratio, 3)
    head["ratio_divergence_pct"] = round(abs(mm_ratio - dfba_ratio) / dfba_ratio * 100, 1)

    # ── figure: 2x2 response panels ────────────────────────────────────────────
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": "#3a4744",
                         "axes.labelcolor": INK, "text.color": INK,
                         "xtick.color": INK, "ytick.color": INK})
    fig, ax = plt.subplots(2, 2, figsize=(11.8, 8.2), dpi=120)

    def _clean(a):
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
        a.grid(True, color=GRID, alpha=0.5, lw=0.6)

    # (A) COMPETITION — biomass trajectories, winner vs loser
    a = ax[0, 0]
    a.plot(comp["time"], cb1, color=TEAL, lw=2.8, label="fast cell  (glucose_vmax 10)")
    a.plot(comp["time"], cb2, color=WARM, lw=2.4, ls="--", label="slow cell  (glucose_vmax 4)")
    a.annotate(f"{head['compete_biomass'][0]}", (comp["time"][-1], cb1[-1]),
               (comp["time"][-1] - 5.4, cb1[-1] * 0.94), fontsize=9, color=TEAL, weight="bold")
    a.annotate(f"{head['compete_biomass'][1]}\n(still {head['compete_loser_vs_seed']}x its 1.25 seed)",
               (comp["time"][-1], cb2[-1]), (comp["time"][-1] - 7.6, cb2[-1] + 26),
               fontsize=8, color=WARM)
    a.annotate(f"{head['compete_biomass_ratio']}x margin", (13.5, 150), fontsize=11,
               color=INK, weight="bold")
    a.set_title("competition — the stronger cell excludes the weaker", color=INK, fontsize=10)
    a.set_xlabel("time (ticks)"); a.set_ylabel("per-cell biomass")
    a.legend(frameon=False, fontsize=8.5, loc="upper left")
    _clean(a)

    # (B) COMPETITION — CPM lattice volume asymmetry (superlinear preemption)
    a = ax[0, 1]
    a.plot(comp["time"], cv1, color=TEAL, lw=2.8, label="fast cell")
    a.plot(comp["time"], cv2, color=WARM, lw=2.4, ls="--", label="slow cell")
    a.set_yscale("symlog", linthresh=100)
    a.annotate(f"{int(head['compete_volume_px'][0])} px\n(~97.5% of the 3600-px lattice)",
               (comp["time"][-1], cv1[-1]), (7.0, 700), fontsize=8, color=TEAL)
    a.annotate(f"{int(head['compete_volume_px'][1])} px  (displaced, not excluded)",
               (comp["time"][-1], cv2[-1]), (9.4, 150), fontsize=8, color=WARM,
               arrowprops=dict(arrowstyle="-", color=WARM, lw=0.8))
    a.set_title("volume tracks biomass — 3511 vs 81 px (43x)", color=INK, fontsize=10)
    a.set_xlabel("time (ticks)"); a.set_ylabel("CPM lattice volume (px, symlog)")
    a.legend(frameon=False, fontsize=8.5, loc="center left")
    _clean(a)

    # (C) CROSS-FEEDING — consumer grows on the acetate plume; knockout kills it
    a = ax[1, 0]
    a.plot(xf["time"], xf_consumer, color=TEAL, lw=2.8, label="consumer (cross-feed)")
    a.plot(ko["time"], ko_consumer, color=KO_RED, lw=2.4, ls="--",
           label="consumer (secretor knockout)")
    a.axhline(1.25, ls=":", color=GREY, lw=1)
    a.annotate("1.25 seed", (0.4, 1.25), (0.6, 1.55), fontsize=8, color=GREY)
    a.annotate(f"1.25 -> {head['crossfeed_consumer_biomass'][1]}\n(on acetate alone)",
               (xf["time"][-1], xf_consumer[-1]), (10.5, 2.55), fontsize=8.5, color=TEAL)
    a.annotate("flat at seed\n(no acetate source)", (xf["time"][-1], ko_consumer[-1]),
               (11.0, 1.30), fontsize=8, color=KO_RED)
    a2 = a.twinx()
    a2.plot(xf["time"], xf_acet, color=WARM, lw=1.8, ls=":", label="consumer local acetate")
    a2.set_ylabel("consumer local acetate", color=WARM)
    a2.tick_params(axis="y", labelcolor=WARM)
    a2.spines["top"].set_visible(False)
    a2.annotate(f"{head['crossfeed_consumer_local_acetate']}", (xf["time"][-1], xf_acet[-1]),
                (14.8, xf_acet[-1] * 0.6), fontsize=8, color=WARM)
    a.set_title("cross-feeding — consumer lives on the diffused acetate plume\n"
                "(its own local glucose stays 0)", color=INK, fontsize=10)
    a.set_xlabel("time (ticks)"); a.set_ylabel("consumer biomass", color=TEAL)
    a.tick_params(axis="y", labelcolor=TEAL)
    a.legend(frameon=False, fontsize=8, loc="upper left")
    _clean(a)

    # (D) SUBSTITUTABILITY — dFBA vs MM colony, same interface, agreeing ratio
    a = ax[1, 1]
    x = np.arange(2)
    w = 0.36
    dfba_vals = [float(cb1[-1]), float(cb2[-1])]
    mm_vals = [mb1, mb2]
    a.bar(x - w / 2, dfba_vals, w, color=TEAL, label="dFBA (real e_coli_core)")
    a.bar(x + w / 2, mm_vals, w, color=WARM_L, label="MM surrogate (cobra-free)")
    for xi, (d, m) in zip(x, zip(dfba_vals, mm_vals)):
        a.text(xi - w / 2, d + 4, f"{d:.1f}", ha="center", fontsize=8, color=TEAL)
        a.text(xi + w / 2, m + 4, f"{m:.1f}", ha="center", fontsize=8, color=WARM)
    a.set_xticks(x); a.set_xticklabels(["fast cell", "slow cell"])
    a.annotate(f"competition ratio\ndFBA {dfba_ratio:.2f}x vs MM {mm_ratio:.2f}x\n"
               f"(agree to {head['ratio_divergence_pct']}%)",
               (0.62, 175), fontsize=9, color=INK)
    a.set_title("one interface, two mechanisms (law 4)", color=INK, fontsize=10)
    a.set_ylabel("per-cell biomass at t=20")
    a.legend(frameon=False, fontsize=8.5, loc="upper right")
    _clean(a)

    fig.suptitle("Cell-cell coupling, exercised — two cells negotiate one shared nutrient field",
                 fontsize=13, color=INK, y=0.995, weight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    fig.savefig(VIZ / "cell-cell-coupling-response.svg", format="svg")
    fig.savefig(VIZ / "cell-cell-coupling-response.png", format="png")
    plt.close(fig)
    return head


if __name__ == "__main__":
    h = render()
    print(json.dumps(h, indent=2))
    print("\nwrote", VIZ / "cell-cell-coupling-response.svg")
