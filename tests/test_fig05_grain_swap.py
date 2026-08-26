"""Fig 5 · a process is swapped between grains as a function of viability.

The runnable fig05 composite (meta_modelers_guide.composites.fig05-grain-runnable)
drives a cell's viability down with a simple external stress ramp; a GrainSelector
swaps which grain realizes the shared interface as viability crosses a threshold.
Two gated processes realize the same biomass output at different grains — a cheap
coarse linear yield and a mechanistic fine Michaelis-Menten law — and exactly one
runs per tick. This test asserts the CAUSAL claims the figure makes:

  (a) while viability >= threshold, active_grain == "coarse";
  (b) once viability drops below threshold the grain becomes "fine" and STAYS fine;
  (c) the switch happens at the tick where viability crosses the threshold (+/- 1);
  (d) the gate hands control over: driven at active_grain="coarse" only the coarse
      process produces biomass, at "fine" only the fine process does — and biomass
      keeps accumulating from whichever grain is active across the run.

Mirrors test_fig10_topology.py (run the composite, assert on the emitted frames).
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.fig05_grain import CoarseGrainProcess, FineGrainProcess

COMPOSITE = (
    Path(__file__).resolve().parent.parent
    / "meta_modelers_guide" / "composites" / "fig05-grain-runnable.composite.json"
)
THRESHOLD = 0.5  # matches grain_selector.config.threshold


def _run_trajectory():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def _cols(rows):
    viab = [float(r["viability"]) for r in rows]
    grain = [str(r["active_grain"]) for r in rows]
    bio = [float(r["biomass"]) for r in rows]
    return viab, grain, bio


# ── (a) coarse while viable ───────────────────────────────────────────────────
def test_coarse_grain_while_viable():
    viab, grain, _ = _cols(_run_trajectory())
    for v, g in zip(viab, grain):
        if v >= THRESHOLD:
            assert g == "coarse", f"viability {v:.3f} >= {THRESHOLD} but grain is {g!r}"


# ── (b) flips to fine and STAYS fine once stressed ────────────────────────────
def test_flips_to_fine_and_stays():
    viab, grain, _ = _cols(_run_trajectory())
    assert grain[0] == "coarse"
    # exactly one transition, and it is coarse -> fine.
    flips = [i for i in range(1, len(grain)) if grain[i] != grain[i - 1]]
    assert len(flips) == 1, f"expected exactly one grain switch, saw {len(flips)}"
    flip = flips[0]
    assert grain[flip - 1] == "coarse" and grain[flip] == "fine"
    assert all(g == "fine" for g in grain[flip:]), "grain must stay fine after the switch"


# ── (c) the switch tracks the viability-threshold crossing ────────────────────
def test_switch_at_threshold_crossing():
    viab, grain, _ = _cols(_run_trajectory())
    cross = next(i for i, v in enumerate(viab) if v < THRESHOLD)
    flip = next(i for i in range(1, len(grain)) if grain[i] != grain[i - 1])
    assert abs(flip - cross) <= 1, f"flip at t={flip} should track crossing at t={cross}"


# ── (d) the gate hands control over; previously-active grain goes inert ───────
def test_gate_hands_control_to_the_active_grain():
    core = build_core()
    coarse = CoarseGrainProcess({}, core=core)
    fine = FineGrainProcess({}, core=core)

    def drive(proc, active):
        return proc.update({"inflow": 1.0, "active_grain": active}, 1.0)

    # coarse is selected: only the coarse process produces; the fine one is inert.
    assert drive(coarse, "coarse").get("biomass", 0.0) > 0.0
    assert drive(fine, "coarse") == {}
    # fine is selected: only the fine process produces; the coarse one is inert.
    assert drive(fine, "fine").get("biomass", 0.0) > 0.0
    assert drive(coarse, "fine") == {}
    # the two grains produce DISTINGUISHABLE biomass (the switch is visible).
    assert abs(drive(coarse, "coarse")["biomass"] - drive(fine, "fine")["biomass"]) > 0.1


def test_biomass_accumulates_across_the_switch():
    viab, grain, bio = _cols(_run_trajectory())
    cross = next(i for i, v in enumerate(viab) if v < THRESHOLD)
    assert bio[0] == 0.0
    assert bio[cross] > 0.0, "coarse grain should have built biomass before the switch"
    assert bio[-1] > bio[cross], "fine grain should keep building biomass after the switch"
    # biomass is non-decreasing throughout (production only, never lost).
    for a, b in zip(bio, bio[1:]):
        assert b >= a - 1e-9
