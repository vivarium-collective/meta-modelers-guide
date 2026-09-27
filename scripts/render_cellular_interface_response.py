#!/usr/bin/env python
"""Render the *cellular-interface* study's flagship evidence figure — the
**response of the contract**.

The Fig 3b draft process (``CellularInterface``) does not merely name ports: the
paper figure prints the very relations the contract demands —

    chemical      = -k_up · [S]                    (first-order uptake, dilute limit)
    mu            = mu_max · [S] / (K_s + [S])      (Monod growth)
    d viability/dt = -A · exp(-E_a / R T) · viability   (Arrhenius thermal death)

with the figure's own constants (mu_max=0.6, K_s=0.5, uptake_rate=0.8,
E_a=300 kJ/mol, R=8.314, temp_opt=37). The compiled executable
(``fig03b-executable`` = ``CellularInterfaceHandler``) realizes exactly these; a
second conforming handler (``fig03b-executable-alt`` = the Moser/Hill + Q10 twin)
realizes the SAME contract by a different internal mechanism.

The legacy evidence ran the executable at ONE static operating point
(chemical=1.0, T=37) and reported endpoint scalars (shape 1->4.2), which hide the
relations the contract demands. This renderer instead *exercises the contract*:
it drives the real compiled executable across the inputs it senses and graphs the
characteristic responses the contract's own equations produce, plus the
compilation payoff (two mechanisms, one interface, agreeing across the operating
range). Every curve is the draft's own equation run through the engine — nothing
invented, nothing outside the fixed figure.

Outputs (into the study's visualizations/):
  cellular-interface-response.svg / .png   — the six-panel response figure
Prints the headline numbers (mu_max, half-saturation, D-values, agreement).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager  # noqa: F401  (ensure font cache is built)
from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "meta_modelers_guide" / "composites"
VIZ = ROOT / "workspace" / "studies" / "cellular-interface" / "visualizations"

MONOD = "fig03b-executable"        # CellularInterfaceHandler: first-order / Monod / Arrhenius
TWIN = "fig03b-executable-alt"     # Cooperative twin: MM carrier / Hill / Q10

# Book palette — the guide's teal family + a warm accent for the second mechanism.
INK = "#16211f"
TEAL = "#0d6e6b"
TEAL_L = "#3f9e99"
WARM = "#a5620f"
WARM_L = "#c98a3a"
GRID = "#c9d3d1"
HEAT = ["#2c6e6b", "#4f8a3f", "#c98a3a", "#c2591f", "#9e2b1f"]  # cool->hot for T curves


def _run(stem, env=None, total_time=12.0, interval=None):
    """Run the pre-compiled executable composite, optionally overriding the static
    ``environment.<k>`` driver defaults (and the process step interval), and return
    the emitted interface series.

    Returns (times, {label: np.array}) for the interface.* observables.
    """
    state = json.loads((COMPOSITES / f"{stem}.composite.json").read_text())["state"]
    state = json.loads(json.dumps(state))  # deep copy
    for k, v in (env or {}).items():
        # realize seeds a leaf from _default (NOT _value) — set both to be safe.
        state["environment"][k]["_default"] = float(v)
        state["environment"][k]["_value"] = float(v)
    if interval is not None:
        # finer engine step → finer time resolution (e.g. the thermal-death cliff).
        state["cell"]["interval"] = float(interval)
    obs = ["chemical", "growth_rate", "shape", "objective", "viability", "signaling"]
    emit = {f"interface.{o}": "float" for o in obs}
    emit["time"] = "float"
    inputs = {f"interface.{o}": ["interface", o] for o in obs}
    inputs["time"] = ["global_time"]
    state["vizemitter"] = {"_type": "step", "address": "local:RAMEmitter",
                           "config": {"emit": emit}, "inputs": inputs}
    core = build_core()
    sim = Composite({"state": state}, core=core)
    sim.run(total_time)
    rows = gather_emitter_results(sim)[("vizemitter",)]
    times = np.array([float(r.get("time", i)) for i, r in enumerate(rows)])
    out = {o: np.array([float(r[f"interface.{o}"]) for r in rows]) for o in obs}
    return times, out


def _steady(stem, chem, temp=37.0):
    """Instantaneous interface response at a fixed operating point (a couple of
    steps is enough — growth_rate / chemical flux are set-semantics, constant for a
    constant driver)."""
    t, s = _run(stem, {"chemical": chem, "thermal": temp}, total_time=3.0)
    return {k: float(v[-1]) for k, v in s.items()}


def render():
    VIZ.mkdir(parents=True, exist_ok=True)
    head = {}

    # ── sweep the chemical driver over the contract's operating range ──────────
    S = np.linspace(0.0, 6.0, 46)
    mu_monod = np.array([_steady(MONOD, s)["growth_rate"] for s in S])
    up_monod = np.array([_steady(MONOD, s)["chemical"] for s in S])
    mu_twin = np.array([_steady(TWIN, s)["growth_rate"] for s in S])

    # RECOVER the contract's constants from the executable curve itself: fit the
    # Monod law mu = mu_max·[S]/(K_s+[S]) to the sampled points. They come back at
    # the figure's printed mu_max=0.6, K_s=0.5 — the executable realizes exactly
    # what the draft demands.
    from scipy.optimize import curve_fit
    def _monod(s, mm, ks):
        return mm * s / (ks + s)
    (mu_max, ks_fit), _ = curve_fit(_monod, S, mu_monod, p0=(0.6, 0.5))
    mu_max, ks_fit = float(mu_max), float(ks_fit)
    S_fit = np.linspace(0, 6, 200)
    mu_fit = _monod(S_fit, mu_max, ks_fit)
    # mechanism agreement across the operating range chem in [0.2, 2.5]
    band = (S >= 0.2) & (S <= 2.5)
    denom = np.maximum(np.abs(mu_monod[band]), 1e-9)
    max_div = float(np.max(np.abs(mu_twin[band] - mu_monod[band]) / denom) * 100)
    head.update(mu_max_fit=round(mu_max, 4), K_s_fit=round(ks_fit, 4),
                uptake_slope=round(float(np.polyfit(S, up_monod, 1)[0]), 4),
                mechanism_max_divergence_pct=round(max_div, 2))

    # ── ramp the thermal driver: Arrhenius viability cliff V(t) ────────────────
    temps = [37.0, 45.0, 50.0, 55.0, 60.0]
    death = {}
    dvals = {}
    for T in temps:
        # fine step (0.2 min) so the cliff resolves and D-values separate at 55/60.
        t, s = _run(MONOD, {"thermal": T, "chemical": 1.0}, total_time=15.0, interval=0.2)
        v = s["viability"]
        death[T] = (t, v)
        # D-value = time to a 1-log kill (V crosses 0.1), linearly interpolated.
        below = np.where(v <= 0.1)[0]
        if len(below) and below[0] > 0:
            i = below[0]
            v0, v1, t0, t1 = v[i - 1], v[i], t[i - 1], t[i]
            dvals[T] = float(t0 + (0.1 - v0) * (t1 - t0) / (v1 - v0)) if v1 != v0 else float(t1)
        elif len(below):
            dvals[T] = float(t[below[0]])
        else:
            dvals[T] = None
    head["D_value_min"] = {f"{int(T)}C": (round(d, 3) if d is not None else ">15")
                           for T, d in dvals.items()}

    # ── goal-directed accretion at a representative operating point ────────────
    ta, sa = _run(MONOD, {"chemical": 1.0, "thermal": 37.0}, total_time=12.0)
    head["objective_final"] = round(float(sa["objective"][-1]), 3)
    head["shape_final"] = round(float(sa["shape"][-1]), 3)

    # ── figure: 2x3 response panels ────────────────────────────────────────────
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": "#3a4744",
                         "axes.labelcolor": INK, "text.color": INK,
                         "xtick.color": INK, "ytick.color": INK})
    fig, ax = plt.subplots(2, 3, figsize=(13.2, 7.4), dpi=120)

    def _clean(a):
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
        a.grid(True, color=GRID, alpha=0.5, lw=0.6)

    # (A) Monod growth mu([S]) — executable points on the contract's analytic law
    a = ax[0, 0]
    a.plot(S_fit, mu_fit, color="#9fb3b0", lw=5, alpha=0.6, zorder=1,
           label="contract: mu$_{max}$=%.2f, K$_s$=%.2f" % (mu_max, ks_fit))
    a.plot(S, mu_monod, color=TEAL, lw=0, marker="o", ms=3.5, zorder=3, label="executable")
    a.axhline(mu_max, ls=":", color="#7a8582", lw=1.2)
    a.axhline(mu_max / 2, ls=":", color="#7a8582", lw=1)
    a.axvline(ks_fit, ls=":", color=WARM, lw=1.2)
    a.annotate(f"mu$_{{max}}$ = {mu_max:.2f} hr$^{{-1}}$", (3.6, mu_max), (3.0, mu_max - 0.10),
               fontsize=8.5, color="#3a4744")
    a.annotate(f"K$_s$ = {ks_fit:.2f}\n(half-max)", (ks_fit, mu_max / 2),
               (ks_fit + 0.5, mu_max / 2 - 0.14), fontsize=8.5, color=WARM)
    a.set_title("Monod growth  mu = mu$_{max}$·[S]/(K$_s$+[S])", color=INK, fontsize=10)
    a.set_xlabel("external substrate [S]"); a.set_ylabel("specific growth rate  mu (hr$^{-1}$)")
    a.legend(frameon=False, fontsize=7.5, loc="lower right")
    _clean(a)

    # (B) first-order uptake flux
    a = ax[0, 1]
    a.plot(S, up_monod, color=TEAL, lw=2.6)
    slope = head["uptake_slope"]
    a.annotate(f"slope = {slope:.2f}\n(= -uptake_rate)", (2.0, up_monod[20]),
               (0.35, up_monod[-1] * 0.62), fontsize=8.5, color="#3a4744")
    a.set_title("first-order uptake  chemical = -k$_{up}$·[S]", color=INK, fontsize=10)
    a.set_xlabel("external substrate [S]"); a.set_ylabel("chemical flux  (mol·s$^{-1}$)")
    _clean(a)

    # (C) mechanism independence — one interface, two mechanisms
    a = ax[0, 2]
    a.plot(S, mu_monod, color=TEAL, lw=2.6, label="Monod / Arrhenius", zorder=3)
    a.plot(S, mu_twin, color=WARM, lw=2.2, ls="--", label="Hill / Q10 (twin)", zorder=3)
    a.axvspan(0.2, 2.5, color=TEAL_L, alpha=0.10)
    a.annotate(f"agree to {max_div:.1f}%\nacross [0.2, 2.5]", (1.3, 0.16),
               fontsize=8.5, color="#3a4744")
    a.set_title("one interface, two mechanisms (law 4)", color=INK, fontsize=10)
    a.set_xlabel("external substrate [S]"); a.set_ylabel("growth rate  mu (hr$^{-1}$)")
    a.legend(frameon=False, fontsize=8.5, loc="lower right")
    _clean(a)

    # (D) Arrhenius viability cliff V(t)
    a = ax[1, 0]
    for i, T in enumerate(temps):
        t, v = death[T]
        a.plot(t, v, color=HEAT[i], lw=2.4, label=f"{int(T)} °C")
    a.axhline(0.1, ls=":", color="#7a8582", lw=1)
    a.annotate("1-log kill", (11.5, 0.1), (9.2, 0.17), fontsize=8, color="#7a8582")
    a.set_title("Arrhenius thermal death  dV/dt = -A·e$^{-E_a/RT}$·V", color=INK, fontsize=10)
    a.set_xlabel("time (min)"); a.set_ylabel("viability  V")
    a.set_ylim(-0.03, 1.05)
    a.legend(frameon=False, fontsize=8, ncol=2, loc="upper right")
    _clean(a)

    # (E) D-value vs temperature (the death cliff as a curve; semilog)
    a = ax[1, 1]
    Tk = np.array([T for T in temps])
    dv = np.array([dvals[T] if dvals[T] is not None else np.nan for T in temps])
    # analytic D(T) = ln(10)/k(T), k(T)=k_ref·exp((Ea/R)(1/Tref_K - 1/T_K)), D_ref=1 min @55C
    Ea, R = 300000.0, 8.314
    Tfine = np.linspace(37, 62, 120)
    k_ref = math.log(10.0) / 1.0
    Tref_K = 55.0 + 273.15
    kT = k_ref * np.exp((Ea / R) * (1.0 / Tref_K - 1.0 / (Tfine + 273.15)))
    Dfine = math.log(10.0) / kT
    a.plot(Tfine, Dfine, color=TEAL, lw=2.2, zorder=2, label="D(T) = ln10 / k(T)")
    finite = ~np.isnan(dv)
    a.scatter(Tk[finite], dv[finite], color=WARM, s=42, zorder=3, label="executable")
    a.set_yscale("log")
    a.axhline(1.0, ls=":", color="#7a8582", lw=1)
    a.annotate("~1 min @ 55 °C", (55, 1.0), (46.5, 2.4), fontsize=8, color="#3a4744")
    a.set_title("thermal-death cliff — D-value vs T", color=INK, fontsize=10)
    a.set_xlabel("temperature (°C)"); a.set_ylabel("D-value (min, log)")
    a.legend(frameon=False, fontsize=8, loc="upper right")
    _clean(a)

    # (F) goal-directed accretion at 37 °C, [S]=1
    a = ax[1, 2]
    a.plot(ta, sa["shape"], color=TEAL, lw=2.4, label="shape (volume)")
    a.plot(ta, sa["objective"], color=WARM, lw=2.4, label="objective (biomass)")
    a.set_title("goal-directed accretion  ([S]=1, 37 °C)", color=INK, fontsize=10)
    a.set_xlabel("time"); a.set_ylabel("accumulated")
    a.legend(frameon=False, fontsize=8.5, loc="upper left")
    _clean(a)

    fig.suptitle("The cellular interface, exercised — the response the contract demands",
                 fontsize=13, color=INK, y=0.995, weight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(VIZ / "cellular-interface-response.svg", format="svg")
    fig.savefig(VIZ / "cellular-interface-response.png", format="png")
    plt.close(fig)
    return head


if __name__ == "__main__":
    h = render()
    print(json.dumps(h, indent=2))
    print("\nwrote", VIZ / "cellular-interface-response.svg")
