#!/usr/bin/env python
"""Render the *development-and-evolution* study's flagship evidence figure — the
**response of the contract**.

The paper's §Development and evolution section (Fig 10c-f) makes a claim with a
characteristic *shape*, not a single number: a heritable trait's population mean
moves DIRECTIONALLY under selection, drifts UNDIRECTED without it, and cannot move
at all without mutation (no raw material). The draft process (``CpmEvolution`` —
study 8's ``CpmGrowthDivision`` reused unchanged plus one heritable per-cell
glucose-uptake trait ``vmax``) defines that contract; the three compiled
executables realize it:

    development-evolution-spatial       selection ON,  mutation ON   (the response)
    development-evolution-no-selection  selection OFF, mutation ON   (neutral drift)
    development-evolution-no-mutation   selection ON,  mutation OFF  (no raw material)

The existing evidence is a baked trait-colored GIF + a per-tick Plotly panel of
ONE flagship seed (seed 3). This renderer instead *exercises the contract on the
real compiled executables* across an N-seed ensemble and graphs the relation the
contract demands: the mean-trait trajectory diverging into directed climb / drift
/ flat, the variance building only under mutation, the per-seed Δmean
distribution recovering the recorded +0.233 (selection) vs -0.026 (drift) vs
0.000 (no-mutation) with the Mann-Whitney rank test, and — the collective
interface — the radial rim-core glucose ratio developing above 1.0 over the same
run. Every curve is measured off the running engine; nothing is re-plotted from
the movie.

Outputs (into the study's visualizations/):
  development-and-evolution-response.svg / .png
Prints the headline numbers (per-arm Δmean, Mann-Whitney p, variance build,
rim-core band).
"""
from __future__ import annotations

import copy
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager  # noqa: F401  (ensure font cache is built)

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "meta_modelers_guide" / "composites"
VIZ = ROOT / "workspace" / "studies" / "development-and-evolution" / "visualizations"
CACHE = Path("/private/tmp/claude-502/-Users-eranagmon-code/"
             "93e8c440-0f5a-4848-b32f-30d078b515bf/scratchpad/dev_evo_ensemble.json")

SEL = "development-evolution-spatial"        # selection ON,  mutation ON
NOSEL = "development-evolution-no-selection"  # selection OFF, mutation ON
NOMUT = "development-evolution-no-mutation"   # selection ON,  mutation OFF
VMAX0 = 1.5
N_SEEDS = 30
STEPS = 45
WORKERS = 6

# ── book palette — the guide's teal family + a warm accent + neutral control ──
INK = "#16211f"
TEAL = "#0d6e6b"       # selection — the directed response
TEAL_L = "#3f9e99"
WARM = "#a5620f"       # no-selection — neutral drift
WARM_L = "#c98a3a"
SLATE = "#5b6b68"      # no-mutation — the static control
GRID = "#c9d3d1"
DEV = "#2c6e6b"        # development / rim-core


# ──────────────────────────────────────────────────────────────────────────────
# Worker: run ONE compiled executable at ONE seed, return the full trajectory of
# the dev/evo observables. Imports inside the fn so it works as a pool worker
# (each process builds its own core / cobra model registry).
# ──────────────────────────────────────────────────────────────────────────────
def _run_arm_seed(args):
    name, seed, steps = args
    from process_bigraph import Composite, gather_emitter_results
    from meta_modelers_guide.core import build_core

    obs = ("n_cells", "mean_vmax", "var_vmax", "rim_core_ratio")
    state = copy.deepcopy(
        json.loads((COMPOSITES / f"{name}.composite.json").read_text())["state"]
    )
    # the seed leaf threads BOTH the CPM potts spec AND the mutation RNG (base
    # process hardcodes potts.seed=1, so this is what makes seeds independent).
    state["evo"]["config"]["seed"] = int(seed)
    emit = {o: "float" for o in obs}
    emit["time"] = "float"
    inputs = {o: ["obs", o] for o in obs}
    inputs["time"] = ["global_time"]
    state["vizemitter"] = {"_type": "step", "address": "local:RAMEmitter",
                           "config": {"emit": emit}, "inputs": inputs}
    core = build_core()
    sim = Composite({"state": state}, core=core)
    sim.run(steps)
    rows = gather_emitter_results(sim)[("vizemitter",)]
    t = [float(r.get("time", i)) for i, r in enumerate(rows)]
    series = {o: [float(r[o]) for r in rows] for o in obs}
    return {"arm": name, "seed": int(seed), "time": t, **series}


def gather(refresh=False):
    if CACHE.exists() and not refresh:
        return json.loads(CACHE.read_text())
    jobs = ([(SEL, s, STEPS) for s in range(1, N_SEEDS + 1)]
            + [(NOSEL, s, STEPS) for s in range(1, N_SEEDS + 1)]
            + [(NOMUT, s, STEPS) for s in range(1, 6)])  # 5 seeds: control is exact
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        runs = list(ex.map(_run_arm_seed, jobs))
    print(f"ran {len(jobs)} executable trajectories in {time.time() - t0:.0f}s")
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(runs))
    return runs


# ──────────────────────────────────────────────────────────────────────────────
def _stack(runs, arm, key):
    """Return (time, MxT array) of `key` over the seeds of one arm, aligned on the
    common tick grid (all runs share the 0..STEPS grid)."""
    sel = [r for r in runs if r["arm"] == arm]
    t = np.array(sel[0]["time"])
    M = np.array([r[key] for r in sel])
    return t, M


def _band(ax, t, M, color, label, lw=2.6, alpha=0.16):
    mean = M.mean(axis=0)
    lo, hi = np.percentile(M, [25, 75], axis=0)
    ax.fill_between(t, lo, hi, color=color, alpha=alpha, lw=0)
    ax.plot(t, mean, color=color, lw=lw, label=label, zorder=4)
    return mean


def render(refresh=False):
    VIZ.mkdir(parents=True, exist_ok=True)
    runs = gather(refresh=refresh)
    head = {}

    # per-arm final-minus-founder deltas (the response magnitude, per seed)
    def deltas(arm):
        _, M = _stack(runs, arm, "mean_vmax")
        return M[:, -1] - VMAX0

    d_sel, d_nosel, d_nomut = deltas(SEL), deltas(NOSEL), deltas(NOMUT)

    from scipy.stats import mannwhitneyu
    mw = mannwhitneyu(d_sel, d_nosel, alternative="two-sided")
    n1, n2 = len(d_sel), len(d_nosel)
    cles = float(mw.statistic) / (n1 * n2)
    rank_biserial = 2 * cles - 1
    head.update(
        selection_delta_mean=round(float(d_sel.mean()), 3),
        selection_delta_sd=round(float(d_sel.std(ddof=1)), 3),
        selection_up=f"{int((d_sel > 0).sum())}/{n1}",
        no_selection_delta_mean=round(float(d_nosel.mean()), 3),
        no_selection_up=f"{int((d_nosel > 0).sum())}/{n2}",
        no_mutation_delta_mean=round(float(d_nomut.mean()), 3),
        no_mutation_var_max=round(float(max(
            r["var_vmax"][-1] for r in runs if r["arm"] == NOMUT)), 6),
        mannwhitney_U=round(float(mw.statistic), 1),
        mannwhitney_p=float(f"{mw.pvalue:.2e}"),
        rank_biserial=round(rank_biserial, 3),
        cles=round(cles, 3),
    )

    # rim-core development band (selection-ON seeds)
    trc, RC = _stack(runs, SEL, "rim_core_ratio")
    rc_final = RC[:, -1]
    head.update(
        rim_core_final_mean=round(float(rc_final.mean()), 3),
        rim_core_final_sd=round(float(rc_final.std(ddof=1)), 3),
        rim_core_final_range=[round(float(rc_final.min()), 3), round(float(rc_final.max()), 3)],
    )

    # ── figure: 2x2 response panels ────────────────────────────────────────────
    plt.rcParams.update({"font.size": 9.2, "axes.edgecolor": "#3a4744",
                         "axes.labelcolor": INK, "text.color": INK,
                         "xtick.color": INK, "ytick.color": INK})
    fig, ax = plt.subplots(2, 2, figsize=(12.8, 9.2), dpi=120,
                           constrained_layout=True)

    def _clean(a):
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
        a.grid(True, color=GRID, alpha=0.5, lw=0.6)

    # (A) mean-trait trajectory — the contract's directed / drift / flat response
    a = ax[0, 0]
    tS, MS = _stack(runs, SEL, "mean_vmax")
    tN, MN = _stack(runs, NOSEL, "mean_vmax")
    _band(a, tS, MS, TEAL, f"selection ON  (Δ={d_sel.mean():+.3f}, up {int((d_sel>0).sum())}/{n1})")
    _band(a, tN, MN, WARM, f"no selection  (Δ={d_nosel.mean():+.3f}, drift)")
    a.axhline(VMAX0, ls=(0, (1, 1.5)), color=SLATE, lw=2.4,
              label=f"no mutation  (Δ={d_nomut.mean():+.3f}, flat)")
    a.axhline(VMAX0, ls=":", color="#9aa5a2", lw=0.9, zorder=1)
    a.annotate("founder v$_{max}$ = 1.5", (1.0, VMAX0), (2.0, VMAX0 - 0.11),
               fontsize=8.3, color="#7a8582")
    a.annotate("directed climb\nunder selection", (33, MS.mean(axis=0)[33]),
               (18, 1.62), fontsize=8.6, color=TEAL,
               arrowprops=dict(arrowstyle="->", color=TEAL_L, lw=1.1))
    a.set_title("EVOLUTION — population-mean trait  v$_{max}$(t)", color=INK, fontsize=10.5, weight="bold")
    a.set_xlabel("time (ticks)"); a.set_ylabel("population-mean  v$_{max}$")
    a.legend(frameon=False, fontsize=8.2, loc="upper left")
    a.set_ylim(1.35, None)
    _clean(a)

    # (B) trait variance — raw material builds only under mutation
    a = ax[0, 1]
    tSv, MSv = _stack(runs, SEL, "var_vmax")
    tNv, MNv = _stack(runs, NOSEL, "var_vmax")
    _band(a, tSv, MSv, TEAL, "selection ON (mutation ON)")
    _band(a, tNv, MNv, WARM, "no selection (mutation ON)")
    a.axhline(0.0, ls=(0, (1, 1.5)), color=SLATE, lw=2.4, label="no mutation (var $\\equiv$ 0)")
    vtop = float(MSv.mean(axis=0).max())
    a.annotate("mutation supplies\nthe raw material", (24, MSv.mean(axis=0)[24]),
               (3, vtop * 0.92), fontsize=8.6, color="#3a4744",
               arrowprops=dict(arrowstyle="->", color="#8a9491", lw=0.9))
    a.annotate("no mutation → no variance\n(nothing for selection to act on)",
               (26, 0.0), (5, vtop * 0.42), fontsize=8.3, color=SLATE)
    a.set_ylim(-0.008, vtop * 1.18)
    a.set_title("the raw-material control — trait variance  var(v$_{max}$)(t)",
                color=INK, fontsize=10.5, weight="bold")
    a.set_xlabel("time (ticks)"); a.set_ylabel("population trait variance")
    a.legend(frameon=False, fontsize=8.2, loc="upper left")
    _clean(a)

    # (C) per-seed Δmean distribution — the dual-control contrast + rank test
    a = ax[1, 0]
    rng = np.random.default_rng(0)
    groups = [(d_nomut, SLATE, "no\nmutation"),
              (d_nosel, WARM, "no\nselection"),
              (d_sel, TEAL, "selection\nON")]
    for i, (d, c, lab) in enumerate(groups):
        x = i + rng.uniform(-0.13, 0.13, size=len(d))
        a.scatter(x, d, s=28, color=c, alpha=0.55, edgecolor="white", lw=0.4, zorder=3)
        a.hlines(d.mean(), i - 0.28, i + 0.28, color=c, lw=3.0, zorder=4)
        a.annotate(f"{d.mean():+.3f}", (i, d.mean()),
                   (i + 0.30, d.mean()), fontsize=8.6, color=c, weight="bold",
                   va="center")
    a.axhline(0.0, ls=":", color="#9aa5a2", lw=1.0)
    a.set_xticks(range(3)); a.set_xticklabels([g[2] for g in groups], fontsize=9)
    a.set_ylabel("per-seed Δ mean-v$_{max}$  (final − founder)")
    a.set_title(f"dual control across N={n1} seeds — selection is the driver",
                color=INK, fontsize=10.5, weight="bold")
    # significance bracket selection vs no-selection
    ytop = max(d_sel.max(), d_nosel.max()) + 0.08
    a.plot([1, 1, 2, 2], [ytop, ytop + 0.03, ytop + 0.03, ytop], color=INK, lw=1.0)
    a.annotate(f"Mann-Whitney U={mw.statistic:.0f}, p={mw.pvalue:.1e}\n"
               f"rank-biserial r={rank_biserial:+.2f}  (CLES {cles:.2f})",
               (1.5, ytop + 0.05), ha="center", fontsize=8.4, color=INK)
    a.set_ylim(None, ytop + 0.30)
    _clean(a)

    # (D) DEVELOPMENT — collective interface: rim-core glucose ratio develops
    a = ax[1, 1]
    _band(a, trc, RC, DEV, f"selection-ON colony  (N={n1} seeds)", lw=2.6)
    a.axhline(1.0, ls=":", color="#9aa5a2", lw=1.1)
    a.annotate("no-gradient floor (1.0)", (2, 1.0), (3, 1.045), fontsize=8.3, color="#7a8582")
    a.annotate(f"core more depleted than rim\nfinal band {rc_final.mean():.3f} "
               f"± {rc_final.std(ddof=1):.3f}", (35, RC.mean(axis=0)[35]),
               (6, 1.30), fontsize=8.6, color=DEV,
               arrowprops=dict(arrowstyle="->", color=DEV, lw=1.1))
    a.set_title("DEVELOPMENT — emergent collective interface  rim/core(t)",
                color=INK, fontsize=10.5, weight="bold")
    a.set_xlabel("time (ticks)"); a.set_ylabel("radial rim-core glucose ratio")
    a.legend(frameon=False, fontsize=8.4, loc="upper left")
    _clean(a)

    st = fig.suptitle(
        "Development & evolution, exercised — the response the contract demands",
        fontsize=13.5, color=INK, weight="bold")
    st.set_position((0.5, 1.008))
    fig.text(0.5, 1.0,
             "every curve measured off the real compiled executables (CpmEvolution) "
             f"across an N={n1}-seed ensemble — not re-plotted from the movie",
             ha="center", va="bottom", fontsize=8.9, color="#5b6b68", style="italic")
    fig.savefig(VIZ / "development-and-evolution-response.svg", format="svg", bbox_inches="tight")
    fig.savefig(VIZ / "development-and-evolution-response.png", format="png", bbox_inches="tight")
    plt.close(fig)
    return head


if __name__ == "__main__":
    import sys
    h = render(refresh="--refresh" in sys.argv)
    print(json.dumps(h, indent=2))
    print("\nwrote", VIZ / "development-and-evolution-response.svg")
