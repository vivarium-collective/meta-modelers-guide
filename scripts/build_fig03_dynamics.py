#!/usr/bin/env python
"""Render Fig 3's time-series demonstration: the environment drives the interface ports.

Fig 3b's principle is the minimal cellular interface — a BOUNDED cell senses its
environmental drivers and exposes typed interface ports (uptake, growth, viability…).
This RUNS the runnable composite (meta_modelers_guide.composites.fig03-runnable): a
single cell (CellularInterfaceHandler) sitting in an environment that supplies a
chemical concentration and holds a thermal driver ABOVE the cell's optimum (45 °C,
optimum 37 °C). Over the run the environment's drivers DRIVE the interface ports:

  * chemical supply       — the external concentration the cell senses;
  * uptake (chemical flux) — nutrient taken up per step (Monod), written to the port;
  * growth_rate + shape    — the cell grows on the supply, accreting volume;
  * viability              — DECLINES by first-order Arrhenius thermal death because
                             the temperature is above tolerance.

It writes a four-panel time-series PNG to the fig-03 study visualizations and asserts
the load-bearing claims: chemical supply drives uptake & growth, and the elevated
temperature drives viability strictly down. Re-run whenever the fig03b handler or the
runnable composite change.

    python scripts/build_fig03_dynamics.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core

ROOT = Path(__file__).resolve().parent.parent
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig03-runnable.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-03" / "visualizations" / "fig03-dynamics.png"

TEMP_OPT = 37.0  # matches cell.config.temp_opt in the composite

# palette (matches the study figures' teal / accent family)
C_CHEM, C_UPTAKE, C_GROWTH, C_TEMP, C_VIAB = "#0b7a75", "#b4531f", "#1c7a77", "#c2410c", "#4b5bd6"


def _run():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def main() -> None:
    rows = _run()
    t = [float(r["time"]) for r in rows]
    chem = [float(r["chemical_ext"]) for r in rows]
    temp = [float(r["thermal_ext"]) for r in rows]
    # chemical_flux is written with set-semantics (holds the instantaneous uptake
    # flux), negative = net uptake; plot the magnitude taken up per step.
    uptake = [-float(r["chemical_flux"]) for r in rows]
    growth = [float(r["growth_rate"]) for r in rows]
    shape = [float(r["shape"]) for r in rows]
    viab = [float(r["viability"]) for r in rows]

    # ── load-bearing claims (drivers → ports) ──────────────────────────────────
    assert uptake[-1] > 0.0, "chemical supply should drive net uptake at the port"
    assert growth[-1] > 0.0, "chemical supply should drive Monod growth"
    assert shape[-1] > shape[0], "the cell should accrete volume under supply"
    assert temp[-1] > TEMP_OPT, "the thermal driver is held above the cell's optimum"
    assert viab[-1] < viab[0], "elevated temperature should drive viability down (Arrhenius death)"
    for a, b in zip(viab, viab[1:]):
        assert b <= a + 1e-9, "viability should fall monotonically above optimum"

    # ── figure ──────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
    fig.suptitle("Fig 3 — the environment senses → the cell's interface ports respond",
                 fontsize=15, fontweight="bold")
    fig.text(0.5, 0.925,
             "A bounded cell senses its environmental drivers (chemical supply, "
             "temperature) and exposes typed interface ports (uptake, growth, viability).",
             ha="center", fontsize=10, color="#444")

    # top-left: chemical supply driver + uptake port response (twin axes)
    ax = axes[0][0]
    ax.plot(t, chem, color=C_CHEM, lw=2.4, marker="o", ms=3, label="chemical supply (driver)")
    ax.set_ylabel("external concentration", color=C_CHEM)
    ax.tick_params(axis="y", labelcolor=C_CHEM)
    ax.set_ylim(0, max(chem) * 1.3 + 0.1)
    ax.set_title("Chemical driver → uptake port  (Monod)", fontsize=11)
    ax.grid(alpha=0.25)
    axb = ax.twinx()
    axb.plot(t, uptake, color=C_UPTAKE, lw=2.4, marker="s", ms=3, label="uptake flux (port)")
    axb.set_ylabel("uptake flux / step", color=C_UPTAKE)
    axb.tick_params(axis="y", labelcolor=C_UPTAKE)
    axb.set_ylim(0, max(uptake) * 1.3 + 0.1)
    lines = ax.get_lines() + axb.get_lines()
    ax.legend(lines, [ln.get_label() for ln in lines], fontsize=8, loc="lower right")

    # top-right: growth_rate port
    ax = axes[0][1]
    ax.plot(t, growth, color=C_GROWTH, lw=2.4, marker="o", ms=3)
    ax.set_title("Growth-rate port  (driven by supply)", fontsize=11)
    ax.set_ylabel("growth rate")
    ax.set_ylim(0, max(growth) * 1.4 + 0.05)
    ax.grid(alpha=0.25)

    # bottom-left: thermal driver + viability port (twin axes)
    ax = axes[1][0]
    ax.plot(t, temp, color=C_TEMP, lw=2.4, marker="o", ms=3, label="temperature (driver)")
    ax.axhline(TEMP_OPT, color="#999", ls="--", lw=1, label=f"optimum ({TEMP_OPT:.0f} °C)")
    ax.set_ylabel("temperature (°C)", color=C_TEMP)
    ax.tick_params(axis="y", labelcolor=C_TEMP)
    ax.set_ylim(TEMP_OPT - 3, max(temp) + 3)
    ax.set_xlabel("time (min)")
    ax.set_title("Thermal driver above optimum → viability falls  (Arrhenius death)", fontsize=11)
    ax.grid(alpha=0.25)
    axb = ax.twinx()
    axb.plot(t, viab, color=C_VIAB, lw=2.4, marker="s", ms=3, label="viability (port)")
    axb.set_ylabel("viability", color=C_VIAB)
    axb.tick_params(axis="y", labelcolor=C_VIAB)
    axb.set_ylim(0, 1.05)
    lines = ax.get_lines() + axb.get_lines()
    ax.legend(lines, [ln.get_label() for ln in lines], fontsize=8, loc="center right")

    # bottom-right: accreted shape/volume port
    ax = axes[1][1]
    ax.plot(t, shape, color=C_GROWTH, lw=2.4, marker="o", ms=3)
    ax.set_title("Shape port  (volume accreted on growth)", fontsize=11)
    ax.set_ylabel("cell volume")
    ax.set_xlabel("time (min)")
    ax.grid(alpha=0.25)

    fig.tight_layout(rect=(0, 0, 1, 0.9))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150)
    plt.close(fig)
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  chemical supply  {chem[0]:.4f} → {chem[-1]:.4f}  (driver)")
    print(f"  uptake / step    {uptake[1]:.4f} → {uptake[-1]:.4f}  (port)")
    print(f"  growth_rate      {growth[0]:.4f} → {growth[-1]:.4f}  (port)")
    print(f"  shape (volume)   {shape[0]:.4f} → {shape[-1]:.4f}  (port)")
    print(f"  temperature      {temp[0]:.4f} → {temp[-1]:.4f} °C  (driver, opt {TEMP_OPT:.0f})")
    print(f"  viability        {viab[0]:.4f} → {viab[-1]:.4f}  (port, Arrhenius death)")


if __name__ == "__main__":
    main()
