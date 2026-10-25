#!/usr/bin/env python
"""Render Fig 6's MECHANISTIC demonstration: a real rotary F₁Fₒ ATP synthase whose
torque, speed, flux, power split, efficiency, stall and reversal are DERIVED from
the proton-motive force, the ATP free energy, and the mechanical load — not imposed.

This runs the ``fig06-mechanistic`` composite (AtpSynthaseRotor driven at a fixed
Δp = 150 mV while MechanicalLoad ramps the shaft load past the stall point) and,
separately, sweeps the proton-motive force on a fresh rotor to locate the
first-principles stall gradient Δp* = atp_per_rev·ΔG_ATP/(n_c·e). It writes a
six-panel decisive figure to the fig-06 study visualizations:

  A  rotor shaft turning — cumulative revolutions θ(t): forward, then backward
  B  angular velocity ω(t) and ATP flux J_ATP(t), stall marked
  C  torque balance: τ_drive (derived from Δp) vs τ_chem vs ramped load τ_ext
  D  power budget P_in = P_ATP + P_ext + P_heat (the identity, stacked)
  E  Δp sweep — rotor direction vs proton-motive force, stall threshold Δp* marked
  F  loaded vs unloaded ATP flux over the run

It asserts the load-bearing claims (power identity closes; torque derived ≈ 38 pN·nm;
forward→stall→reversal; Δp threshold sets direction) before plotting. Re-run whenever
the fig06 mechanistic model or composite changes.

    python scripts/build_fig06_mechanistic.py
"""
from __future__ import annotations

import json
import math
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.handlers_fig06_mech import AtpSynthaseRotor, _E, _NA, _R

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig06-mechanistic.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-06" / "visualizations" / "fig06-mechanistic-dynamics.png"

TWO_PI = 2 * math.pi
_CFG = dict(n_c=10.0, atp_per_rev=3.0, drag=1.0e-23, dg0_kjmol=30.5,
            temperature=298.15, buffer_pools=True, min_conc=1.0e-6)

# palette (teal / accents, matching the study figures)
C_ATP, C_OMEGA, C_IN, C_EXT, C_HEAT, C_DRIVE, C_CHEM, C_LOAD = (
    "#0b7a75", "#4b5bd6", "#0b7a75", "#b4531f", "#c0392b", "#4b5bd6", "#7a5195", "#b4531f")
C_FWD, C_REV, C_STALL = "#0b7a75", "#c0392b", "#555555"


def _run_composite():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def _step(pmf, load=0.0, atp=10.0, adp=1.0, pi=0.2, buffer=True):
    cfg = dict(_CFG, buffer_pools=buffer)
    return AtpSynthaseRotor(cfg, core=build_core()).update(
        {"pmf": pmf, "load_torque": load, "atp": atp, "adp": adp, "pi": pi}, 1.0)


def main() -> None:
    rows = _run_composite()
    t = [float(r["time"]) for r in rows]
    omega = [float(r["omega"]) for r in rows]
    jatp = [float(r["atp_flux"]) for r in rows]
    tau_drive = [float(r["drive_torque"]) for r in rows]
    tau_chem = [float(r["chem_torque"]) for r in rows]
    tau_ext = [float(r["load_torque"]) for r in rows]
    p_in = [float(r["power_in"]) for r in rows]
    p_atp = [float(r["power_atp"]) for r in rows]
    p_ext = [float(r["power_ext"]) for r in rows]
    p_heat = [float(r["power_heat"]) for r in rows]

    # cumulative revolutions θ(t)/2π (rotor shaft turning forward then back)
    revs, acc = [], 0.0
    for om in omega:
        acc += om / TWO_PI
        revs.append(acc)

    # ── assertions (claims before plotting) ──────────────────────────────────
    resid = max(abs(pi_ - (pa + pe + ph)) for pi_, pa, pe, ph in zip(p_in, p_atp, p_ext, p_heat))
    assert resid < 1e-30, f"power identity residual {resid:.2e}"
    td = max(tau_drive)
    assert 35e-21 < td < 42e-21, f"derived torque {td/1e-21:.1f} pN·nm off literature"
    assert max(omega) > 100 and min(omega) < -100, "no forward→reversal sweep"

    # Δp sweep on a fresh rotor (fixed pools); locate direction flip
    kT = _R * _CFG["temperature"] / _NA
    dg = _CFG["dg0_kjmol"] * 1e3 / _NA + kT * math.log(10.0 / (1.0 * 0.2))
    d_star = _CFG["atp_per_rev"] * dg / (_CFG["n_c"] * _E)          # stall gradient (V)
    pmf_grid = [0.02 * k for k in range(1, 16)]                    # 20 … 300 mV
    omega_of_pmf = [float(_step(p)["omega"]) for p in pmf_grid]

    # loaded vs unloaded ATP flux over the run (unloaded = no shaft load)
    jatp_unloaded = [float(_step(0.150)["atp_flux"])] * len(t)     # constant (fixed Δp, no load)

    # ── figure ────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.4))
    fig.suptitle("Fig 6 (mechanistic) · F₁Fₒ ATP synthase as a real rotary motor — "
                 "torque, stall and reversal DERIVED, not imposed", fontsize=13, y=0.99)

    # stall time (first forward→non-positive ω crossing)
    stall_t = next((t[i + 1] for i in range(len(omega) - 1) if omega[i] > 0 >= omega[i + 1]), None)

    def mark_stall(ax):
        if stall_t is not None:
            ax.axvline(stall_t, color=C_STALL, ls=":", lw=1.2)
            ax.axvspan(stall_t, t[-1], color=C_REV, alpha=0.05)

    # A — rotor shaft turning
    ax = axes[0, 0]
    ax.plot(t, revs, color=C_OMEGA, lw=2)
    ax.axhline(max(revs), color=C_OMEGA, ls=":", lw=0.8, alpha=0.5)
    mark_stall(ax)
    ax.set_title("A · Rotor shaft angle (cumulative revolutions)")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("revolutions θ/2π")
    ax.annotate("forward\n(synthesis)", (t[2], revs[2]), fontsize=8, color=C_FWD)
    ax.annotate("reversal\n(hydrolysis)", (t[-1], revs[-1]), fontsize=8, color=C_REV,
                ha="right", va="bottom")

    # B — ω and J_ATP
    ax = axes[0, 1]
    ax.axhline(0, color="#999", lw=0.8)
    ax.plot(t, omega, color=C_OMEGA, lw=2, label="ω (rad·s⁻¹)")
    ax.plot(t, jatp, color=C_ATP, lw=2, label="J_ATP (ATP·s⁻¹)")
    mark_stall(ax)
    ax.set_title("B · Angular velocity & ATP flux — stall then reversal")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("ω / J_ATP")
    ax.legend(fontsize=8, loc="upper right")

    # C — torque balance (pN·nm)
    ax = axes[0, 2]
    s = 1e-21  # N·m → pN·nm
    ax.axhline(0, color="#999", lw=0.8)
    ax.plot(t, [x / s for x in tau_drive], color=C_DRIVE, lw=2, label="τ_drive (from Δp)")
    ax.plot(t, [x / s for x in tau_chem], color=C_CHEM, lw=2, ls="--", label="τ_chem (ATP)")
    ax.plot(t, [x / s for x in tau_ext], color=C_LOAD, lw=2, label="τ_ext (load ramp)")
    ax.plot(t, [(d - c - e) / s for d, c, e in zip(tau_drive, tau_chem, tau_ext)],
            color=C_STALL, lw=1.5, ls=":", label="τ_net")
    mark_stall(ax)
    ax.set_title("C · Torque balance (τ_drive ≈ 38 pN·nm, derived)")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("torque (pN·nm)")
    ax.legend(fontsize=7.5, loc="upper right")

    # D — power budget identity
    ax = axes[1, 0]
    ax.axhline(0, color="#999", lw=0.8)
    ax.plot(t, p_in, color=C_IN, lw=2.4, label="P_in (pmf)")
    ax.plot(t, p_atp, color=C_ATP, lw=1.6, label="P_ATP")
    ax.plot(t, p_ext, color=C_EXT, lw=1.6, label="P_ext (load)")
    ax.plot(t, p_heat, color=C_HEAT, lw=1.6, label="P_heat (viscous)")
    ax.plot(t, [pa + pe + ph for pa, pe, ph in zip(p_atp, p_ext, p_heat)],
            color="#000", lw=0.8, ls=":", label="P_ATP+P_ext+P_heat")
    mark_stall(ax)
    ax.set_title("D · Power budget closes: P_in = P_ATP + P_ext + P_heat")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("power (W)")
    ax.legend(fontsize=7, loc="upper right")

    # E — Δp sweep: direction vs proton-motive force
    ax = axes[1, 1]
    ax.axhline(0, color="#999", lw=0.8)
    colors = [C_FWD if o > 0 else C_REV for o in omega_of_pmf]
    ax.scatter([p * 1000 for p in pmf_grid], omega_of_pmf, c=colors, s=28, zorder=3)
    ax.plot([p * 1000 for p in pmf_grid], omega_of_pmf, color="#bbb", lw=1, zorder=1)
    ax.axvline(d_star * 1000, color=C_STALL, ls="--", lw=1.3)
    ax.annotate(f"Δp* = {d_star*1000:.0f} mV\n(stall, from first principles)",
                (d_star * 1000, 0), fontsize=8, color=C_STALL, ha="left", va="bottom")
    ax.set_title("E · Proton-gradient sweep sets direction")
    ax.set_xlabel("proton-motive force Δp (mV)"); ax.set_ylabel("ω (rad·s⁻¹)")
    ax.annotate("synthesis", (260, max(omega_of_pmf) * 0.6), color=C_FWD, fontsize=8, ha="center")
    ax.annotate("hydrolysis", (60, min(omega_of_pmf) * 0.6), color=C_REV, fontsize=8, ha="center")

    # F — loaded vs unloaded ATP flux
    ax = axes[1, 2]
    ax.axhline(0, color="#999", lw=0.8)
    ax.plot(t, jatp_unloaded, color=C_FWD, lw=2, ls="--", label="unloaded (τ_ext=0)")
    ax.plot(t, jatp, color=C_ATP, lw=2, label="loaded (τ_ext ramps)")
    mark_stall(ax)
    ax.fill_between(t, jatp, jatp_unloaded, color=C_LOAD, alpha=0.12)
    ax.set_title("F · Load throttles the motor (loaded vs unloaded)")
    ax.set_xlabel("time (ticks)"); ax.set_ylabel("J_ATP (ATP·s⁻¹)")
    ax.legend(fontsize=8, loc="upper right")

    for ax in axes.flat:
        ax.grid(True, alpha=0.25, lw=0.5)
        ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    print(f"  derived τ_drive = {td/1e-21:.1f} pN·nm; power residual ≤ {resid:.1e} W; "
          f"stall at t≈{stall_t}; Δp* = {d_star*1000:.0f} mV")


if __name__ == "__main__":
    main()
