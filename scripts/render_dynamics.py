#!/usr/bin/env python
"""Run every figure's CLOSED-LOOP model (viva_meta_modelers_guide.dynamics) to
completion through the real engine, check its conservation invariant, and render
the characteristic dynamics into each study's visualizations/<slug>-dynamics.svg.

Also writes scripts/_catalog/dynamics_readouts.json (invariant + series stats per
figure) — the honest, physically-checked readouts the studies + report cite.

Run:  PYTHONPATH=. .venv/bin/python scripts/render_dynamics.py [--montage]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from process_bigraph import Composite, gather_emitter_results

from viva_meta_modelers_guide.core import build_core
from viva_meta_modelers_guide.dynamics import DYNAMICS

ROOT = Path(__file__).resolve().parent.parent
STUDIES = ROOT / "workspace" / "studies"
TEAL, OCHRE, TEAL2, GREY = "#0d6e6b", "#a5620f", "#3f9e99", "#657572"
PALETTE = [TEAL, OCHRE, TEAL2, GREY, "#c98a3a", "#1c7a77", "#8b9995"]
INK = "#16211f"

# ── Shared publication style (consistent typography/palette across all figures) ─
plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 150,
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 11, "axes.titlesize": 12, "axes.titleweight": "medium",
    "axes.titlecolor": INK, "axes.labelsize": 11, "axes.labelcolor": INK,
    "xtick.labelsize": 9.5, "ytick.labelsize": 9.5, "xtick.color": GREY, "ytick.color": GREY,
    "axes.edgecolor": GREY, "axes.linewidth": 0.9,
    "legend.fontsize": 9, "legend.frameon": False, "lines.linewidth": 2.4,
    "grid.color": "#c9d2d0", "grid.alpha": 0.4, "grid.linewidth": 0.6,
})


from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
FIELD_CMAP = LinearSegmentedColormap.from_list(
    "teal_field", ["#f7f5f0", "#a7d4d0", "#3f9e99", "#0d6e6b", "#16211f"])


def _units(ylabel):
    """Append '(a.u.)' unless the label already carries a unit / is dimensionless."""
    low = ylabel.lower()
    if any(t in ylabel for t in ("°", "/", "(")) or any(
            t in low for t in ("viability", "count", "position")):
        return ylabel
    return ylabel + " (a.u.)"


def run(composite, t_end):
    core = build_core()
    sim = Composite({"state": composite["state"]}, core=core)
    sim.run(t_end)
    rows = gather_emitter_results(sim)[("emitter",)]
    R = {"time": [r["time"] for r in rows]}
    for k in rows[0]:
        if k != "time":
            R[k] = [float(r[k]) for r in rows]
    return R


def _t(title):
    """Render arrows via mathtext so they don't drop to a missing-glyph box."""
    return title.replace("→", r"$\rightarrow$").replace("⇒", r"$\Rightarrow$")


def _style(ax, title, ylabel, idx=None, n=1):
    ax.set_title(_t(title), pad=8)
    ax.set_xlabel("time (a.u.)"); ax.set_ylabel(_units(ylabel))
    ax.grid(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.margins(x=0.01)
    if n > 1 and idx is not None:        # panel label (a), (b), …
        ax.text(-0.10, 1.10, "(" + chr(97 + idx) + ")", transform=ax.transAxes,
                fontsize=13, fontweight="bold", color=INK, va="top", ha="left")


def render_single(spec):
    R = run(spec["build"](), spec["t_end"])
    panels = spec["panels"]
    fig, axes = plt.subplots(1, len(panels), figsize=(5.2 * len(panels), 3.7))
    if len(panels) == 1:
        axes = [axes]
    for pi, (ax, panel) in enumerate(zip(axes, panels)):
        title, ylabel, series = panel[0], panel[1], panel[2]
        for i, s in enumerate(series):
            ax.plot(R["time"], R[s], color=PALETTE[i % len(PALETTE)], label=s.replace("_", " "))
        _style(ax, title, ylabel, idx=pi, n=len(panels))
        handles = list(ax.get_lines())
        if len(panel) == 5:                                    # twin right axis
            r_ylabel, r_series = panel[3], panel[4]
            ax2 = ax.twinx()
            for j, s in enumerate(r_series):
                ax2.plot(R["time"], R[s], ls="--",
                         color=PALETTE[(len(series) + j) % len(PALETTE)], label=s.replace("_", " "))
            ax2.set_ylabel(_units(r_ylabel)); ax2.spines["top"].set_visible(False); ax2.margins(x=0.01)
            handles += list(ax2.get_lines())
        if len(handles) > 1:
            ax.legend(handles, [h.get_label() for h in handles], loc="best")
    fig.tight_layout()
    return fig, R


def render_field(spec):
    R = run(spec["build"](), spec["t_end"])
    n = sum(1 for k in R if k.startswith("c") and k[1:].isdigit())
    M = np.array([[R[f"c{i}"][t] for i in range(n)] for t in range(len(R["time"]))])
    fig, (axf, axu) = plt.subplots(1, 2, figsize=(10.4, 3.9),
                                   gridspec_kw={"width_ratios": [1.5, 1]})
    im = axf.imshow(M.T, aspect="auto", origin="lower", cmap=FIELD_CMAP,
                    extent=[0, R["time"][-1], 0, n - 1])
    axf.set_title(_t(spec["panels"][0][0]), pad=8)
    axf.set_xlabel("time (a.u.)"); axf.set_ylabel("lattice position")
    axf.text(-0.10, 1.10, "(a)", transform=axf.transAxes, fontsize=13,
             fontweight="bold", color=INK, va="top", ha="left")
    cb = fig.colorbar(im, ax=axf, fraction=0.046, pad=0.04); cb.set_label("nutrient conc. (a.u.)")
    axu.plot(R["time"], R["uptake_total"], color=OCHRE, label="cumulative uptake")
    axu.plot(R["time"], R["biomass"], color=TEAL, label="biomass")
    _style(axu, "Cell draws the field down", "amount", idx=1, n=2)
    axu.legend(loc="best")
    fig.tight_layout()
    return fig, R


def render_multi(spec):
    variants = spec["build"]()
    Rs = {name: run(comp, spec["t_end"]) for name, comp in variants.items()}
    overlay = spec["overlay"]
    fig, axes = plt.subplots(1, len(overlay), figsize=(5.2 * len(overlay), 3.7))
    if len(overlay) == 1:
        axes = [axes]
    for pi, (ax, (title, ylabel, series)) in enumerate(zip(axes, overlay)):
        for i, (name, R) in enumerate(Rs.items()):
            ax.plot(R["time"], R[series], color=PALETTE[i % len(PALETTE)], label=name)
        _style(ax, title, ylabel, idx=pi, n=len(overlay))
        ax.legend(loc="best")
    fig.tight_layout()
    return fig, Rs


def main():
    montage = "--montage" in sys.argv
    readouts = {}
    thumbs = []
    for slug, spec in DYNAMICS.items():
        if spec.get("multi"):
            fig, R = render_multi(spec)
            inv = spec["invariant"][1](R)
        elif spec.get("field"):
            fig, R = render_field(spec)
            inv = spec["invariant"][1](R)
        else:
            fig, R = render_single(spec)
            inv = spec["invariant"][1](R)
        out = STUDIES / slug / "visualizations" / f"{slug}-dynamics.svg"
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, format="svg")
        png = ROOT / "scripts" / "_catalog" / f"{slug}-dynamics.png"
        png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(png, format="png")
        thumbs.append(png)
        plt.close(fig)
        readouts[slug] = {"invariant_kind": spec["invariant"][0], "invariant": inv}
        print(f"  ✓ {slug}: {inv}")
    (ROOT / "scripts" / "_catalog" / "dynamics_readouts.json").write_text(
        json.dumps(readouts, indent=2))
    print(f"\nwrote {len(readouts)} dynamics figures + dynamics_readouts.json")

    if montage:
        from PIL import Image
        imgs = [Image.open(p) for p in thumbs]
        w = max(i.width for i in imgs)
        scaled = [i.resize((w, int(i.height * w / i.width))) for i in imgs]
        H = sum(i.height for i in scaled)
        canvas = Image.new("RGB", (w, H), "white")
        y = 0
        for i in scaled:
            canvas.paste(i, (0, y)); y += i.height
        mp = ROOT / "scripts" / "_catalog" / "_montage.png"
        canvas.save(mp)
        print(f"montage -> {mp}")


if __name__ == "__main__":
    main()
