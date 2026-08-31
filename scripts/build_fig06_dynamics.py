#!/usr/bin/env python
"""Render Fig 6's time-series demonstration: a molecular transducer couples a
proton-motive force across four typed physical channels.

Fig 6b's principle is that a molecular mechanism is a process with typed physical
channels. This RUNS the runnable composite
(meta_modelers_guide.composites.fig06-runnable): the F₁Fₒ ATP synthase
(MolecularMechanismHandler) driven by a ProtonMotiveRamp that charges the
substrate/proton drive (chemical_in) linearly over the run — the fig06 analogue of
fig04's diffusing gradient. From the ONE coupled quantity (the proton flux) the
transducer produces four typed output channels, conserving matter/charge/
angular-momentum/energy:

  * chemical   — ATP synthesis flux J_ATP (ATP·s⁻¹), scales with the proton drive;
  * electrical — the proton current I = J_H·e carried across the PMF;
  * mechanical — the (near-constant) rotary torque on the Fₒ rotor (N·m);
  * thermal    — the non-conserved remainder dissipated as heat = (1−η)·(PMF power).

It writes a four-panel time-series PNG to the fig-06 study visualizations and
asserts the load-bearing claims: ATP flux scales with the driving proton flux, the
ATP:H⁺ stoichiometry is 1/n_protons_per_atp, and the electrical energy balance
(heat = input power − useful work) holds. Re-run whenever the fig06 dynamics or the
runnable composite change.

    python scripts/build_fig06_dynamics.py
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig06-runnable.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-06" / "visualizations" / "fig06-dynamics.png"

E_CHARGE = 1.602e-19   # elementary charge (C) — matches proton_charge in the composite
PMF_VOLTS = 0.15       # matches molecular_mechanism.config.pmf_volts
N_PROTONS = 3.3        # matches molecular_mechanism.config.n_protons_per_atp
EFFICIENCY = 0.75      # matches molecular_mechanism.config.efficiency
TORQUE_NM = 40.0 * 1e-21  # configured 40 pN·nm in N·m

# palette (matches the study figures' teal / accent family)
C_ATP, C_CURRENT, C_TORQUE, C_HEAT, C_DRIVE = "#0b7a75", "#b4531f", "#4b5bd6", "#c0392b", "#999999"


def _run():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def main() -> None:
    rows = _run()
    t = [float(r["time"]) for r in rows]
    atp = [float(r["chemical_out"]) for r in rows]
    current = [float(r["electrical_out"]) for r in rows]
    torque = [float(r["mechanical_out"]) for r in rows]
    heat = [float(r["thermal_out"]) for r in rows]
    # the driving proton flux J_H = I / e (H⁺·s⁻¹) — the one coupled quantity.
    j_h = [i / E_CHARGE for i in current]

    # ── load-bearing claims (assert before plotting) ─────────────────────────
    assert atp[-1] > atp[1] > 0.0, "ATP synthesis flux should be positive and rise with the drive"
    assert j_h[-1] > j_h[1] > 0.0, "the driving proton flux should rise over the run"
    # ATP:H⁺ stoichiometry = 1/n_protons_per_atp on every active step.
    ratios = [a / h for a, h in zip(atp[1:], j_h[1:])]
    assert all(abs(r - 1.0 / N_PROTONS) < 1e-6 for r in ratios), "ATP:H⁺ must equal 1/n_protons"
    # torque ≈ configured, ~constant.
    assert all(abs(x - TORQUE_NM) < 1e-24 for x in torque[1:]), "torque should hold at the configured value"
    # electrical energy balance: heat = (1−η)·input power, input power = I·pmf.
    for i, q in zip(current[1:], heat[1:]):
        in_power = i * PMF_VOLTS
        useful = in_power - q
        assert abs(q - (1.0 - EFFICIENCY) * in_power) < 1e-24, "heat must be (1−η)·input power"
        assert useful >= 0.0 and q >= 0.0, "useful work and heat must be non-negative"

    atp_h = atp[-1] / j_h[-1]

    # ── figure ────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.4), sharex=True)
    fig.suptitle("Fig 6 — a molecular transducer couples a proton-motive force across four typed channels",
                 fontsize=14, fontweight="bold")
    fig.text(0.5, 0.925,
             "The F₁Fₒ ATP synthase: one proton flux (drive, dashed) sets ATP synthesis, proton current, "
             "rotary torque and heat — conserving matter, charge, angular momentum and energy.",
             ha="center", fontsize=9.5, color="#444")

    def _drive_twin(ax):
        """Overlay the driving proton flux J_H (dashed, right axis) for the 'vs drive' read."""
        ax2 = ax.twinx()
        ax2.plot(t, j_h, color=C_DRIVE, ls="--", lw=1.3, label="driving proton flux J_H")
        ax2.set_ylabel("J_H  (H⁺·s⁻¹)", color=C_DRIVE, fontsize=8)
        ax2.tick_params(axis="y", labelcolor=C_DRIVE, labelsize=7)
        return ax2

    # (1) ATP synthesis flux
    ax = axes[0][0]
    ax.plot(t, atp, color=C_ATP, lw=2.4, marker="o", ms=3)
    ax.set_title("Chemical — ATP synthesis flux  (scales with the drive)", fontsize=10.5)
    ax.set_ylabel("J_ATP  (ATP·s⁻¹)")
    ax.grid(alpha=0.25)
    _drive_twin(ax)
    ax.annotate(f"ATP:H⁺ = {atp_h:.3f} ≈ 1/{N_PROTONS:g}",
                xy=(0.04, 0.86), xycoords="axes fraction", fontsize=9,
                bbox=dict(boxstyle="round,pad=0.3", fc="#eef6f5", ec=C_ATP, lw=0.8))

    # (2) proton current
    ax = axes[0][1]
    ax.plot(t, current, color=C_CURRENT, lw=2.4, marker="o", ms=3)
    ax.set_title("Electrical — proton current  I = J_H·e", fontsize=10.5)
    ax.set_ylabel("I  (A)")
    ax.grid(alpha=0.25)
    _drive_twin(ax)

    # (3) rotary torque
    ax = axes[1][0]
    ax.plot(t, torque, color=C_TORQUE, lw=2.4, marker="o", ms=3)
    ax.axhline(TORQUE_NM, color="#bbb", ls=":", lw=1)
    ax.set_title("Mechanical — rotary torque on the Fₒ rotor  (~constant, 40 pN·nm)", fontsize=10.5)
    ax.set_ylabel("torque  (N·m)")
    ax.set_xlabel("time")
    ax.set_ylim(0, TORQUE_NM * 1.6)
    ax.grid(alpha=0.25)
    _drive_twin(ax)

    # (4) dissipated heat
    ax = axes[1][1]
    ax.plot(t, heat, color=C_HEAT, lw=2.4, marker="o", ms=3)
    ax.set_title(f"Thermal — dissipated heat  = (1−η)·PMF power  (η={EFFICIENCY:g})", fontsize=10.5)
    ax.set_ylabel("heat  (W)")
    ax.set_xlabel("time")
    ax.grid(alpha=0.25)
    _drive_twin(ax)

    fig.tight_layout(rect=(0, 0, 1, 0.9))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150)
    plt.close(fig)
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  driving proton flux J_H  {j_h[1]:.3e} → {j_h[-1]:.3e}  H⁺·s⁻¹")
    print(f"  ATP synthesis flux       {atp[1]:.3f} → {atp[-1]:.3f}  ATP·s⁻¹  (ATP:H⁺ = {atp_h:.4f} ≈ 1/{N_PROTONS:g})")
    print(f"  proton current           {current[1]:.3e} → {current[-1]:.3e}  A")
    print(f"  rotary torque            {torque[-1]:.3e}  N·m  (configured {TORQUE_NM:.3e})")
    print(f"  dissipated heat          {heat[1]:.3e} → {heat[-1]:.3e}  W  (= (1−η)·input power, η={EFFICIENCY:g})")


if __name__ == "__main__":
    main()
