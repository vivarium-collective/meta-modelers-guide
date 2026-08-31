#!/usr/bin/env python
"""Render Fig 2's demonstration: multi-timestepping through a shared store.

Fig 2 is the orchestration overview. Its panel (a) — multi-timestepping — is the
part with genuine, non-forced dynamics: processes updating at DIFFERENT rates
through a SHARED store, interleaved on one clock. This RUNS the smallest honest
version (meta_modelers_guide.composites.fig02-runnable): two processes share one
pool store —

  * FastProduction (interval 1.0) adds to pool.molecules every base tick;
  * SlowConversion (interval 5.0) fires once per 5 ticks, converting a fraction of
    the accumulated pool into pool.biomass and drawing it back out.

molecules ramps up on the fast clock and saws down each time the slow process
fires, while biomass advances in coarse staircase steps on the slow clock — two
rates coordinated through the one shared store (exactly Fig 2a). Panels (b)
workflow-DAG and (c) event-driven rewrites stay schematic; this demonstrates (a).

Writes a two-panel time-series PNG to the fig-02 study visualizations and asserts
the load-bearing claim: the fast pool fill updates far more often than the slow
biomass conversion, and each slow firing conserves what it moves. Re-run whenever
the demo processes or the runnable composite change.

    python scripts/build_fig02_dynamics.py
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
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig02-runnable.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-02" / "visualizations" / "fig02-dynamics.png"

# palette (matches the study figures' teal / accent family)
C_FAST, C_SLOW = "#b4531f", "#0b7a75"


def _run():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def _n_changes(series):
    return sum(1 for x, y in zip(series, series[1:]) if abs(y - x) > 1e-9)


def main() -> None:
    rows = _run()
    t = [float(r["time"]) for r in rows]
    mol = [float(r["molecules"]) for r in rows]
    bio = [float(r["biomass"]) for r in rows]

    fast_changes = _n_changes(mol)
    slow_changes = _n_changes(bio)

    # ── the load-bearing claim: the two processes run at DIFFERENT rates ───────
    assert fast_changes > 2 * slow_changes, (
        f"fast pool ({fast_changes} updates) should update far more often than "
        f"slow biomass ({slow_changes} updates)")
    assert slow_changes >= 2, "the slow process should fire multiple times over the run"
    # the fast fill is a sawtooth: it both rises (fast) and drops (each slow draw).
    assert any(y > x for x, y in zip(mol, mol[1:])), "molecules should rise on the fast clock"
    assert any(y < x for x, y in zip(mol, mol[1:])), "molecules should saw down on each slow conversion"

    # ── figure ────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharex=True)
    fig.suptitle("Fig 2a — multi-timestepping: two rates coordinated through a shared store",
                 fontsize=14.5, fontweight="bold")
    fig.text(0.5, 0.9,
             "A fast process fills the shared pool every tick; a slow process fires "
             "every 5 ticks, converting the pool into biomass.",
             ha="center", fontsize=10, color="#444")

    ax = axes[0]
    ax.plot(t, mol, color=C_FAST, lw=2.4, marker="o", ms=3.5)
    ax.set_title(f"pool.molecules — fast clock  ({fast_changes} updates, sawtooth)", fontsize=11)
    ax.set_ylabel("molecules (shared pool)")
    ax.set_xlabel("time")
    ax.grid(alpha=0.25)

    ax = axes[1]
    ax.step(t, bio, where="post", color=C_SLOW, lw=2.4, marker="o", ms=3.5)
    ax.set_title(f"pool.biomass — slow clock  ({slow_changes} updates, staircase)", fontsize=11)
    ax.set_ylabel("biomass (shared pool)")
    ax.set_xlabel("time")
    ax.grid(alpha=0.25)

    fig.tight_layout(rect=(0, 0, 1, 0.87))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150)
    plt.close(fig)
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  molecules  {fast_changes} updates (fast)  range {min(mol):.2f}..{max(mol):.2f}")
    print(f"  biomass    {slow_changes} updates (slow)  {bio[0]:.2f} → {bio[-1]:.2f}")


if __name__ == "__main__":
    main()
