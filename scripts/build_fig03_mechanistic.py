#!/usr/bin/env python
"""Render Fig 3's (paper §Cellular interface) MECHANISTIC demonstration: a cell
whose interface ports are COUPLED through a shared ATP pool and a temperature-set
enzyme activity, so a perturbation of one input propagates through internal state
to every downstream port — unlike the baseline's independent per-port responses.

Runs the fig03-mechanistic composite (heat shock 37→48 °C at t=12) plus a
nutrient-starvation scenario, a metabolically-disabled control, and a small
input→output response matrix. Writes a six-panel figure to the fig-03 study viz:

  A  heat-shock cascade: one temperature step propagates to enzyme, uptake, ATP,
     growth AND viability (shared-state coupling)
  B  membrane cross-section with simulated port flows, before vs after the shock
  C  nutrient-starvation cascade (the second perturbation)
  D  cross-port response matrix: perturb one input, which outputs move
     (mechanistic = dense/off-diagonal; disabled = diagonal only)
  E  intact vs metabolically-disabled: propagation broken when metabolism is off
  F  ATP budget: production vs (growth cost + maintenance) — growth paid from ATP

    python scripts/build_fig03_mechanistic.py
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
from matplotlib.patches import FancyArrow, Rectangle

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.handlers_fig03_mech import MetabolicCell

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig03-mechanistic.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-03" / "visualizations" / "fig03-mechanistic-dynamics.png"
EPS = 1e-9
C_ENZ, C_UPT, C_ATP, C_GROW, C_VIAB, C_TEMP = "#7a5195", "#0b7a75", "#4b5bd6", "#b4531f", "#c0392b", "#d19a00"


def run(cell_over=None, env_over=None, steps=24):
    spec = json.loads(COMPOSITE.read_text())
    if cell_over:
        spec["state"]["cell"]["config"].update(cell_over)
    if env_over:
        spec["state"]["env_driver"]["config"].update(env_over)
        if "nutrient_hi" in env_over:
            spec["state"]["env"]["nutrient"]["_default"] = env_over["nutrient_hi"]
        if "temp_base" in env_over:
            spec["state"]["env"]["temperature"]["_default"] = env_over["temp_base"]
    sim = Composite({"state": spec["state"]}, core=build_core())
    sim.run(steps)
    return gather_emitter_results(sim)[("emitter",)]


def col(rows, k):
    return np.array([float(r[k]) for r in rows])


def _instant(cell_cfg, nutrient, temp):
    """Instantaneous outputs for a cell at a given input (fresh instance → set
    deltas read as absolute values)."""
    cell = MetabolicCell(cell_cfg, core=build_core())
    return cell.update({"nutrient": nutrient, "temperature": temp, "atp": 2.5, "biomass": 1.0, "viability": 1.0}, 1.0)


def response_matrix(cfg):
    """Fractional response of each output to a perturbation of each input
    (nutrient −30%, temperature +6 °C), one-step instantaneous."""
    base = _instant(cfg, 2.0, 37.0)
    outs = ["uptake", "atp_production", "growth_rate", "enzyme_activity"]
    base_g = _instant(cfg, 2.0, 37.0)
    # growth here needs ATP state; use a short transient proxy via atp_production→growth coupling.
    perts = {"nutrient −30%": _instant(cfg, 1.4, 37.0), "temperature +6°C": _instant(cfg, 2.0, 43.0)}
    M = np.zeros((len(perts), len(outs)))
    for i, (_, p) in enumerate(perts.items()):
        for j, o in enumerate(outs):
            b = float(base[o]); v = float(p[o])
            M[i, j] = 0.0 if abs(b) < 1e-12 else (v - b) / abs(b)
    return list(perts.keys()), outs, M


def main() -> None:
    rows = run()  # heat shock
    t = col(rows, "time")
    starve = run(env_over={"nutrient_hi": 2.0, "nutrient_lo": 0.03, "nutrient_step_time": 12.0,
                           "temp_base": 37.0, "temp_step": 37.0, "temp_step_time": 1e9})
    disabled = run(cell_over={"catalytic_capacity": EPS})

    cfg_full = json.loads(COMPOSITE.read_text())["state"]["cell"]["config"]
    cfg_dis = dict(cfg_full, catalytic_capacity=EPS)

    # ── assertions ────────────────────────────────────────────────────────────
    assert col(rows, "enzyme_activity")[13] < 0.4 * col(rows, "enzyme_activity")[11]
    assert col(rows, "growth_rate")[16] < 0.4 * col(rows, "growth_rate")[11]
    assert max(col(disabled, "growth_rate")) < 1e-3

    fig, axes = plt.subplots(2, 3, figsize=(15, 8.6))
    fig.suptitle("Fig 3 (mechanistic) · the cellular interface — ports coupled through a shared ATP/enzyme state "
                 "(a perturbation propagates)", fontsize=12.5, y=0.99)

    STEP = 12
    # A — heat-shock cascade
    ax = axes[0, 0]
    ax.axvline(STEP, color="#888", ls=":", lw=1.2)
    ax.axvspan(STEP, t[-1], color=C_TEMP, alpha=0.05)
    for k, c, lab in [("enzyme_activity", C_ENZ, "enzyme activity"), ("uptake", C_UPT, "uptake"),
                      ("growth_rate", C_GROW, "growth"), ("viability", C_VIAB, "viability")]:
        y = col(rows, k); ax.plot(t, y / max(y.max(), 1e-9), color=c, lw=2, label=lab)
    ax.set_title("A · Heat shock (37→48 °C at t=12) cascades to every port")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("normalized (each ÷ its max)")
    ax.legend(fontsize=7.5, loc="center left")

    # B — membrane cross-section with port flows, before vs after
    ax = axes[0, 1]; ax.axis("off")
    ax.set_title("B · Membrane cross-section — port flows (pre vs post shock)")
    pre, post = rows[11], rows[13]
    for yc, tag, r in [(0.70, "pre-shock (37 °C)", pre), (0.28, "post-shock (48 °C)", post)]:
        ax.add_patch(Rectangle((0.35, yc - 0.09), 0.06, 0.18, color="#999"))  # membrane
        ax.text(0.14, yc + 0.13, tag, fontsize=8.5, weight="bold")
        ax.text(0.08, yc, "env", fontsize=8, ha="center", va="center")
        ax.text(0.62, yc + 0.02, f"ATP {float(r['atp']):.2f}", fontsize=8, ha="center", color=C_ATP)
        up = float(r["uptake"]); gr = float(r["growth_rate"])
        ax.add_patch(FancyArrow(0.14, yc, 0.18, 0, width=0.004 + 0.06 * up, color=C_UPT,
                                length_includes_head=True, head_width=0.03 + 0.06 * up))
        ax.text(0.22, yc + 0.11, f"uptake {up:.2f}", fontsize=7.5, color=C_UPT, ha="center")
        ax.add_patch(FancyArrow(0.66, yc, 0.20, 0, width=0.004 + 0.12 * gr, color=C_GROW,
                                length_includes_head=True, head_width=0.03 + 0.12 * gr))
        ax.text(0.80, yc + 0.11, f"growth {gr:.2f}", fontsize=7.5, color=C_GROW, ha="center")
        ax.text(0.80, yc - 0.12, f"viab {float(r['viability']):.2f}", fontsize=7.5, color=C_VIAB, ha="center")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    # C — nutrient starvation cascade
    ax = axes[0, 2]
    ax.axvline(STEP, color="#888", ls=":", lw=1.2)
    for k, c, lab in [("uptake", C_UPT, "uptake"), ("atp", C_ATP, "ATP pool"),
                      ("growth_rate", C_GROW, "growth"), ("viability", C_VIAB, "viability")]:
        y = col(starve, k); ax.plot(t, y / max(y.max(), 1e-9), color=c, lw=2, label=lab)
    ax.set_title("C · Nutrient starvation (2.0→0.03 at t=12) — same cascade")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("normalized"); ax.legend(fontsize=7.5)

    # D — cross-port response matrix (mechanistic)
    ax = axes[1, 0]
    inl, outl, M = response_matrix(cfg_full)
    im = ax.imshow(M, cmap="RdBu", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(outl))); ax.set_xticklabels(["uptake", "ATP prod", "growth", "enzyme"], fontsize=8, rotation=20)
    ax.set_yticks(range(len(inl))); ax.set_yticklabels(inl, fontsize=8)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            ax.text(j, i, f"{M[i,j]:+.2f}", ha="center", va="center", fontsize=8,
                    color="white" if abs(M[i, j]) > 0.5 else "black")
    ax.set_title("D · Cross-port response matrix (one input moves many outputs)")
    fig.colorbar(im, ax=ax, label="fractional Δ output", fraction=0.046, pad=0.04)

    # E — intact vs disabled biomass
    ax = axes[1, 1]
    ax.plot(t, col(rows, "biomass"), color=C_GROW, lw=2, label="intact (heat shock)")
    ax.plot(t, col(disabled, "biomass"), color="#999", lw=2, ls="--", label="metabolism disabled (ε)")
    ax.axvline(STEP, color="#888", ls=":", lw=1.0)
    ax.set_title("E · Disabling metabolism breaks the propagation")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("biomass"); ax.legend(fontsize=8)

    # F — ATP budget
    ax = axes[1, 2]
    prod = col(rows, "atp_production")
    ax.plot(t, prod, color=C_ATP, lw=2, label="ATP production")
    ax.plot(t, col(rows, "atp"), color="#4b5bd6", lw=1.6, ls="--", label="ATP pool")
    ax.axhline(cfg_full["maintenance_rate"], color=C_VIAB, lw=1.2, ls=":", label="maintenance demand")
    ax.axvline(STEP, color="#888", ls=":", lw=1.0)
    ax.set_title("F · ATP budget — growth is paid out of ATP")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("ATP (energy units)"); ax.legend(fontsize=7.5)

    for ax in [axes[0, 0], axes[0, 2], axes[1, 1], axes[1, 2]]:
        ax.grid(True, alpha=0.2, lw=0.5); ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    print(f"  heat shock: enzyme {col(rows,'enzyme_activity')[11]:.2f}→{col(rows,'enzyme_activity')[13]:.2f}, "
          f"growth {col(rows,'growth_rate')[11]:.2f}→{col(rows,'growth_rate')[16]:.2f}, "
          f"viab {col(rows,'viability')[-1]:.2f}; disabled biomass flat at {col(disabled,'biomass')[-1]:.2f}")


if __name__ == "__main__":
    main()
