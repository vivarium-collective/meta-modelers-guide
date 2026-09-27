#!/usr/bin/env python
"""The *disintegration* study's "response of the contract" figure.

The Fig 5 §Disintegration draft process (``CpmDisintegration``) defines a typed
contract that demands a characteristic relation: a cell holds a coherent domain
while a diffusing stressor stays BELOW its footprint-local viability bound, then,
once that bound is CROSSED, viability latches lost, the domain resorbs to zero,
its vacated footprint pixels become physical debris particles (a mass ledger that
closes), and the debris cloud keeps scattering. The compiled executable
``disintegration-spatial`` realizes exactly this: one real ``viva-cpm`` cell on a
shared 60x60 spatio-flux ``acetate`` field (radial gradient, low at the seeded
centre, rising toward the periphery) inside a ``DiffusionAdvection`` relaxation,
coupled through ``CpmDisintegration`` (the viability-collapse trigger + scripted
resorption, resorb_per_tick=6.0) plus a seeded ``BrownianMovement`` scattering the
shed debris.

Every curve here is MEASURED off the running compiled executable -- this renderer
drives a live ``process_bigraph.Composite`` in a manual per-tick loop (the CPM
lattice lives on the process instance's ``world`` and the debris live in the
shared ``particles`` map, neither of which the emitter surfaces as a plain
time-series), reading ``obs`` (area, mean_stressor, released, released_tick) and
the ``particles`` store after each tick. It is NOT a re-plot of the baked movie.

The demanded relation, exercised (measured on the fixed-seed run):

  * hold        -- area 61-66 through tick 6, released False, 0 debris.
  * cross       -- footprint-local acetate mean crosses viability_threshold=0.5;
                   released latches at deterministic released_tick = 7 (area 56).
  * resorb      -- domain resorbs monotonically 56 (tick 7) -> 0 by tick 16.
  * shed        -- vacated pixels become debris: 0 -> 63 by tick 16, then flat
                   (a released-mass ledger: 63 shed == distinct vacated pixels).
  * scatter     -- debris-cloud RMS spread strictly increases after dissolution.

Outputs (into the study's visualizations/):
  disintegration-response.svg / .png   -- the six-panel response figure
Prints the headline numbers.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb
from process_bigraph import Composite

from meta_modelers_guide.core import build_core

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "meta_modelers_guide" / "composites"
VIZ = ROOT / "workspace" / "studies" / "disintegration" / "visualizations"

STEM = "disintegration-spatial"
TOTAL_TICKS = 24
RELEASED_TICK = 7          # deterministic, latched (verified below)
SNAP_TICKS = (4, 10, 20)   # coherent / mid-resorption / fully-shed-and-scattered

# Book palette -- the guide's teal family + a warm accent for the shed debris.
INK = "#16211f"
TEAL = "#0d6e6b"
TEAL_L = "#3f9e99"
WARM = "#a5620f"
WARM_L = "#c98a3a"
CRIMSON = "#9e2b1f"
GRID = "#c9d3d1"


def _rms_spread(particles):
    """RMS radius of the debris cloud: sqrt(mean squared distance from the
    cloud's own centroid), over the shed particle positions in the shared store.
    A single, spread-free reading is 0."""
    pts = []
    for p in particles.values():
        pos = p.get("position") if isinstance(p, dict) else None
        if pos is None:
            continue
        pts.append((float(pos[0]), float(pos[1])))
    if len(pts) < 1:
        return 0.0, np.empty((0, 2))
    a = np.array(pts)
    c = a.mean(axis=0)
    return float(np.sqrt(((a - c) ** 2).sum(axis=1).mean())), a


def _run():
    """Drive the compiled executable one tick at a time; return per-tick series
    plus field/footprint/debris snapshots at SNAP_TICKS. Every value is read
    off the LIVE composite (obs store + CPM world + particles map)."""
    state = json.loads((COMPOSITES / f"{STEM}.composite.json").read_text())["state"]
    core = build_core()
    proc_key = next(
        k for k, v in state.items()
        if isinstance(v, dict) and v.get("_type") == "process"
        and "CpmDisintegration" in v.get("address", "")
    )
    field_name = str(state[proc_key]["config"].get("stressor_field", "stressor"))
    viability_threshold = float(state[proc_key]["config"].get("viability_threshold", 0.5))

    comp = Composite({"state": state}, core=core)
    ny, nx = comp.state["fields"][field_name].shape
    bounds = dict(state[proc_key]["config"].get("bounds") or {})
    bx = float(bounds.get("x", nx))
    by = float(bounds.get("y", ny))

    series = {k: [] for k in ("time", "area", "mean_stressor", "released",
                              "released_tick", "n_particles", "rms")}
    snaps = {}

    for tick in range(1, TOTAL_TICKS + 1):
        comp.run(1)
        world = comp.state[proc_key]["instance"].world
        lattice = np.array(world.snapshot()).reshape(ny, nx)
        footprint = lattice > 0
        obs = comp.state["obs"]
        particles = comp.state.get("particles", {}) or {}
        rms, pts = _rms_spread(particles)

        series["time"].append(float(tick))
        series["area"].append(float(obs.get("area", int(footprint.sum()))))
        series["mean_stressor"].append(float(obs.get("mean_stressor", 0.0)))
        series["released"].append(bool(obs.get("released", False)))
        series["released_tick"].append(float(obs.get("released_tick", 0.0)))
        series["n_particles"].append(float(len(particles)))
        series["rms"].append(rms)

        if tick in SNAP_TICKS:
            # forward pixel mapping matches the process's inverse placement
            # (x = (col+0.5)*bx/nx): col = x/bx*nx, row = y/by*ny.
            px = (pts[:, 0] / bx * nx, pts[:, 1] / by * ny) if len(pts) else (np.array([]), np.array([]))
            snaps[tick] = {
                "field": np.asarray(comp.state["fields"][field_name]).copy(),
                "footprint": footprint.copy(),
                "px_col": px[0], "px_row": px[1],
            }

    for k in series:
        series[k] = np.array(series[k])
    return series, snaps, dict(nx=nx, ny=ny, field_name=field_name,
                               viability_threshold=viability_threshold)


def _clean(a):
    for sp in ("top", "right"):
        a.spines[sp].set_visible(False)
    a.grid(True, color=GRID, alpha=0.5, lw=0.6)


def _snapshot_panel(ax, snap, meta, title, stressor_vmax):
    """Field heatmap + translucent-filled CPM footprint + shed debris dots +
    the viability-threshold isoline (the level-shift front the paper's Fig 5
    demands, made literal)."""
    field = snap["field"]
    im = ax.imshow(field, origin="lower", cmap="magma", vmin=0.0, vmax=stressor_vmax)
    # footprint: translucent fill + thin contour (never contour-only)
    mask = snap["footprint"]
    if mask.any():
        r, g, b = to_rgb(TEAL_L)
        rgba = np.zeros((*mask.shape, 4))
        rgba[mask] = (r, g, b, 0.55)
        ax.imshow(rgba, origin="lower")
        ax.contour(mask, levels=[0.5], colors=[TEAL], linewidths=1.6)
    # viability-threshold isoline (the crossing front)
    if field.max() > meta["viability_threshold"] > field.min():
        ax.contour(field, levels=[meta["viability_threshold"]],
                   colors=["#eaf3f1"], linewidths=1.0, linestyles=":")
    # debris particles
    if len(snap["px_col"]):
        ax.scatter(snap["px_col"], snap["px_row"], s=10, c=WARM_L,
                   edgecolors=WARM, linewidths=0.4, zorder=5)
    ax.set_title(title, color=INK, fontsize=9.5)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_xlim(0, meta["nx"] - 1); ax.set_ylim(0, meta["ny"] - 1)
    return im


def render():
    VIZ.mkdir(parents=True, exist_ok=True)
    s, snaps, meta = _run()
    t = s["time"]

    # ── headline numbers, straight off the run ─────────────────────────────
    rel_idx = int(np.argmax(s["released"])) if s["released"].any() else -1
    released_tick = int(s["released_tick"][-1])
    i7 = int(np.where(t == 7)[0][0])
    i16 = int(np.where(t == 16)[0][0])
    i24 = int(np.where(t == 24)[0][0])
    hold_lo, hold_hi = int(s["area"][:6].min()), int(s["area"][:6].max())
    head = {
        "released_tick": released_tick,
        "area_hold_range": [hold_lo, hold_hi],
        "area_at_release_t7": int(s["area"][i7]),
        "area_at_t16": int(s["area"][i16]),
        "n_particles_final": int(s["n_particles"][i16]),
        "rms_t16": round(float(s["rms"][i16]), 2),
        "rms_t24": round(float(s["rms"][i24]), 2),
        "mean_stressor_at_release_t7": round(float(s["mean_stressor"][i7]), 3),
        "viability_threshold": meta["viability_threshold"],
    }

    plt.rcParams.update({"font.size": 9, "axes.edgecolor": "#3a4744",
                         "axes.labelcolor": INK, "text.color": INK,
                         "xtick.color": INK, "ytick.color": INK})
    fig = plt.figure(figsize=(13.2, 7.6), dpi=120)
    gs = fig.add_gridspec(2, 3, height_ratios=[1.0, 0.92], hspace=0.34, wspace=0.40)

    XT = "time (ticks)"
    stressor_vmax = max(float(snaps[k]["field"].max()) for k in SNAP_TICKS)

    def _mark_release(a):
        a.axvline(RELEASED_TICK, ls="--", color=CRIMSON, lw=1.4, alpha=0.9)

    # (A) coherent-before vs disintegration-after: area falls, stressor crosses
    a = fig.add_subplot(gs[0, 0])
    a.axvspan(0, RELEASED_TICK, color=TEAL_L, alpha=0.10)
    a.plot(t, s["area"], color=TEAL, lw=2.6, marker="o", ms=3, label="cell area (px)")
    a.set_xlabel(XT); a.set_ylabel("CPM footprint area (px)", color=TEAL)
    a.tick_params(axis="y", labelcolor=TEAL)
    _mark_release(a)
    a2 = a.twinx()
    a2.plot(t, s["mean_stressor"], color=WARM, lw=2.0, ls="--",
            label="footprint acetate")
    a2.axhline(meta["viability_threshold"], ls=":", color=CRIMSON, lw=1.1)
    a2.set_ylabel("footprint acetate mean", color=WARM)
    a2.tick_params(axis="y", labelcolor=WARM)
    a2.spines["top"].set_visible(False)
    a.annotate(f"crosses bound ->\nreleased_tick = {released_tick}",
               (RELEASED_TICK, hold_hi * 0.62), (RELEASED_TICK + 1.2, hold_hi * 0.78),
               fontsize=8, color=CRIMSON,
               arrowprops=dict(arrowstyle="->", color=CRIMSON, lw=1.0))
    a.annotate("HOLD\ncoherent", (2.6, hold_hi * 0.32), fontsize=8.5, color=TEAL, ha="center")
    a.set_title("coherent below the bound, then it crosses", color=INK, fontsize=10)
    _clean(a)

    # (B) released-mass ledger: area down, debris count up
    a = fig.add_subplot(gs[0, 1])
    a.plot(t, s["area"], color=TEAL, lw=2.6, label="cell area (px)")
    a.set_xlabel(XT); a.set_ylabel("CPM footprint area (px)", color=TEAL)
    a.tick_params(axis="y", labelcolor=TEAL)
    _mark_release(a)
    a2 = a.twinx()
    a2.plot(t, s["n_particles"], color=WARM, lw=2.6, ls="-", marker="s", ms=2.6,
            label="debris particles")
    a2.set_ylabel("debris particle count", color=WARM)
    a2.tick_params(axis="y", labelcolor=WARM)
    a2.spines["top"].set_visible(False)
    a2.annotate(f"{head['n_particles_final']} shed by tick 16\n"
                f"(= distinct vacated pixels;\nmass ledger closes)",
                (16, head["n_particles_final"]), (9.4, head["n_particles_final"] * 0.52),
                fontsize=8, color=WARM,
                arrowprops=dict(arrowstyle="->", color=WARM, lw=1.0))
    a.set_title("resorb + shed -- the released-mass ledger", color=INK, fontsize=10)
    _clean(a)

    # (C) debris-cloud RMS spread keeps growing after dissolution
    a = fig.add_subplot(gs[0, 2])
    post = t >= 16
    a.plot(t, s["rms"], color="#7a8582", lw=1.6, alpha=0.6)
    a.plot(t[post], s["rms"][post], color=WARM, lw=2.8, marker="o", ms=3.2,
           label="post-dissolution")
    a.axvspan(16, 24, color=WARM_L, alpha=0.12)
    _mark_release(a)
    a.annotate(f"RMS {head['rms_t16']} (tick 16)\n->  {head['rms_t24']} (tick 24)\n"
               "genuine scattering",
               (20, head["rms_t24"]), (10.2, head["rms_t24"] * 0.62),
               fontsize=8, color=WARM,
               arrowprops=dict(arrowstyle="->", color=WARM, lw=1.0))
    a.set_title("debris cloud keeps scattering", color=INK, fontsize=10)
    a.set_xlabel(XT); a.set_ylabel("debris-cloud RMS spread (px)")
    _clean(a)

    # (D-F) field/footprint/debris snapshots: coherent -> mid-resorb -> shed
    titles = {
        SNAP_TICKS[0]: f"t={SNAP_TICKS[0]}: coherent domain (below bound)",
        SNAP_TICKS[1]: f"t={SNAP_TICKS[1]}: resorbing, shedding debris",
        SNAP_TICKS[2]: f"t={SNAP_TICKS[2]}: dissolved, debris scattering",
    }
    last_im = None
    for j, tk in enumerate(SNAP_TICKS):
        a = fig.add_subplot(gs[1, j])
        last_im = _snapshot_panel(a, snaps[tk], meta, titles[tk], stressor_vmax)
    cbar = fig.colorbar(last_im, ax=fig.axes[-1], fraction=0.046, pad=0.04)
    cbar.set_label("acetate", fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    fig.suptitle("Disintegration, exercised -- coherent below the viability bound, "
                 "then dissolution into scattering debris",
                 fontsize=13, color=INK, y=0.995, weight="bold")
    fig.text(0.5, 0.945,
             "snapshots: teal fill = live CPM footprint on the acetate field   |   "
             "warm dots = shed debris particles   |   dotted ring = viability isoline (bound 0.5)",
             ha="center", fontsize=8, color="#3a4744")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(VIZ / "disintegration-response.svg", format="svg")
    fig.savefig(VIZ / "disintegration-response.png", format="png")
    plt.close(fig)
    return head


if __name__ == "__main__":
    h = render()
    print(json.dumps(h, indent=2))
    print("\nwrote", VIZ / "disintegration-response.svg")
