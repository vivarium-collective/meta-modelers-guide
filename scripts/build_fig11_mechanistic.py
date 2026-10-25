#!/usr/bin/env python
"""Render Fig 11's MECHANISTIC demonstration: a real Wright–Fisher population under
selection, mutation and heritable variation — quantitative, many-seed, with
ancestry.

Unlike the baseline (one fixed seed at capacity 12, where drift dominates and the
mean "tracking" the optimum is expected by design), this runs the mechanistic
EvolvingPopulation engine at a large carrying capacity across MANY independent
replicates, and writes a six-panel decisive figure to the fig-11 visualizations:

  A  trait-density heatmap (generation × trait) with the moving optimum overlaid
  B  lineage genealogy (a small population) — ancestry edges coloured by trait
  C  replicate mean-trait trajectories with 90% intervals, tracking the optimum
  D  selection vs neutral: mean lag with intervals (selection tracks; drift wanders)
  E  adaptation failure: final lag vs drift rate (runaway beyond a critical rate)
  F  executable-trait mode: evolved mean tracks the derived metabolic optimum a*

It asserts the load-bearing claims (selection beats drift; lag grows with drift;
heritability ≈ 1) before plotting. Re-run whenever the fig11 mechanistic model
changes.

    python scripts/build_fig11_mechanistic.py
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

from meta_modelers_guide.handlers_fig11_mech import EvolvingPopulation, ensemble

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "workspace" / "studies" / "fig-11" / "visualizations" / "fig11-mechanistic-dynamics.png"

GENS = 40
C_OPT, C_SEL, C_NEU, C_FAIL = "#c0392b", "#0b7a75", "#b4531f", "#7a5195"


def main() -> None:
    # A — trait density heatmap (one representative large-N run)
    pop = EvolvingPopulation(seed=1, capacity=600, drift=0.06, sel_strength=1.0, mut_sigma=0.12)
    hist = pop.run(GENS)
    edges = np.linspace(-1.0, 3.5, 70)
    dens = np.array([np.histogram(s, bins=edges, density=True)[0] for s in hist["snapshots"]])

    # C/D — many-seed ensembles
    m_sel, lag_sel, opt = ensemble(generations=GENS, n_seeds=40, drift=0.06, sel_strength=1.0,
                                   mut_sigma=0.12, capacity=300)
    m_neu, lag_neu, _ = ensemble(generations=GENS, n_seeds=40, drift=0.06, neutral=True, capacity=300)

    # E — adaptation-failure sweep
    drifts = [0.02, 0.05, 0.10, 0.20, 0.35, 0.55]
    fail = [ensemble(generations=GENS, n_seeds=20, drift=d, sel_strength=1.0, mut_sigma=0.12,
                     capacity=300)[1][:, -1] for d in drifts]

    # F — uptake executable-trait mode
    m_up, lag_up, opt_up = ensemble(generations=50, n_seeds=25, fitness_mode="uptake",
                                    drift=0.05, mut_sigma=0.05, capacity=300,
                                    trait_mean0=0.4, trait_sd0=0.1)

    # B — lineage genealogy (small population; track trait by lineage)
    gpop = EvolvingPopulation(seed=7, capacity=24, drift=0.06, sel_strength=1.0, mut_sigma=0.18)
    traj = [gpop.traits.copy()]
    for _ in range(GENS):
        gpop.step(); traj.append(gpop.traits.copy())
    traj = np.array(traj)            # [gens+1, N]
    anc = gpop.ancestry              # [gens][N] parent indices

    # ── assertions ──────────────────────────────────────────────────────────────
    assert lag_sel[:, -1].mean() < 0.4 * lag_neu[:, -1].mean(), "selection should beat neutral drift"
    assert fail[-1].mean() > 4 * fail[0].mean(), "lag should run away at high drift (adaptation failure)"
    par, off = EvolvingPopulation(seed=3, capacity=400, mut_sigma=0.12).parent_offspring()
    assert abs(np.polyfit(par, off, 1)[0] - 1.0) < 0.1, "clonal+mutation heritability ≈ 1"

    fig, axes = plt.subplots(2, 3, figsize=(15, 8.6))
    fig.suptitle("Fig 11 (mechanistic) · evolution as Wright–Fisher population genetics — "
                 "selection vs drift, quantified over many seeds", fontsize=12.5, y=0.99)

    # A
    ax = axes[0, 0]
    im = ax.imshow(dens.T, aspect="auto", origin="lower", cmap="viridis",
                   extent=[0, GENS, edges[0], edges[-1]])
    ax.plot(range(len(hist["optimum"])), hist["optimum"], color="#fff", lw=2, label="optimum (drifting)")
    ax.set_title("A · Trait density over generations (N=600)")
    ax.set_xlabel("generation"); ax.set_ylabel("trait value")
    ax.legend(fontsize=8, loc="upper left", framealpha=0.5)
    fig.colorbar(im, ax=ax, label="density", fraction=0.046, pad=0.04)

    # B — genealogy coloured by trait
    ax = axes[0, 1]
    segs, cols = [], []
    for g in range(len(anc)):
        for child, parent in enumerate(anc[g]):
            segs.append([(g, traj[g][parent]), (g + 1, traj[g + 1][child])])
            cols.append(traj[g + 1][child])
    lc = LineCollection(segs, cmap="plasma", array=np.array(cols), lw=0.8, alpha=0.7)
    ax.add_collection(lc)
    ax.plot(range(len(hist["optimum"])), hist["optimum"], color="#c0392b", lw=1.6, ls="--", label="optimum")
    ax.set_xlim(0, GENS); ax.set_ylim(-1, 3.5)
    ax.set_title("B · Lineage genealogy (N=24), coloured by trait")
    ax.set_xlabel("generation"); ax.set_ylabel("trait value")
    ax.legend(fontsize=8, loc="upper left")
    fig.colorbar(lc, ax=ax, label="trait", fraction=0.046, pad=0.04)

    # C — replicate means with intervals
    ax = axes[0, 2]
    g = np.arange(GENS)
    lo, hi = np.percentile(m_sel, [5, 95], axis=0)
    ax.fill_between(g, lo, hi, color=C_SEL, alpha=0.2, label="90% of seeds")
    ax.plot(g, m_sel.mean(0), color=C_SEL, lw=2, label="mean trait (40 seeds)")
    ax.plot(g, opt, color=C_OPT, lw=1.8, ls="--", label="optimum")
    ax.set_title("C · Replicate means track the optimum (lag = R=h²S balance)")
    ax.set_xlabel("generation"); ax.set_ylabel("trait value")
    ax.legend(fontsize=8, loc="upper left")

    # D — selection vs neutral lag
    ax = axes[1, 0]
    for lag, c, lab in [(lag_sel, C_SEL, "selection"), (lag_neu, C_NEU, "neutral (drift)")]:
        lo, hi = np.percentile(lag, [5, 95], axis=0)
        ax.fill_between(g, lo, hi, color=c, alpha=0.18)
        ax.plot(g, lag.mean(0), color=c, lw=2, label=lab)
    ax.set_title("D · Selection tracks; neutral drift wanders (40 seeds)")
    ax.set_xlabel("generation"); ax.set_ylabel("lag  |mean − optimum|")
    ax.legend(fontsize=8, loc="upper left")

    # E — adaptation-failure sweep
    ax = axes[1, 1]
    means = [f.mean() for f in fail]; stds = [f.std() for f in fail]
    ax.errorbar(drifts, means, yerr=stds, marker="o", color=C_FAIL, capsize=3, lw=1.8)
    ax.set_title("E · Adaptation failure: lag runs away with drift rate")
    ax.set_xlabel("optimum drift rate (per generation)"); ax.set_ylabel("final lag (20 seeds)")
    ax.annotate("population\ncan't keep up", (drifts[-1], means[-1]), fontsize=8,
                color=C_FAIL, ha="right", va="top")

    # F — uptake executable-trait mode
    ax = axes[1, 2]
    gg = np.arange(50)
    lo, hi = np.percentile(m_up, [5, 95], axis=0)
    ax.fill_between(gg, lo, hi, color="#4b5bd6", alpha=0.2, label="90% of seeds")
    ax.plot(gg, m_up.mean(0), color="#4b5bd6", lw=2, label="evolved mean trait")
    ax.plot(gg, opt_up, color=C_OPT, lw=1.8, ls="--", label="metabolic optimum a*")
    ax.set_title("F · Executable-trait fitness: tracks derived optimum a*")
    ax.set_xlabel("generation"); ax.set_ylabel("uptake-investment trait a")
    ax.legend(fontsize=8, loc="upper left")

    for ax in axes.flat:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(True, alpha=0.2, lw=0.5)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    print(f"  selection lag {lag_sel[:,-1].mean():.3f} vs neutral {lag_neu[:,-1].mean():.3f}; "
          f"failure sweep final lag {means[0]:.2f}→{means[-1]:.2f}; heritability≈1")


if __name__ == "__main__":
    main()
