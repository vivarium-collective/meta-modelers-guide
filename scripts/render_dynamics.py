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


def _style(ax, title, ylabel):
    ax.set_title(title, fontsize=10, color="#16211f")
    ax.set_xlabel("time"); ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.15)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def render_single(spec):
    R = run(spec["build"](), spec["t_end"])
    panels = spec["panels"]
    fig, axes = plt.subplots(1, len(panels), figsize=(4.7 * len(panels), 3.5), dpi=110)
    if len(panels) == 1:
        axes = [axes]
    for ax, panel in zip(axes, panels):
        title, ylabel, series = panel[0], panel[1], panel[2]
        for i, s in enumerate(series):
            ax.plot(R["time"], R[s], lw=2.2, color=PALETTE[i % len(PALETTE)],
                    label=s.replace("_", " "))
        _style(ax, title, ylabel)
        handles = list(ax.get_lines())
        if len(panel) == 5:                                    # twin right axis
            r_ylabel, r_series = panel[3], panel[4]
            ax2 = ax.twinx()
            for j, s in enumerate(r_series):
                ax2.plot(R["time"], R[s], lw=2.4, ls="--",
                         color=PALETTE[(len(series) + j) % len(PALETTE)],
                         label=s.replace("_", " "))
            ax2.set_ylabel(r_ylabel)
            ax2.spines["top"].set_visible(False)
            handles += list(ax2.get_lines())
        if len(handles) > 1:
            ax.legend(handles, [h.get_label() for h in handles], fontsize=7.5, frameon=False)
    fig.tight_layout()
    return fig, R


def render_field(spec):
    R = run(spec["build"](), spec["t_end"])
    n = sum(1 for k in R if k.startswith("c") and k[1:].isdigit())
    M = np.array([[R[f"c{i}"][t] for i in range(n)] for t in range(len(R["time"]))])
    fig, (axf, axu) = plt.subplots(1, 2, figsize=(9.4, 3.5), dpi=110,
                                   gridspec_kw={"width_ratios": [1.5, 1]})
    im = axf.imshow(M.T, aspect="auto", origin="lower", cmap="viridis",
                    extent=[0, R["time"][-1], 0, n - 1])
    axf.set_title(spec["panels"][0][0], fontsize=10, color="#16211f")
    axf.set_xlabel("time"); axf.set_ylabel("lattice position")
    fig.colorbar(im, ax=axf, fraction=0.046, pad=0.04, label="nutrient conc.")
    axu.plot(R["time"], R["uptake_total"], lw=2.2, color=OCHRE, label="cumulative uptake")
    axu.plot(R["time"], R["biomass"], lw=2.2, color=TEAL, label="biomass")
    _style(axu, "Cell draws the field down", "amount")
    axu.legend(fontsize=7.5, frameon=False)
    fig.tight_layout()
    return fig, R


def render_multi(spec):
    variants = spec["build"]()
    Rs = {name: run(comp, spec["t_end"]) for name, comp in variants.items()}
    overlay = spec["overlay"]
    fig, axes = plt.subplots(1, len(overlay), figsize=(4.7 * len(overlay), 3.5), dpi=110)
    if len(overlay) == 1:
        axes = [axes]
    for ax, (title, ylabel, series) in zip(axes, overlay):
        for i, (name, R) in enumerate(Rs.items()):
            ax.plot(R["time"], R[series], lw=2.2, color=PALETTE[i % len(PALETTE)], label=name)
        _style(ax, title, ylabel)
        ax.legend(fontsize=7.5, frameon=False)
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
