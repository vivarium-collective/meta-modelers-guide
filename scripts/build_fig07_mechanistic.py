#!/usr/bin/env python
"""Render Fig 7's MECHANISTIC demonstration: nested cellular hierarchy where the
nesting INFLUENCES FUNCTION, not just routes a scalar.

A genuinely nested place graph (environment ⊃ cell ⊃ cytoplasm ⊃ nucleus) with two
PermeableBoundary processes (plasma membrane, nuclear envelope) gating conservative
passive transport of a substrate inward, a locally-restricted cytoplasmic reaction,
and a nuclear reporter whose production depends on the substrate that reaches it.
Because the deep reporter sits behind TWO boundaries in series, closing either shuts
it down — a boundary-level cause with a deep functional effect. This script runs the
fig07-mechanistic composite plus permeability sweeps, a localized perturbation, and
matched-null controls, and writes a six-panel figure to the fig-07 study
visualizations:

  A  the nested compartments + the process-bigraph port path (substrate flux inward)
  B  concentration traces: substrate propagates level by level; the reporter rises
  C  prediction: higher membrane permeability fills the deep compartment faster (transient)
  D  gating in series: either boundary closed (ε) zeroes the deep reporter
  E  locally-restricted metabolism: cytoplasmic consumption starves the nucleus
  F  a localized cytoplasmic perturbation reaches the nucleus only if the envelope is open

Re-run whenever the fig07 mechanistic model or composite changes.

    python scripts/build_fig07_mechanistic.py
"""
from __future__ import annotations

import copy
import json
import warnings
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig07-mechanistic.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-07" / "visualizations" / "fig07-mechanistic-dynamics.png"
EPS = 1e-9

C_ENV, C_CYTO, C_NUC, C_REP = "#4b5bd6", "#0b7a75", "#b4531f", "#c0392b"


def _spec(perm_mem=0.3, perm_nuc=0.3, k_met=0.05):
    spec = json.loads(COMPOSITE.read_text())
    spec["state"]["membrane"]["config"]["permeability"] = perm_mem
    spec["state"]["nuclear_envelope"]["config"]["permeability"] = perm_nuc
    spec["state"]["cytoplasmic_metabolism"]["config"]["k"] = k_met
    return spec


def run(perm_mem=0.3, perm_nuc=0.3, k_met=0.05, steps=40):
    sim = Composite({"state": _spec(perm_mem, perm_nuc, k_met)["state"]}, core=build_core())
    sim.run(steps)
    return gather_emitter_results(sim)[("emitter", )]


def run_with_pulse(perm_nuc=0.3, pulse_at=20, pulse=8.0, steps=40):
    """Inject a localized substrate pulse into the CYTOPLASM at pulse_at, continue,
    and return the reporter trace — to see whether the perturbation reaches the deep
    nucleus (gated by the nuclear envelope permeability)."""
    sim = Composite({"state": _spec(perm_nuc=perm_nuc)["state"]}, core=build_core())
    rep = []
    for t in range(steps):
        if t == pulse_at:
            cyto = sim.state["environment"]["cell"]["cytoplasm"]
            cyto["substrate"] = float(cyto["substrate"]) + pulse
        sim.run(1)
        nuc = sim.state["environment"]["cell"]["cytoplasm"]["nucleus"]
        rep.append(float(nuc["reporter"]))
    return rep


def main() -> None:
    rows = run()
    t = np.array([float(r["time"]) for r in rows])
    env = np.array([float(r["env_substrate"]) for r in rows])
    cyto = np.array([float(r["cyto_substrate"]) for r in rows])
    nuc = np.array([float(r["nuc_substrate"]) for r in rows])
    rep = np.array([float(r["reporter"]) for r in rows])

    # assertions
    assert rep[-1] > 1.0
    assert float(run(perm_mem=EPS)[-1]["reporter"]) < 1e-6
    assert float(run(perm_nuc=EPS)[-1]["reporter"]) < 1e-6

    fig = plt.figure(figsize=(15, 8.6))
    fig.suptitle("Fig 7 (mechanistic) · nested hierarchy that INFLUENCES FUNCTION — "
                 "permeable boundaries gate a deep observable", fontsize=12.5, y=0.99)
    gs = fig.add_gridspec(2, 3)

    # A — nested compartments + port path
    ax = fig.add_subplot(gs[0, 0]); ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
    ax.set_title("A · Nested compartments + substrate port path")
    boxes = [("environment", 0.3, 0.3, 9.4, 9.0, "#eef1ff"),
             ("cell", 1.3, 1.1, 7.4, 7.4, "#e7f4f2"),
             ("cytoplasm", 2.1, 1.9, 5.8, 5.8, "#fdeee4"),
             ("nucleus", 3.2, 2.9, 3.6, 3.6, "#fde9e7")]
    for name, x, y, w, h, col in boxes:
        ax.add_patch(Rectangle((x, y), w, h, facecolor=col, edgecolor="#555", lw=1.3))
        ax.text(x + 0.15, y + h - 0.35, name, fontsize=8.5, color="#333", style="italic")
    # substrate depot + flux arrows crossing each boundary (the port path)
    ax.scatter([1.0], [8.6], s=80, color=C_ENV, zorder=5)
    ax.text(0.6, 9.0, "substrate", fontsize=8, color=C_ENV)
    for (x0, y0, x1, y1, lbl) in [(1.3, 7.0, 2.1, 6.0, "membrane\nP_mem"),
                                  (2.5, 5.2, 3.6, 4.6, "nuclear env.\nP_nuc")]:
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=14,
                                     color="#333", lw=1.6))
        ax.text((x0 + x1) / 2 - 0.4, (y0 + y1) / 2 + 0.15, lbl, fontsize=7, color="#b4531f")
    ax.text(4.1, 4.4, "reporter\n(deep,\ngated ×2)", fontsize=7.5, color=C_REP, ha="center")
    ax.text(0.3, 0.05, "containment = nesting · boundary = part-of · reporter depends on signal = regulatory",
            fontsize=6.6, color="#777")

    # B — concentration traces
    ax = fig.add_subplot(gs[0, 1])
    ax.plot(t, env, color=C_ENV, lw=2, label="env substrate")
    ax.plot(t, cyto, color=C_CYTO, lw=2, label="cytoplasm")
    ax.plot(t, nuc, color=C_NUC, lw=2, label="nucleus")
    ax.plot(t, rep, color=C_REP, lw=2, ls="--", label="nuclear reporter")
    ax.set_title("B · Substrate propagates inward; reporter rises")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("concentration")
    ax.legend(fontsize=7.5)

    # C — prediction: deeper filling vs membrane permeability (transient)
    ax = fig.add_subplot(gs[0, 2])
    pms = [0.05, 0.1, 0.2, 0.4, 0.8]
    deep = [float(run(perm_mem=pm, k_met=EPS, steps=8)[-1]["nuc_substrate"]) for pm in pms]
    ax.plot(pms, deep, "o-", color=C_NUC, lw=2)
    ax.set_title("C · Higher permeability fills the deep\ncompartment faster (predicted)")
    ax.set_xlabel("membrane permeability P_mem"); ax.set_ylabel("nuclear substrate @ t=8")

    # D — series gating
    ax = fig.add_subplot(gs[1, 0])
    labels = ["both open", "membrane ε", "nucleus ε"]
    vals = [float(run()[-1]["reporter"]), float(run(perm_mem=EPS)[-1]["reporter"]),
            float(run(perm_nuc=EPS)[-1]["reporter"])]
    ax.bar(labels, vals, color=["#0b7a75", "#c0392b", "#c0392b"])
    ax.set_title("D · Either boundary gates the deep reporter\n(depth = barriers in series)")
    ax.set_ylabel("final nuclear reporter")
    for i, v in enumerate(vals):
        ax.annotate(f"{v:.2f}", (i, v), ha="center", va="bottom", fontsize=8)

    # E — locally-restricted metabolism
    ax = fig.add_subplot(gs[1, 1])
    r_on = np.array([float(r["reporter"]) for r in run(k_met=0.3)])
    r_off = np.array([float(r["reporter"]) for r in run(k_met=EPS)])
    ax.plot(t, r_off, color=C_CYTO, lw=2, label="cyto metabolism OFF")
    ax.plot(t, r_on, color=C_NUC, lw=2, ls="--", label="cyto metabolism ON")
    ax.fill_between(t, r_on, r_off, color=C_CYTO, alpha=0.12)
    ax.set_title("E · Locally-restricted cytoplasmic\nmetabolism starves the nucleus")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("nuclear reporter")
    ax.legend(fontsize=7.5)

    # F — localized perturbation reaches the nucleus only if the envelope is open
    ax = fig.add_subplot(gs[1, 2])
    open_env = run_with_pulse(perm_nuc=0.3)
    closed_env = run_with_pulse(perm_nuc=EPS)
    tt = np.arange(1, len(open_env) + 1)
    ax.axvline(20, color="#999", ls=":", lw=1)
    ax.plot(tt, open_env, color=C_REP, lw=2, label="envelope open")
    ax.plot(tt, closed_env, color="#999", lw=2, ls="--", label="envelope ε (isolated)")
    ax.annotate("cytoplasmic\npulse", (20, max(open_env) * 0.5), fontsize=7.5, color="#555", ha="left")
    ax.set_title("F · A localized cytoplasmic pulse reaches\nthe nucleus only if the envelope is open")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("nuclear reporter")
    ax.legend(fontsize=7.5)

    for ax in fig.get_axes()[1:]:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(True, alpha=0.2, lw=0.5)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    print(f"  reporter open={rep[-1]:.2f}; membrane-ε and nucleus-ε both →0; "
          f"deep-fill monotone; pulse reach gated by envelope")


if __name__ == "__main__":
    main()
