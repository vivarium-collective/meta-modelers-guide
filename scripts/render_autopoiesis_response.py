#!/usr/bin/env python
"""The *autopoiesis* study's "response of the contract" figure.

The paper's Fig 8 / Self-organized-processes draft process states the autopoiesis
criterion as a *boundary problem*: a membrane is alive not because it exists but
because the processes inside it maintain the very organization that keeps those
processes possible. That draft compiles to a family of reaction-diffusion
executables on a 64x64 lattice, and this figure exercises the RELATION the
contract demands off the REAL running compiled composites -- never a re-plot of
the baked movie.

The demanded relation and its load-bearing controls, all measured here:

  * ``protocell-autopoietic`` (baseline) -- production GATED on the boundary
    staying topologically closed, self-limited by enclosed area. The closed loop
    MAINTAINS ITSELF: enclosed_area settles to a homeostatic plateau ~149 px
    (throttled down from the ~465 px seed, NOT runaway), persists == 1.0,
    collapse_tick == -1 across the full ~1800-step window.
  * ``protocell-vesicle-control`` (knockout, k_prod=0) -- the SINGLE-variable
    ablation. With no production loop the ring is a mere vesicle: it loses
    topological closure at internal step ~96, enclosed_area -> 0, persists -> 0.0.
    Flipping one rate constant flips self-maintenance into dissipation.
  * ``protocell-autopoietic-v2`` (local-mechanism closure, NO global observer) --
    closure-dependence EMERGES from geometry; sustains closure to 293 px at 1000
    steps (persists == 1.0), interior precursor pooled ~349.
  * ``protocell-autopoietic-v2-open`` (externally driven) -- a local open drive
    does NOT rescue steady self-maintenance: it DESTABILISES the ring into runaway
    autocatalytic filling (membrane mass 575 -> ~2400+, closure lost ~step 592).

Every trajectory below is read straight from the emitter of the running compiled
composite (the executable's OWN observables enclosed_area / membrane_mass /
persists / collapse_tick / precursor_mass). steps_per_tick is lowered only to
sample the SAME deterministic trajectory more finely -- the physics is byte-for-
byte identical (the process reads phi from the store, advances N internal RD
steps, emits the delta; the trajectory at a given internal step is invariant to
how often it is snapshotted).

Outputs into the study's visualizations/:
  autopoiesis-response.svg / .png
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib import gridspec
from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.protocell.autopoiesis import enclosed_area

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "meta_modelers_guide" / "composites"
VIZ = ROOT / "workspace" / "studies" / "autopoiesis" / "visualizations"

# Book palette -- the guide's teal family + a warm accent + a collapse red.
INK, TEAL, TEAL_L, WARM, WARM_L, GRID = (
    "#16211f", "#0d6e6b", "#3f9e99", "#a5620f", "#c98a3a", "#c9d3d1")
RED = "#9e2b1f"
# White -> teal membrane colormap for the phi snapshots.
MEMBRANE_CMAP = LinearSegmentedColormap.from_list(
    "membrane", ["#f7faf9", "#bcd8d5", TEAL_L, TEAL, INK])


def _load(stem):
    return json.loads((COMPOSITES / f"{stem}.composite.json").read_text())["state"]


def _run(stem, steps_per_tick, ticks, overrides=None):
    """Run a compiled protocell composite, sampling every ``steps_per_tick``
    internal RD steps for ``ticks`` snapshots, and return the emitter series
    (internal-step axis + the executable's own observables + the phi field).

    ``steps_per_tick`` sets ONLY the emit cadence: the RD trajectory at a given
    internal step is deterministic and independent of it. ``overrides`` patches
    the protocell process config (e.g. a knockout rate)."""
    st = _load(stem)
    st["protocell"]["config"]["steps_per_tick"] = int(steps_per_tick)
    for k, v in (overrides or {}).items():
        st["protocell"]["config"][k] = v

    # Ensure a RAMEmitter reading phi (+ p if present) and every obs the process
    # exposes; v2-open ships without a baked emitter, the others reuse theirs.
    has_p = "p" in st["fields"]
    outs = st["protocell"]["outputs"]
    emit = {"phi": "array"}
    inputs = {"phi": ["fields", "phi"]}
    if has_p:
        emit["p"] = "array"
        inputs["p"] = ["fields", "p"]
    for name in outs:
        if name == "fields":
            continue
        emit[name] = "float"
        inputs[name] = ["obs", name]
    emit["time"] = "float"
    inputs["time"] = ["global_time"]
    st["emitter"] = {"_type": "step", "address": "local:RAMEmitter",
                     "config": {"emit": emit}, "inputs": inputs}

    sim = Composite({"state": st}, core=build_core())
    sim.run(int(ticks))
    rows = gather_emitter_results(sim)[("emitter",)]
    # Drop the engine's t=0 pre-run emit (obs stores still at their 0 defaults).
    rows = [r for r in rows if float(r.get("time", 0)) > 0]

    def col(k):
        return np.array([float(r[k]) for r in rows]) if rows and k in rows[0] else None

    out = {
        "step": np.array([float(r["time"]) for r in rows]) * steps_per_tick,
        "enclosed_area": col("enclosed_area"),
        "membrane_mass": col("membrane_mass"),
        "persists": col("persists"),
        "collapse_tick": col("collapse_tick"),
        "precursor_mass": col("precursor_mass"),
        "phi_final": np.asarray(rows[-1]["phi"], dtype=float),
    }
    return out


def _clean(a):
    for sp in ("top", "right"):
        a.spines[sp].set_visible(False)
    a.grid(True, color=GRID, alpha=0.5, lw=0.6)


def _snapshot(ax, phi, title, edge, thr=0.30):
    """Membrane-density heatmap with the thr=0.30 closure contour."""
    im = ax.imshow(phi, cmap=MEMBRANE_CMAP, vmin=0.0, vmax=1.0,
                   interpolation="bilinear", origin="lower")
    ax.contour(phi, levels=[thr], colors=[edge], linewidths=1.4)
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_edgecolor(edge); sp.set_linewidth(1.6)
    ax.set_title(title, color=INK, fontsize=9.5)
    return im


def render():
    VIZ.mkdir(parents=True, exist_ok=True)
    head = {}

    # ── measure the seed the whole study rides on ──────────────────────────────
    seed = np.asarray(_load("protocell-autopoietic")["fields"]["phi"], dtype=float)
    seed_area = int(enclosed_area(seed).sum())
    seed_mass = float(seed.sum())
    head["seed_enclosed_area"] = seed_area
    head["seed_mass"] = round(seed_mass, 1)

    # ── run the compiled arms ──────────────────────────────────────────────────
    base = _run("protocell-autopoietic", 50, 36)          # canonical 1800 steps
    base_fine = _run("protocell-autopoietic", 25, 14)      # finer 0-350 window
    ctrl = _run("protocell-vesicle-control", 4, 60)        # fine cliff at ~96
    v2 = _run("protocell-autopoietic-v2", 50, 20)          # 1000 steps, sustains
    vopen = _run("protocell-autopoietic-v2-open", 50, 20)  # 1000 steps, runaway

    head["baseline_plateau_area"] = int(base["enclosed_area"][-1])
    head["baseline_persists"] = float(base["persists"][-1])
    head["baseline_collapse_tick"] = float(base["collapse_tick"][-1])
    head["baseline_mass_final"] = round(float(base["membrane_mass"][-1]), 1)
    head["knockout_collapse_step"] = float(ctrl["collapse_tick"][-1])
    head["knockout_persists"] = float(ctrl["persists"][-1])
    head["v2_area_1000"] = int(v2["enclosed_area"][-1])
    head["v2_persists"] = float(v2["persists"][-1])
    head["v2_precursor_pooled"] = round(float(v2["precursor_mass"][-1]), 1)
    head["open_collapse_step"] = float(vopen["collapse_tick"][-1])
    head["open_mass_final"] = round(float(vopen["membrane_mass"][-1]), 1)
    head["open_mass_seed"] = round(float(vopen["membrane_mass"][0]), 1)

    plt.rcParams.update({"font.size": 9, "axes.edgecolor": "#3a4744",
                         "axes.labelcolor": INK, "text.color": INK,
                         "xtick.color": INK, "ytick.color": INK})
    fig = plt.figure(figsize=(13.4, 8.4), dpi=120)
    gs = gridspec.GridSpec(2, 3, figure=fig, height_ratios=[1.1, 0.95],
                           top=0.905, bottom=0.055, left=0.055, right=0.895,
                           hspace=0.48, wspace=0.34)

    # (A) the demanded self-maintenance vs its single-variable ablation ─────────
    a = fig.add_subplot(gs[0, 0])
    m = base_fine["step"] <= 350
    a.plot(np.concatenate([[0], base_fine["step"][m]]),
           np.concatenate([[seed_area], base_fine["enclosed_area"][m]]),
           color=TEAL, lw=2.6, marker="o", ms=3.2,
           label="autopoietic (persists = 1)")
    mc = ctrl["step"] <= 200
    a.plot(np.concatenate([[0], ctrl["step"][mc]]),
           np.concatenate([[seed_area], ctrl["enclosed_area"][mc]]),
           color=RED, lw=2.4, ls="--", label="k$_{prod}$=0 knockout (persists = 0)")
    a.axhline(0, color="#7a8582", lw=0.8, ls=":")
    a.axvline(96, color=RED, lw=1.0, ls=":")
    a.annotate("closure lost\nstep 96  ->  area 0", (96, 250), (150, 355),
               fontsize=8.2, color=RED,
               arrowprops=dict(arrowstyle="->", color=RED, lw=1.0))
    a.annotate("membrane maintains\nits enclosed interior", (250, 145), (150, 60),
               fontsize=8.2, color=TEAL)
    a.set_title("The contract vs its ablation\n(enclosed interior, early window)",
                color=INK, fontsize=10)
    a.set_xlabel("internal RD step"); a.set_ylabel("enclosed area (px)")
    a.set_xlim(0, 350); a.set_ylim(-20, 720)
    a.legend(frameon=False, fontsize=8, loc="upper right")
    _clean(a)

    # (B) homeostasis — 465 px seed settles to a bounded ~149 px plateau ────────
    a = fig.add_subplot(gs[0, 1])
    a.plot(np.concatenate([[0], base["step"]]),
           np.concatenate([[seed_area], base["enclosed_area"]]),
           color=TEAL, lw=2.6, marker="o", ms=2.6, label="enclosed area")
    a.axhline(head["baseline_plateau_area"], ls=":", color=WARM, lw=1.2)
    a.scatter([0], [seed_area], color=INK, zorder=5, s=22)
    a.annotate(f"seed {seed_area} px", (0, seed_area), (110, 560),
               fontsize=8.3, color="#3a4744",
               arrowprops=dict(arrowstyle="->", color="#3a4744", lw=0.9))
    a.annotate(f"homeostatic plateau ~{head['baseline_plateau_area']} px\n"
               f"(persists = 1, collapse_tick = -1)",
               (1250, head["baseline_plateau_area"]),
               (560, 300), fontsize=8.3, color=WARM,
               arrowprops=dict(arrowstyle="->", color=WARM, lw=0.9))
    a.set_title("Homeostasis, not runaway growth\n"
                "(production self-throttled by enclosed area)",
                color=INK, fontsize=10)
    a.set_xlabel("internal RD step"); a.set_ylabel("enclosed area (px)")
    a.set_xlim(0, 1800); a.set_ylim(0, 560)
    _clean(a)

    # (C) an external drive destabilises rather than sustains ───────────────────
    a = fig.add_subplot(gs[0, 2])
    a.plot(np.concatenate([[0], v2["step"]]),
           np.concatenate([[seed_area], v2["enclosed_area"]]),
           color=TEAL, lw=2.6, label="v2 undriven (persists = 1)")
    a.plot(np.concatenate([[0], vopen["step"]]),
           np.concatenate([[seed_area], vopen["enclosed_area"]]),
           color=WARM, lw=2.4, ls="--", label="v2 open-driven (persists = 0)")
    a.axvline(head["open_collapse_step"], color=WARM, lw=1.0, ls=":")
    a.annotate(f"closure lost\nstep ~{int(head['open_collapse_step'])}\n"
               f"(runaway fill:\nmass {int(head['open_mass_seed'])} -> "
               f"{int(head['open_mass_final'])}+)",
               (head["open_collapse_step"], 60), (640, 240),
               fontsize=7.8, color=WARM,
               arrowprops=dict(arrowstyle="->", color=WARM, lw=1.0))
    a.set_title("External drive DESTABILISES\n(open-system EMERGE step)",
                color=INK, fontsize=10)
    a.set_xlabel("internal RD step"); a.set_ylabel("enclosed area (px)")
    a.set_xlim(0, 1000); a.set_ylim(-20, 540)
    a.legend(frameon=False, fontsize=7.8, loc="upper right")
    _clean(a)

    # ── bottom row: the membrane state itself, read off the same runs ──────────
    im = _snapshot(fig.add_subplot(gs[1, 0]), base["phi_final"],
                   f"intact closed ring\n(baseline, {head['baseline_plateau_area']} px enclosed, "
                   f"persists)", TEAL)
    _snapshot(fig.add_subplot(gs[1, 1]), ctrl["phi_final"],
              "collapsed vesicle\n(k$_{prod}$=0 knockout, 0 px enclosed)", RED)
    _snapshot(fig.add_subplot(gs[1, 2]), vopen["phi_final"],
              "runaway-filled domain\n(open-driven, 0 px enclosed)", WARM)

    cax = fig.add_axes([0.905, 0.09, 0.011, 0.28])
    cb = fig.colorbar(im, cax=cax)
    cb.set_label("membrane density $\\varphi$", fontsize=8)
    cb.ax.tick_params(labelsize=7)

    fig.suptitle("Autopoiesis, exercised — a boundary that maintains itself, and the ablations that break it",
                 fontsize=13.5, color=INK, y=0.972, weight="bold")
    fig.text(0.475, 0.474,
             "Top row: each running executable's OWN observables over internal RD steps.   "
             "Bottom row: the final membrane field $\\varphi$ with the closure contour ($\\varphi$ = 0.30).",
             ha="center", fontsize=8.4, color="#3a4744")
    fig.savefig(VIZ / "autopoiesis-response.svg", format="svg")
    fig.savefig(VIZ / "autopoiesis-response.png", format="png")
    plt.close(fig)
    return head


if __name__ == "__main__":
    h = render()
    print(json.dumps(h, indent=2))
    print("\nwrote", VIZ / "autopoiesis-response.svg")
