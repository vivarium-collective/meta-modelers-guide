#!/usr/bin/env python
"""Render Fig 1's MECHANISTIC demonstration: ONE reusable, reversible, typed
transport process, wired differently, gives different dynamics — the paper's
composition point made measurable (topology lives in the wiring, not the code).

Runs the two composites that share the identical CompartmentTransport class and
configs on the same nested three-compartment place graph but differ only in wiring:
  fig01-mechanistic        — chain A↔B↔C  (equilibrium A:B:C = 1:4:16)
  fig01-mechanistic-star   — hub   A↔B,A↔C (equilibrium A:B:C = 1:4:4)
and writes a six-panel decisive figure to the fig-01 study visualizations:

  A  chain dynamics (A,B,C) + conserved total
  B  hub dynamics (A,B,C) + conserved total
  C  the two wirings (same process class, different topology) as node–edge diagrams
  D  mass-balance residual |A+B+C − total| over time (both topologies)
  E  equilibrium distribution chain vs hub — topology controls where quantity ends up
  F  solver verification: the k_reverse→0 limit reproduces the baseline's 0.85^n decay

Asserts the load-bearing claims (conservation; topology redirects the distribution;
0.85^n recovered) before plotting. Re-run whenever the fig01 mechanistic model changes.

    python scripts/build_fig01_mechanistic.py
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Circle

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
CHAIN = ROOT / "meta_modelers_guide" / "composites" / "fig01-mechanistic.composite.json"
STAR = ROOT / "meta_modelers_guide" / "composites" / "fig01-mechanistic-star.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-01" / "visualizations" / "fig01-mechanistic-dynamics.png"

C_A, C_B, C_C, C_TOT = "#0b7a75", "#4b5bd6", "#b4531f", "#999999"


def run(path):
    spec = json.loads(path.read_text())
    sim = Composite({"state": spec["state"]}, core=build_core())
    sim.run(spec["default_n_steps"])
    rows = gather_emitter_results(sim)[("emitter",)]
    t = np.array([float(r["time"]) for r in rows])
    A = np.array([float(r["A"]) for r in rows])
    B = np.array([float(r["B"]) for r in rows])
    C = np.array([float(r["C"]) for r in rows])
    return t, A, B, C


def decay_verification():
    state = {
        "store_a": {"_type": "concentration", "_default": 1.0},
        "store_b": {"_type": "concentration", "_default": 0.0},
        "t": {"_type": "process", "address": "local:CompartmentTransport", "interval": 1.0,
              "config": {"k_forward": 0.15, "k_reverse": 1e-9},
              "inputs": {"source": ["store_a"], "sink": ["store_b"]},
              "outputs": {"source": ["store_a"], "sink": ["store_b"]}},
        "emitter": {"_type": "step", "address": "local:RAMEmitter",
                    "config": {"emit": {"store_a": "concentration", "time": "float"}},
                    "inputs": {"store_a": ["store_a"], "time": ["global_time"]}},
    }
    sim = Composite({"state": state}, core=build_core())
    sim.run(20)
    rows = gather_emitter_results(sim)[("emitter",)]
    return np.array([float(r["store_a"]) for r in rows])


def _wiring(ax, topology):
    """Draw a tiny node–edge diagram of the place graph + transport edges."""
    ax.set_xlim(0, 10); ax.set_ylim(0, 6); ax.axis("off")
    pos = {"A": (2, 4.5), "B": (5, 4.5), "C": (8, 4.5)}
    for name, (x, y) in pos.items():
        ax.add_patch(Circle((x, y), 0.6, fc="#eef3f3", ec="#0b7a75", lw=1.6))
        ax.text(x, y, name, ha="center", va="center", fontsize=12, weight="bold", color="#0b7a75")
    # nesting hint
    ax.text(2, 3.4, "cell▸outer", ha="center", fontsize=7, color="#888")
    ax.text(5, 3.4, "cell▸inner", ha="center", fontsize=7, color="#888")
    ax.text(8, 3.4, "▸organelle", ha="center", fontsize=7, color="#888")
    edges = [("A", "B"), ("B", "C")] if topology == "chain" else [("A", "B"), ("A", "C")]
    for a, b in edges:
        (x0, y0), (x1, y1) = pos[a], pos[b]
        if topology == "star" and (a, b) == ("A", "C"):
            ax.add_patch(FancyArrowPatch((x0, y0 + 0.6), (x1, y1 + 0.6),
                         connectionstyle="arc3,rad=-0.4", arrowstyle="<->",
                         mutation_scale=14, lw=2, color="#b4531f"))
        else:
            ax.add_patch(FancyArrowPatch((x0 + 0.6, y0), (x1 - 0.6, y1), arrowstyle="<->",
                         mutation_scale=14, lw=2, color="#4b5bd6"))
    ax.text(5, 1.3, f"CompartmentTransport ×2  (same class)\ntopology: {topology}",
            ha="center", fontsize=8.5, color="#444")


def main() -> None:
    tc, Ac, Bc, Cc = run(CHAIN)
    ts, As, Bs, Cs = run(STAR)
    decay = decay_verification()

    totc = Ac + Bc + Cc
    tots = As + Bs + Cs
    assert max(abs(totc - totc[0])) < 1e-9 and max(abs(tots - tots[0])) < 1e-9, "total not conserved"
    assert Cc[-1] > 1.5 * Cs[-1], "rewiring did not redirect the distribution"
    assert max(abs(decay[n] - 0.85 ** n) for n in range(len(decay))) < 1e-6, "0.85^n not recovered"

    fig, axes = plt.subplots(2, 3, figsize=(15, 8.4))
    fig.suptitle("Fig 1 (mechanistic) · one reusable reversible transport — rewired, not reimplemented: "
                 "topology lives in the wiring and controls the dynamics", fontsize=12.5, y=0.99)

    for ax, (t, A, B, C, tot, title) in zip(
            (axes[0, 0], axes[0, 1]),
            [(tc, Ac, Bc, Cc, totc, "A · Chain A↔B↔C — quantity driven out to deep C"),
             (ts, As, Bs, Cs, tots, "B · Hub A↔B, A↔C — quantity split evenly")]):
        ax.plot(t, A, color=C_A, lw=2, label="A (outer)")
        ax.plot(t, B, color=C_B, lw=2, label="B (inner)")
        ax.plot(t, C, color=C_C, lw=2, label="C (organelle)")
        ax.plot(t, tot, color=C_TOT, lw=1.2, ls=":", label="total (conserved)")
        ax.set_title(title, fontsize=10.5)
        ax.set_xlabel("time (ticks)"); ax.set_ylabel("concentration (mol·L⁻¹)")
        ax.legend(fontsize=7.5, loc="center right")

    _wiring(axes[0, 2], "chain")
    axes[0, 2].set_title("C · Same process class, two wirings", fontsize=10.5)
    # overlay a star mini-diagram note
    axes[0, 2].text(5, 0.2, "(hub variant: A↔B and A↔C — see panel E)", ha="center", fontsize=7, color="#888")

    ax = axes[1, 0]
    ax.plot(tc, np.abs(totc - totc[0]), color=C_B, lw=1.8, label="chain")
    ax.plot(ts, np.abs(tots - tots[0]), color=C_C, lw=1.8, ls="--", label="hub")
    ax.set_title("D · Mass-balance residual |A+B+C − total|", fontsize=10.5)
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("residual")
    ax.set_yscale("symlog", linthresh=1e-16)
    ax.legend(fontsize=8)

    ax = axes[1, 1]
    x = np.arange(3); w = 0.38
    ax.bar(x - w / 2, [Ac[-1], Bc[-1], Cc[-1]], w, color=C_B, label="chain A↔B↔C")
    ax.bar(x + w / 2, [As[-1], Bs[-1], Cs[-1]], w, color=C_C, label="hub A↔B,A↔C")
    ax.set_xticks(x); ax.set_xticklabels(["A", "B", "C"])
    ax.set_title("E · Equilibrium distribution — topology controls the outcome", fontsize=10.5)
    ax.set_ylabel("final concentration")
    ax.legend(fontsize=8)
    ax.annotate("chain 1:4:16\nhub 1:4:4", (0.02, 0.98), xycoords="axes fraction",
                fontsize=8, va="top", color="#555")

    ax = axes[1, 2]
    n = np.arange(len(decay))
    ax.plot(n, 0.85 ** n, color=C_TOT, lw=4, alpha=0.4, label="analytic 0.85ⁿ")
    ax.plot(n, decay, color=C_A, lw=1.6, ls="--", label="sim (k_reverse→0)")
    ax.set_title("F · Solver verification: irreversible limit = 0.85ⁿ", fontsize=10.5)
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("store_a")
    ax.legend(fontsize=8)
    ax.annotate("equation-specific\nverification, not a discovery",
                (0.4, 0.6), xycoords="axes fraction", fontsize=7.5, color="#555")

    for ax in [axes[0, 0], axes[0, 1], axes[1, 0], axes[1, 1], axes[1, 2]]:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(True, alpha=0.2, lw=0.5)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    print(f"  chain final A:B:C = {Ac[-1]:.3f}:{Bc[-1]:.3f}:{Cc[-1]:.3f}; "
          f"hub = {As[-1]:.3f}:{Bs[-1]:.3f}:{Cs[-1]:.3f}; "
          f"max residual {max(max(abs(totc-totc[0])), max(abs(tots-tots[0]))):.1e}; "
          f"0.85ⁿ recovered to {max(abs(decay[k]-0.85**k) for k in range(len(decay))):.1e}")


if __name__ == "__main__":
    main()
