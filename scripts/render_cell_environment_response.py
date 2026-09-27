#!/usr/bin/env python
"""The *cell-environment-coupling* study's "response of the contract" figure.

The Fig 5 cell-environment contract demands a cell whose metabolism, driven by the
substrate it senses in a shared field, grows it — and whose interface exposes the
same coarse observables no matter which internal mechanism realizes them. The
compiled executable ``single-cell-in-a-field`` realizes this with a real
dynamic-FBA metabolism (COBRApy ``e_coli_core``) solved at the cell's own CPM
footprint, coupled to a spatio-flux diffusion field; two ablation arms expose the
contract's demanded relations:

  * ``-o2uncapped`` — removes the respiratory-capacity (O2) cap → NO acetate
    overflow (the overflow phenotype is *caused* by the finite-O2 constraint).
  * ``-mm``        — swaps the dFBA metabolism for a Michaelis-Menten surrogate
    behind the SAME interface ports → the coarse observables still track (law 4).

Every trajectory here is measured off the running compiled executable; the fourth
panel recovers the underlying FBA law the dFBA cell rides on, straight from the
real ``e_coli_core`` LP (growth vs glucose-uptake bound; an essential-gene
knockout collapses it) — the deterministic cobra optimum ~0.87 hr^-1.

Outputs into the study's visualizations/:
  cell-environment-coupling-response.svg / .png
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "meta_modelers_guide" / "composites"
VIZ = ROOT / "workspace" / "studies" / "cell-environment-coupling" / "visualizations"

INK, TEAL, TEAL_L, WARM, WARM_L, GRID = "#16211f", "#0d6e6b", "#3f9e99", "#a5620f", "#c98a3a", "#c9d3d1"
TOTAL = 20.0


def _run(stem, total_time=TOTAL):
    """Run the pre-compiled executable arm; return its emitter time-series dict."""
    st = json.loads((COMPOSITES / f"{stem}.composite.json").read_text())
    st = st["state"]
    core = build_core()
    sim = Composite({"state": st}, core=core)
    sim.run(total_time)
    rows = gather_emitter_results(sim)[("emitter",)]
    keys = [k for k in rows[0] if k not in ("time", "position")]

    def _scalar(x):
        # field arrays (glucose, acetate) reduce to a field-wide total; scalars pass.
        a = np.asarray(x, dtype=float)
        return float(a.sum()) if a.ndim else float(a)

    out = {k: np.array([_scalar(r[k]) for r in rows]) for k in keys}
    out["time"] = np.array([float(r.get("time", i)) for i, r in enumerate(rows)])
    return out


def _fba_law():
    """The metabolism contract's characteristic law, straight off the real
    e_coli_core LP: growth (biomass objective) vs glucose-uptake bound, and the
    same sweep with an essential TCA reaction (ICDHyr) knocked out."""
    from cobra.io import load_model
    base = load_model("textbook")            # e_coli_core, 95 reactions
    base.reactions.EX_o2_e.lower_bound = -18.0   # finite respiratory capacity
    uptakes = np.linspace(0.0, 18.0, 19)
    wt, ko, ac = [], [], []
    for u in uptakes:
        m = base.copy()
        m.reactions.EX_glc__D_e.lower_bound = -float(u)
        sol = m.optimize()
        wt.append(sol.objective_value or 0.0)
        ac.append(max(0.0, float(sol.fluxes["EX_ac_e"])))
        mk = base.copy()
        mk.reactions.EX_glc__D_e.lower_bound = -float(u)
        mk.reactions.ICDHyr.knock_out()
        solk = mk.optimize()
        ko.append(solk.objective_value or 0.0)
    return uptakes, np.array(wt), np.array(ko), np.array(ac)


def render():
    VIZ.mkdir(parents=True, exist_ok=True)
    head = {}
    dfba = _run("single-cell-in-a-field")
    unc = _run("single-cell-in-a-field-o2uncapped")
    mm = _run("single-cell-in-a-field-mm")

    head["biomass_dfba"] = round(float(dfba["biomass"][-1]), 3)
    head["volume_dfba"] = round(float(dfba["volume"][-1]), 1)
    head["acetate_capped"] = round(float(dfba["acetate"][-1]), 2)
    head["acetate_uncapped"] = round(float(unc["acetate"][-1]), 2)
    # dFBA vs MM interface agreement on biomass at the final tick
    bd, bm = float(dfba["biomass"][-1]), float(mm["biomass"][-1])
    head["biomass_mm"] = round(bm, 3)
    head["interface_biomass_divergence_pct"] = round(abs(bm - bd) / max(bd, 1e-9) * 100, 1)

    up, wt, ko, ac = _fba_law()
    # headline: the deterministic optimum at the operating uptake (10)
    i10 = int(np.argmin(np.abs(up - 10.0)))
    head["fba_growth_at_uptake10"] = round(float(wt[i10]), 4)
    head["fba_growth_knockout"] = round(float(ko[i10]), 4)
    head["acetate_overflow_onset_uptake"] = round(float(up[np.argmax(ac > 1e-6)]), 2)

    plt.rcParams.update({"font.size": 9, "axes.edgecolor": "#3a4744",
                         "axes.labelcolor": INK, "text.color": INK,
                         "xtick.color": INK, "ytick.color": INK})
    fig, ax = plt.subplots(2, 2, figsize=(11.6, 8.0), dpi=120)

    def _clean(a):
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
        a.grid(True, color=GRID, alpha=0.5, lw=0.6)

    # (A) metabolism drives growth — biomass + CPM volume
    a = ax[0, 0]
    a.plot(dfba["time"], dfba["biomass"], color=TEAL, lw=2.6, label="biomass (dFBA)")
    a.set_xlabel("time (ticks)"); a.set_ylabel("biomass", color=TEAL)
    a.tick_params(axis="y", labelcolor=TEAL)
    a2 = a.twinx()
    a2.plot(dfba["time"], dfba["volume"], color=WARM, lw=2.2, ls="--", label="CPM volume")
    a2.set_ylabel("CPM volume (px)", color=WARM); a2.tick_params(axis="y", labelcolor=WARM)
    a2.spines["top"].set_visible(False)
    a.set_title(f"metabolism drives growth  (biomass {head['biomass_dfba']}, "
                f"volume {head['volume_dfba']} px)", color=INK, fontsize=10)
    _clean(a)

    # (B) O2 cap forces acetate overflow — control vs ablation
    a = ax[0, 1]
    a.plot(dfba["time"], dfba["acetate"], color=TEAL, lw=2.6, label="O$_2$ capped (overflow)")
    a.plot(unc["time"], unc["acetate"], color=WARM, lw=2.2, ls="--", label="O$_2$ uncapped (control)")
    a.annotate(f"acetate {head['acetate_capped']}\nvs {head['acetate_uncapped']}",
               (dfba["time"][-1] * 0.55, dfba["acetate"][-1] * 0.5), fontsize=8.5, color="#3a4744")
    a.set_title("O$_2$ cap forces acetate overflow", color=INK, fontsize=10)
    a.set_xlabel("time (ticks)"); a.set_ylabel("field-wide acetate")
    a.legend(frameon=False, fontsize=8.5, loc="upper left")
    _clean(a)

    # (C) one interface, two mechanisms — dFBA vs MM surrogate
    a = ax[1, 0]
    a.plot(dfba["time"], dfba["biomass"], color=TEAL, lw=2.6, label="dFBA (real e_coli_core)")
    a.plot(mm["time"], mm["biomass"], color=WARM, lw=2.2, ls="--", label="Michaelis-Menten surrogate")
    a.annotate(f"agree to {head['interface_biomass_divergence_pct']}%\non biomass",
               (dfba["time"][-1] * 0.5, bd * 0.35), fontsize=8.5, color="#3a4744")
    a.set_title("one interface, two mechanisms (law 4)", color=INK, fontsize=10)
    a.set_xlabel("time (ticks)"); a.set_ylabel("biomass")
    a.legend(frameon=False, fontsize=8.5, loc="lower right")
    _clean(a)

    # (D) the underlying FBA law — growth vs glucose uptake, + knockout
    a = ax[1, 1]
    a.plot(up, wt, color=TEAL, lw=2.6, marker="o", ms=3.5, label="wild-type")
    a.plot(up, ko, color="#9e2b1f", lw=2.2, ls="--", label="ICDHyr knockout")
    a.axvline(10.0, ls=":", color="#7a8582", lw=1)
    a.annotate(f"mu = {head['fba_growth_at_uptake10']:.3f} hr$^{{-1}}$\n@ uptake 10",
               (10.0, head["fba_growth_at_uptake10"]), (2.5, head["fba_growth_at_uptake10"] * 0.9),
               fontsize=8.5, color="#3a4744")
    a.annotate("ICDHyr knockout -> 0\n(essential TCA step)", (3.0, 0.06), fontsize=8.5, color="#9e2b1f")
    a.set_title("the FBA law it rides on  (real e_coli_core LP)", color=INK, fontsize=10)
    a.set_xlabel("glucose-uptake bound (mmol·gDW$^{-1}$·h$^{-1}$)")
    a.set_ylabel("growth rate  mu (hr$^{-1}$)")
    a.legend(frameon=False, fontsize=8.5, loc="lower right")
    _clean(a)

    fig.suptitle("Cell-environment coupling, exercised — metabolism drives growth on the field it senses",
                 fontsize=13, color=INK, y=0.995, weight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(VIZ / "cell-environment-coupling-response.svg", format="svg")
    fig.savefig(VIZ / "cell-environment-coupling-response.png", format="png")
    plt.close(fig)
    return head


if __name__ == "__main__":
    h = render()
    print(json.dumps(h, indent=2))
    print("\nwrote", VIZ / "cell-environment-coupling-response.svg")
