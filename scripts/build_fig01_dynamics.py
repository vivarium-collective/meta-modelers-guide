#!/usr/bin/env python
"""Render Fig 1's minimal demonstration: a process bigraph is EXECUTABLE.

Fig 1 is the definitional figure — a process bigraph is Milner's place graph
(nested stores/nodes) with processes wired to those nodes through typed ports.
The published Fig 1b draws that structure statically. This RUNS the smallest
honest bit of dynamics behind it (meta_modelers_guide.composites.fig01-runnable):
ONE real process (StoreTransfer) wired to TWO scalar place-graph nodes — source
``store_a`` and sink ``store_b`` — under a first-order transfer::

    dA/dt = -k*A      dB/dt = +k*A

so the source drains exponentially into the sink while the total A+B is conserved.
The point the figure makes, made runnable: give a process an update rule and the
wired stores evolve over time.

Writes a two-panel time-series PNG to the fig-01 study visualizations and asserts
the load-bearing claims: the source falls, the sink rises, and the total is
conserved to round-off. Re-run whenever the StoreTransfer dynamics or the runnable
composite change.

    python scripts/build_fig01_dynamics.py
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
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig01-runnable.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-01" / "visualizations" / "fig01-dynamics.png"

# palette (matches the study figures' teal / accent family)
C_SOURCE, C_SINK, C_TOTAL = "#b4531f", "#0b7a75", "#4b5bd6"


def _run():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def main() -> None:
    rows = _run()
    t = [float(r["time"]) for r in rows]
    a = [float(r["store_a"]) for r in rows]
    b = [float(r["store_b"]) for r in rows]
    total = [ai + bi for ai, bi in zip(a, b)]

    # ── the load-bearing claims ────────────────────────────────────────────────
    assert a[-1] < a[0], "source store_a should drain over the run"
    assert b[-1] > b[0], "sink store_b should fill over the run"
    assert max(total) - min(total) < 1e-9, "total A+B should be conserved"

    # ── figure ────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    fig.suptitle("Fig 1 — a process bigraph is an executable place-graph + processes",
                 fontsize=15, fontweight="bold")
    fig.text(0.5, 0.9,
             "One process (StoreTransfer) wired to two place-graph nodes: it drains "
             "source store_a into sink store_b — the stores evolve over time.",
             ha="center", fontsize=10, color="#444")

    ax = axes[0]
    ax.plot(t, a, color=C_SOURCE, lw=2.4, marker="o", ms=3.5, label="store_a (source)")
    ax.plot(t, b, color=C_SINK, lw=2.4, marker="o", ms=3.5, label="store_b (sink)")
    ax.set_title("The two wired stores evolve  (process → stores)", fontsize=11)
    ax.set_ylabel("store value")
    ax.set_xlabel("time")
    ax.legend(fontsize=9, loc="center right")
    ax.grid(alpha=0.25)

    ax = axes[1]
    ax.plot(t, total, color=C_TOTAL, lw=2.4, marker="o", ms=3.5)
    ax.set_title("Total store_a + store_b  (conserved by the transfer)", fontsize=11)
    ax.set_ylabel("store_a + store_b")
    ax.set_xlabel("time")
    ax.set_ylim(0.0, max(total) * 1.4 + 0.1)
    ax.grid(alpha=0.25)

    fig.tight_layout(rect=(0, 0, 1, 0.87))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150)
    plt.close(fig)
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  store_a  {a[0]:.4f} → {a[-1]:.4f}  (drains)")
    print(f"  store_b  {b[0]:.4f} → {b[-1]:.4f}  (fills)")
    print(f"  total    {total[0]:.6f} → {total[-1]:.6f}  (Δ = {max(total)-min(total):.2e})")


if __name__ == "__main__":
    main()
