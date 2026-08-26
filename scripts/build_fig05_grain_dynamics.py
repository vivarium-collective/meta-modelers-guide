#!/usr/bin/env python
"""Render Fig 5's time-series demonstration: the grain switch triggered by viability.

Fig 5b's principle is a *grain swap on the viability function* — a process is
swapped between grains as a function of viability. This RUNS the runnable composite
(meta_modelers_guide.composites.fig05-grain-runnable): a simple external stress ramp
(StressRamp) drives the cell's viability down over the run, and a GrainSelector swaps
which grain realizes the shared interface. While viability >= threshold the cheap
COARSE process (linear yield) produces the interface's biomass; once viability slides
below the threshold, control switches to the mechanistic FINE process (saturating
Michaelis-Menten), which resolves the regime near the boundary. Exactly one grain is
active per tick, so the coarse->fine handover happens on-screen.

It writes a two-panel time-series PNG to the fig-05 study visualizations and asserts
the load-bearing claim: active_grain flips coarse->fine at the viability-threshold
crossing (+/- one tick) and biomass keeps accumulating across the switch. Re-run
whenever the fig05 dynamics or the runnable composite change.

    python scripts/build_fig05_grain_dynamics.py
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
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig05-grain-runnable.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-05" / "visualizations" / "fig05-grain-dynamics.png"

THRESHOLD = 0.5  # matches grain_selector.config.threshold in the composite

# palette (matches the study figures' teal / accent family)
C_VIAB, C_COARSE, C_FINE, C_BIO = "#0b7a75", "#4b5bd6", "#b4531f", "#1c7a77"


def _run():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def main() -> None:
    rows = _run()
    t = [float(r["time"]) for r in rows]
    viab = [float(r["viability"]) for r in rows]
    grain = [str(r["active_grain"]) for r in rows]
    bio = [float(r["biomass"]) for r in rows]

    # ── the load-bearing claims ───────────────────────────────────────────────
    # viability crosses below threshold at this tick:
    cross = next(i for i, v in enumerate(viab) if v < THRESHOLD)
    # active_grain flips coarse -> fine at this tick:
    flip = next(i for i in range(1, len(grain)) if grain[i] != grain[i - 1])
    assert grain[0] == "coarse", "should start in the coarse grain"
    assert grain[flip] == "fine" and all(g == "fine" for g in grain[flip:]), \
        "once it flips to fine it must stay fine"
    assert abs(flip - cross) <= 1, f"flip ({flip}) should track the crossing ({cross})"
    assert bio[flip - 1] > bio[0], "biomass must grow while viable (coarse)"
    assert bio[-1] < bio[flip - 1], "biomass must decay once dying (fine)"

    t_flip = t[flip]

    # ── figure ────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 1, figsize=(10, 7.2), sharex=True)
    fig.suptitle("Fig 5 — the grain switch triggered by viability",
                 fontsize=15, fontweight="bold")
    fig.text(0.5, 0.925,
             "A simple external stress ramp drives viability down; as it crosses the "
             "threshold, control switches from the COARSE process to the FINE process.",
             ha="center", fontsize=10, color="#444")

    # panel 1: viability with the threshold line + the coarse/fine regime shading
    ax = axes[0]
    ax.axhspan(0, 0, color="none")  # keep autoscale sane
    # regime shading: coarse (viable) vs fine (stressed), split at the flip tick.
    ax.axvspan(t[0], t_flip, color=C_COARSE, alpha=0.08)
    ax.axvspan(t_flip, t[-1], color=C_FINE, alpha=0.08)
    ax.plot(t, viab, color=C_VIAB, lw=2.4, marker="o", ms=3.5, label="viability")
    ax.axhline(THRESHOLD, color="#999", ls="--", lw=1.2, label=f"threshold = {THRESHOLD}")
    ax.axvline(t_flip, color="#333", ls=":", lw=1.3)
    ax.set_ylabel("viability  (0–1)")
    ax.set_title("Viability slides down past the threshold", fontsize=11)
    ax.set_ylim(0, 1.05)
    ax.grid(alpha=0.25)
    # annotate the two regimes
    ax.text(t[flip // 2], 1.0, "COARSE grain\n(viable)", ha="center", va="top",
            fontsize=9, color=C_COARSE, fontweight="bold")
    ax.text((t_flip + t[-1]) / 2, 1.0, "FINE grain\n(stressed)", ha="center", va="top",
            fontsize=9, color=C_FINE, fontweight="bold")
    ax.legend(fontsize=8, loc="lower left")

    # panel 2: biomass, shaded by active grain, switch point marked
    ax = axes[1]
    ax.axvspan(t[0], t_flip, color=C_COARSE, alpha=0.08)
    ax.axvspan(t_flip, t[-1], color=C_FINE, alpha=0.08)
    # split the biomass line at the flip so each grain's contribution shows in colour.
    ax.plot(t[:flip + 1], bio[:flip + 1], color=C_COARSE, lw=2.6, marker="o", ms=3.5,
            label="biomass — coarse (growth, viable)")
    ax.plot(t[flip:], bio[flip:], color=C_FINE, lw=2.6, marker="o", ms=3.5,
            label="biomass — fine (decay, dying)")
    ax.axvline(t_flip, color="#333", ls=":", lw=1.3)
    ax.plot([t_flip], [bio[flip]], marker="*", ms=16, color="#333", zorder=5)
    ax.annotate(f"grain flips coarse→fine\nat t = {t_flip:.0f}  (viability = {viab[flip]:.2f})",
                xy=(t_flip, bio[flip]), xytext=(t_flip + 3.5, max(bio) * 0.86),
                ha="left", fontsize=9, color="#333",
                arrowprops=dict(arrowstyle="->", color="#333", lw=1.1))
    ax.set_ylabel("biomass")
    ax.set_xlabel("time")
    ax.set_title("Biomass grows while viable (coarse), then decays once dying (fine)", fontsize=11)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, loc="upper left")

    fig.tight_layout(rect=(0, 0, 1, 0.9))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150)
    plt.close(fig)
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  viability   {viab[0]:.3f} → {viab[-1]:.3f}  (crosses {THRESHOLD} at t={cross})")
    print(f"  active_grain flips coarse→fine at t={flip}  (viability there = {viab[flip]:.3f})")
    print(f"  biomass     {bio[0]:.3f} → {bio[-1]:.3f}  (grows to the switch, then decays)")


if __name__ == "__main__":
    main()
