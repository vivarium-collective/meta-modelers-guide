#!/usr/bin/env python
"""Render the *molecular-interfaces* study's flagship evidence figure — the
**response of the contract**.

The paper's §Molecular interface (Fig 6) frames a molecule as a typed interface
exposing physical channels; this study takes the CHEMICAL channel onto a 2D
lattice as a Gray-Scott reaction-diffusion system and asks the discriminating
question one channel down. The draft's contract demands a *diffusion-driven
instability*: a spatial pattern forms ONLY when the activator/inhibitor
diffusion is differential (Du > Dv) — the equal-diffusion control (Du = Dv)
produces NO pattern; and a temperature PARAMETER (a static uniform Arrhenius
rate multiplier) GRADES that pattern rather than collapsing it.

The legacy evidence baked three fixed operating points (flagship, control,
thermal) into GIFs and reported endpoint scalars. This renderer instead
*exercises the contract*: it drives the REAL compiled ``GrayScott`` executable
(``local:GrayScott``, the exact composites the study cites — same baked
seed_uv(seed=1) initial field, same F/k/dt/steps_per_tick=500, 16 ticks = 8000
internal steps each) across a SWEEP of the diffusion ratio Du/Dv and of the
temperature parameter, and measures an order parameter (the inhibitor-field
spatial variance v_var, and the connected-domain count) off each final field.
It graphs the sharp onset from uniform to patterned that the contract demands,
recovers the equal-diffusion control sitting at ~0 amplitude, and shows the
final-field "money shots" across the boundary. Every curve is the draft's own
physics run through the engine — nothing invented, nothing outside the study.

Outputs (into the study's visualizations/):
  molecular-interfaces-response.svg / .png  — the multi-panel response figure
Prints the headline numbers (control vs patterned amplitude, onset boundary,
n_domains coarsening under temperature).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec
from matplotlib import font_manager  # noqa: F401  (ensure font cache is built)
from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.molecular.gray_scott import PATTERN_FLOOR

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "meta_modelers_guide" / "composites"
VIZ = ROOT / "workspace" / "studies" / "molecular-interfaces" / "visualizations"

TURING = "molecular-turing-pattern"          # canonical spot regime Du=0.16, Dv=0.08
CONTROL = "molecular-equal-diffusion-control"  # Du = Dv = 0.12 (causal control)

# Book palette — the guide's teal family + a warm accent.
INK = "#16211f"
TEAL = "#0d6e6b"
TEAL_L = "#3f9e99"
WARM = "#a5620f"
WARM_L = "#c98a3a"
GRID = "#c9d3d1"
UNIFORM = "#7a8582"
FIELD_CMAP = "magma"  # inhibitor v field — classic RD pattern colormap, reads in both themes

_CORE = None


def _core():
    global _CORE
    if _CORE is None:
        _CORE = build_core()
    return _CORE


def _load(stem):
    """Deep-copied state dict for a study composite (the real baked spec)."""
    state = json.loads((COMPOSITES / f"{stem}.composite.json").read_text())["state"]
    return json.loads(json.dumps(state))


def _run(state, gs_over=None, temp=None, total_time=16.0):
    """Run the pre-compiled Gray-Scott executable, optionally overriding the
    ``gs.config`` process params (Du/Dv/F/k/Ea/Tref) and/or injecting a static
    uniform ``temperature`` field, and read the final field + observables off
    the composite's own RAMEmitter.

    Returns (v_var, n_domains, patterned, final_v_field).
    """
    st = json.loads(json.dumps(state))
    if gs_over:
        st["gs"]["config"].update({k: float(v) for k, v in gs_over.items()})
    if temp is not None:
        # add the thermal channel: a static uniform temperature field over the
        # SAME baked seed field — the Arrhenius rate multiplier in the process
        # takes effect only when this field is present.
        shape = np.array(st["fields"]["u"]).shape
        st["fields"]["temperature"] = np.full(shape, float(temp)).tolist()
    sim = Composite({"state": st}, core=_core())
    sim.run(total_time)
    row = gather_emitter_results(sim)[("emitter",)][-1]
    return (float(row["v_var"]), float(row["n_domains"]),
            float(row["patterned"]), np.array(row["v"], dtype=float))


def render():
    VIZ.mkdir(parents=True, exist_ok=True)
    head = {}
    base = _load(TURING)

    # ── SWEEP 1: the diffusion ratio Du/Dv (Du fixed at 0.16, vary Dv) ──────────
    # This is the contract's core demand: differential diffusion is the CAUSE of
    # structure. ratio == 1 (Du = Dv) is the equal-diffusion regime → no pattern.
    Du = 0.16
    Dv_vals = np.array([0.160, 0.140, 0.130, 0.120, 0.115, 0.110, 0.105,
                        0.100, 0.090, 0.080, 0.070, 0.060, 0.050, 0.040])
    ratios, sw_vvar, sw_ndom, sw_pat, sw_field = [], [], [], [], {}
    for Dv in Dv_vals:
        vv, nd, pat, fld = _run(base, {"Du": Du, "Dv": Dv})
        ratios.append(Du / Dv)
        sw_vvar.append(vv); sw_ndom.append(nd); sw_pat.append(pat)
        sw_field[round(Du / Dv, 3)] = fld
    ratios = np.array(ratios)
    sw_vvar = np.array(sw_vvar); sw_ndom = np.array(sw_ndom); sw_pat = np.array(sw_pat)

    # explicit equal-diffusion causal control (Du = Dv = 0.12) — the study's own
    ctrl_vvar, ctrl_ndom, ctrl_pat, ctrl_field = _run(_load(CONTROL))

    # onset boundary: interpolate the ratio at which v_var crosses PATTERN_FLOOR
    order = np.argsort(ratios)
    r_s, v_s = ratios[order], sw_vvar[order]
    onset = None
    for i in range(1, len(r_s)):
        if v_s[i - 1] <= PATTERN_FLOOR < v_s[i]:
            onset = float(r_s[i - 1] + (PATTERN_FLOOR - v_s[i - 1])
                          * (r_s[i] - r_s[i - 1]) / (v_s[i] - v_s[i - 1]))
            break

    canon_vvar = float(sw_vvar[np.argmin(np.abs(ratios - 2.0))])
    head.update(
        control_amplitude_vvar=round(ctrl_vvar, 6),
        control_n_domains=int(ctrl_ndom),
        control_patterned=ctrl_pat,
        canonical_amplitude_vvar=round(canon_vvar, 5),
        canonical_ratio=2.0,
        pattern_floor=PATTERN_FLOOR,
        onset_ratio_Du_over_Dv=round(onset, 3) if onset else None,
    )

    # ── SWEEP 2: the temperature parameter (Arrhenius rate multiplier) ──────────
    # inject a static uniform temperature field over the FLAGSHIP seed + chemistry
    # (Ea=0.15, Tref=1.0). T=1.0 → rate=1 → byte-identical to the flagship.
    T_vals = np.array([1.00, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30])
    th_vvar, th_ndom, th_pat, th_field = [], [], [], {}
    for T in T_vals:
        vv, nd, pat, fld = _run(base, {"Ea": 0.15, "Tref": 1.0}, temp=T)
        th_vvar.append(vv); th_ndom.append(nd); th_pat.append(pat)
        th_field[round(float(T), 3)] = fld
    th_vvar = np.array(th_vvar); th_ndom = np.array(th_ndom); th_pat = np.array(th_pat)
    head.update(
        thermal_n_domains_T1p0=int(th_ndom[0]),
        thermal_n_domains_T1p2=int(th_ndom[np.argmin(np.abs(T_vals - 1.2))]),
        thermal_vvar_T1p0=round(float(th_vvar[0]), 5),
        thermal_vvar_T1p2=round(float(th_vvar[np.argmin(np.abs(T_vals - 1.2))]), 5),
        thermal_all_patterned=bool(np.all(th_pat == 1.0)),
    )

    # ── figure ──────────────────────────────────────────────────────────────────
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": "#3a4744",
                         "axes.labelcolor": INK, "text.color": INK,
                         "xtick.color": INK, "ytick.color": INK})
    fig = plt.figure(figsize=(13.6, 8.4), dpi=120)
    outer = gridspec.GridSpec(2, 1, height_ratios=[1.0, 0.92], hspace=0.42,
                              left=0.06, right=0.965, top=0.9, bottom=0.06)
    top = outer[0].subgridspec(1, 3, wspace=0.30)
    bot = outer[1].subgridspec(1, 5, wspace=0.12)

    def _clean(a):
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
        a.grid(True, color=GRID, alpha=0.5, lw=0.6)

    # (A) order parameter: pattern amplitude v_var vs diffusion ratio
    a = fig.add_subplot(top[0, 0])
    pat_mask = sw_pat == 1.0
    a.plot(ratios[order], sw_vvar[order], color=TEAL, lw=2.2, zorder=2)
    a.scatter(ratios[~pat_mask], sw_vvar[~pat_mask], color=UNIFORM, s=34,
              zorder=3, label="uniform (patterned = 0)")
    a.scatter(ratios[pat_mask], sw_vvar[pat_mask], color=TEAL, s=34,
              zorder=3, label="patterned = 1")
    a.scatter([1.0], [ctrl_vvar], marker="D", s=70, color=WARM, zorder=4,
              edgecolor="white", linewidth=0.8, label="equal-diff control")
    a.axhline(PATTERN_FLOOR, ls=":", color="#7a8582", lw=1.1)
    a.annotate("pattern floor", (ratios.max(), PATTERN_FLOOR),
               (ratios.max() - 2.6, PATTERN_FLOOR + 0.0009), fontsize=7.5, color="#7a8582")
    if onset:
        a.axvspan(1.0, onset, color=UNIFORM, alpha=0.12)
        a.axvline(onset, ls="--", color=WARM, lw=1.3)
        a.annotate(f"onset\nDu/Dv ≈ {onset:.2f}", (onset, canon_vvar * 0.62),
                   (onset + 0.25, canon_vvar * 0.42), fontsize=8, color=WARM)
    a.set_title("order parameter — pattern amplitude", color=INK, fontsize=10.5)
    a.set_xlabel("diffusion ratio  Du / Dv"); a.set_ylabel("v-field spatial variance  v_var")
    a.legend(frameon=False, fontsize=7.2, loc="upper left")
    _clean(a)

    # (B) connected v-domains vs diffusion ratio
    a = fig.add_subplot(top[0, 1])
    a.plot(ratios[order], sw_ndom[order], color=TEAL, lw=2.2, marker="o", ms=4, zorder=2)
    a.scatter([1.0], [ctrl_ndom], marker="D", s=70, color=WARM, zorder=4,
              edgecolor="white", linewidth=0.8)
    if onset:
        a.axvspan(1.0, onset, color=UNIFORM, alpha=0.12)
        a.axvline(onset, ls="--", color=WARM, lw=1.3)
    a.annotate("uniform:\n0 domains", (1.0, 2), (1.15, 22), fontsize=7.8, color=UNIFORM)
    a.annotate("canonical regime\n(Du/Dv = 2)", (2.0, sw_ndom[np.argmin(np.abs(ratios - 2.0))]),
               (2.15, 45), fontsize=7.8, color=TEAL)
    a.set_title("spatial structure — connected domains", color=INK, fontsize=10.5)
    a.set_xlabel("diffusion ratio  Du / Dv"); a.set_ylabel("n connected v-domains")
    _clean(a)

    # (C) temperature parameter GRADES the pattern (coarsening, not collapse)
    a = fig.add_subplot(top[0, 2])
    a.plot(T_vals, th_ndom, color=WARM, lw=2.3, marker="o", ms=4.5, zorder=3,
           label="n_domains")
    a.set_title("temperature parameter grades the chemical channel", color=INK, fontsize=10.5)
    a.set_xlabel("uniform temperature field  T  (Tref = 1.0, Ea = 0.15)")
    a.set_ylabel("n connected v-domains", color=WARM)
    a.tick_params(axis="y", colors=WARM)
    a.annotate(f"T = 1.0 → {int(th_ndom[0])} domains\n(≡ flagship, rate = 1)",
               (1.0, th_ndom[0]), (1.035, 10.1), fontsize=7.8, color=WARM)
    iT12 = int(np.argmin(np.abs(T_vals - 1.2)))
    a.annotate(f"T = 1.2 → {int(th_ndom[iT12])} domains\ncoarsened, still patterned",
               (1.2, th_ndom[iT12]), (1.135, 4.4), fontsize=7.8, color=WARM,
               arrowprops=dict(arrowstyle="->", color=WARM, lw=0.8))
    a2 = a.twinx()
    a2.plot(T_vals, th_vvar, color=TEAL, lw=1.8, ls="--", marker="s", ms=3.5,
            zorder=2, label="v_var")
    a2.axhline(PATTERN_FLOOR, ls=":", color="#7a8582", lw=1.0)
    a2.set_ylabel("v_var (amplitude)", color=TEAL)
    a2.tick_params(axis="y", colors=TEAL)
    a2.set_ylim(0, max(th_vvar) * 1.25)
    for sp in ("top",):
        a.spines[sp].set_visible(False); a2.spines[sp].set_visible(False)
    a.grid(True, color=GRID, alpha=0.5, lw=0.6)
    a2.annotate("v_var stays above floor → graded, not collapsed", (1.02, 0),
                xytext=(1.02, 0.12), textcoords=("data", "axes fraction"),
                fontsize=7.2, color=TEAL)

    # ── bottom row: final-field "money shots" across the boundary ──────────────
    # pick representative diffusion points + the thermal-graded field.
    def _closest(d, target):
        return d[min(d, key=lambda r: abs(r - target))]

    shots = [
        ("Du = Dv  (control)\nratio 1.0 · uniform", ctrl_field, UNIFORM),
        ("Du/Dv ≈ 1.33\nsub-threshold", _closest(sw_field, 0.16 / 0.12), UNIFORM),
        ("Du/Dv = 2.0\ncanonical regime", _closest(sw_field, 2.0), TEAL),
        ("Du/Dv = 4.0\nfine labyrinth", _closest(sw_field, 4.0), TEAL),
        ("T = 1.2 (Ea 0.15)\nthermal-graded", _closest(th_field, 1.2), WARM),
    ]
    # shared color scale across snapshots for honest comparison
    vmax = max(float(f.max()) for _, f, _ in shots)
    im = None
    for j, (label, fld, col) in enumerate(shots):
        a = fig.add_subplot(bot[0, j])
        im = a.imshow(fld, cmap=FIELD_CMAP, vmin=0.0, vmax=vmax, interpolation="nearest")
        a.set_xticks([]); a.set_yticks([])
        for sp in a.spines.values():
            sp.set_edgecolor(col); sp.set_linewidth(2.0)
        a.set_title(label, color=col, fontsize=8.6, pad=4)
    # one shared thin colorbar under the filmstrip
    cax = fig.add_axes([0.30, 0.028, 0.40, 0.015])
    cb = fig.colorbar(im, cax=cax, orientation="horizontal")
    cb.set_label("inhibitor concentration  v", fontsize=8)
    cb.ax.tick_params(labelsize=7)

    fig.text(0.06, 0.47, "final inhibitor field  v  (128×128, 8000 internal steps) — the boundary, uniform → patterned → coarsened",
             fontsize=9.5, color=INK, style="italic")

    fig.suptitle("The molecular interface, spatialized — the response the contract demands",
                 fontsize=14, color=INK, y=0.965, weight="bold")
    fig.text(0.5, 0.925,
             "Gray-Scott chemical channel: differential diffusion is the CAUSE of structure; "
             "a temperature parameter grades it. Every curve measured off the real compiled executable.",
             ha="center", fontsize=9.5, color="#3a4744")

    fig.savefig(VIZ / "molecular-interfaces-response.svg", format="svg")
    fig.savefig(VIZ / "molecular-interfaces-response.png", format="png")
    plt.close(fig)
    return head


if __name__ == "__main__":
    h = render()
    print(json.dumps(h, indent=2))
    print("\nwrote", VIZ / "molecular-interfaces-response.svg")
