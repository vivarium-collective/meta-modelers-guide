#!/usr/bin/env python
"""Render Fig 11's time-series demonstration: evolution as quantities over time.

Fig 11b's principle is that evolution is a runtime place-graph rewrite: a founder
population divides (binary fission with heritable mutation), grows to carrying
capacity, and — under selection for a slowly DRIFTING optimum — its whole trait
cloud tracks that moving target. The fig-11 snapshot sequence shows the population
TOPOLOGY at two stages; this shows the same adaptation as QUANTITIES OVER TIME. It
RUNS the runnable fig11-evolution composite via build_core()+Composite for the
composite's default_n_steps and gathers the population + environment trajectory:

  * population size          — grows from the lone founder to carrying capacity;
  * mean trait (± spread)     — the trait cloud, starting far below the optimum;
  * selection_optimum         — the environment's drifting target the cloud chases.

The mean trait starts at 0 (well below the optimum) and climbs to sit on the drifting
optimum line — adaptation to a moving environment — while the population fills to
capacity. Writes a labelled two-panel PNG to the fig-11 study visualizations.

    python scripts/build_fig11_dynamics.py
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
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig11-evolution.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-11" / "visualizations" / "fig11-dynamics.png"

OPTIMUM0 = 1.0  # composite's optimum0 default (the t=0 leaf is still the raw template)

# palette (matches the study figures' teal / accent family)
C_POP, C_TRAIT, C_OPT = "#0b7a75", "#b4531f", "#4b5bd6"


def _cells(pop: dict):
    return [k for k, v in pop.items()
            if not k.startswith("_") and isinstance(v, dict) and v.get("_control") == "cell"]


def _traits(pop: dict):
    return [float(pop[k]["contents"].get("trait", 0.0)) for k in _cells(pop)]


def _optimum(env: dict) -> float:
    niche = next(k for k, v in env.items()
                 if not k.startswith("_") and isinstance(v, dict) and v.get("_control") == "niche")
    raw = env[niche]["contents"].get("selection_optimum", OPTIMUM0)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return OPTIMUM0  # t=0 leaf is still the unsubstituted "${optimum0}" template


def _run():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def main() -> None:
    rows = _run()
    t = [float(r["time"]) for r in rows]
    pop_size = [len(_cells(r["population"])) for r in rows]
    traits = [_traits(r["population"]) for r in rows]
    mean_trait = [sum(x) / len(x) if x else 0.0 for x in traits]
    lo = [min(x) if x else 0.0 for x in traits]
    hi = [max(x) if x else 0.0 for x in traits]
    optimum = [_optimum(r["environment"]) for r in rows]

    # ── the load-bearing claims: population grows to capacity; cloud tracks the
    #    drifting optimum (mean trait moves toward it over the run) ──────────────
    assert pop_size[-1] > pop_size[0], "population should grow from the founder"
    gap0 = abs(mean_trait[0] - optimum[0])
    gapN = abs(mean_trait[-1] - optimum[-1])
    assert gapN < gap0, "mean trait should move toward the drifting optimum"
    assert optimum[-1] > optimum[0], "the selection optimum should drift over the run"

    # ── figure ──────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 1, figsize=(10.5, 8), sharex=True)
    fig.suptitle("Fig 11 — evolution as a place-graph rewrite, over time",
                 fontsize=15, fontweight="bold")
    fig.text(0.5, 0.925,
             "The founder lineage divides to carrying capacity while its trait cloud tracks "
             "the environment's slowly drifting selection optimum.",
             ha="center", fontsize=10, color="#444")

    ax = axes[0]
    ax.step(t, pop_size, where="post", color=C_POP, lw=2.6, marker="o", ms=4)
    cap = max(pop_size)
    ax.axhline(cap, color="#999", ls="--", lw=1, label=f"carrying capacity ({cap})")
    ax.set_title("Population size  (founder → carrying capacity)", fontsize=11)
    ax.set_ylabel("number of cells")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(alpha=0.25)

    ax = axes[1]
    ax.fill_between(t, lo, hi, color=C_TRAIT, alpha=0.15, label="trait cloud (min–max)")
    ax.plot(t, mean_trait, color=C_TRAIT, lw=2.6, marker="o", ms=3, label="mean trait")
    ax.plot(t, optimum, color=C_OPT, lw=2.4, ls="--", label="selection optimum (drifting)")
    ax.set_title("Trait cloud tracks the drifting optimum  (adaptation to a moving target)",
                 fontsize=11)
    ax.set_ylabel("trait value")
    ax.set_xlabel("time")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.25)

    fig.tight_layout(rect=(0, 0, 1, 0.9))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150)
    plt.close(fig)
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  population   {pop_size[0]} → {pop_size[-1]}")
    print(f"  mean trait   {mean_trait[0]:.3f} → {mean_trait[-1]:.3f}")
    print(f"  optimum      {optimum[0]:.2f} → {optimum[-1]:.2f}  (gap {gap0:.3f} → {gapN:.3f})")


if __name__ == "__main__":
    main()
