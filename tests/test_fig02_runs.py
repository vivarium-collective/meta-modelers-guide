"""Fig 2 · orchestration across timescales — multi-timestepping is EXECUTABLE.

Fig 2 is the orchestration overview. Panel (a), multi-timestepping, is the piece
a minimal run can demonstrate honestly: processes updating at DIFFERENT rates
through a SHARED store. The runnable composite
(meta_modelers_guide.composites.fig02-runnable) wires two processes to one pool:

  * FastProduction (interval 1.0) fills pool.molecules every base tick;
  * SlowConversion (interval 5.0) fires every 5 ticks, converting a fraction of the
    accumulated pool into pool.biomass and drawing it back out.

These tests assert the multi-timestepping claim: the fast process updates the
shared store far more often than the slow one, the fast pool is a sawtooth (fills,
then drops each slow firing), and each slow conversion conserves what it moves.
(Panels (b) workflow-DAG and (c) event rewrites are structural/schematic and are
not part of this runnable demonstration.)
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.fig02_demo import FastProduction, SlowConversion

COMPOSITE = (
    Path(__file__).resolve().parent.parent
    / "meta_modelers_guide" / "composites" / "fig02-runnable.composite.json"
)


def _run_trajectory():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def _n_changes(series):
    return sum(1 for x, y in zip(series, series[1:]) if abs(y - x) > 1e-9)


# ── the two processes have real dynamics (drive the handlers directly) ────────
def test_fast_production_adds_each_tick():
    core = build_core()
    fast = FastProduction({"rate": 1.0}, core=core)
    assert fast.update({"molecules": 3.0}, 1.0)["molecules"] == 1.0


def test_slow_conversion_conserves_what_it_moves():
    core = build_core()
    slow = SlowConversion({"yield_frac": 0.6}, core=core)
    delta = slow.update({"molecules": 10.0}, 5.0)
    assert delta["biomass"] > 0.0
    # what leaves molecules is exactly what arrives as biomass.
    assert abs(delta["biomass"] + delta["molecules"]) < 1e-12


# ── the composite runs and the two clocks are visibly different ───────────────
def test_fast_pool_updates_far_more_often_than_slow_biomass():
    rows = _run_trajectory()
    mol = [float(r["molecules"]) for r in rows]
    bio = [float(r["biomass"]) for r in rows]

    fast_changes = _n_changes(mol)
    slow_changes = _n_changes(bio)
    assert slow_changes >= 2, "the slow process should fire multiple times"
    assert fast_changes > 2 * slow_changes, (
        "the fast process should update the shared store far more often than the slow one")


def test_fast_pool_is_a_sawtooth():
    rows = _run_trajectory()
    mol = [float(r["molecules"]) for r in rows]
    # fills on the fast clock ...
    assert any(y > x for x, y in zip(mol, mol[1:])), "molecules should rise on the fast clock"
    # ... and is drawn down each time the slow process converts it.
    assert any(y < x for x, y in zip(mol, mol[1:])), "molecules should drop on each slow conversion"


def test_biomass_only_advances():
    """Biomass is produced on the slow clock and never returns to the pool: it is
    non-decreasing and ends strictly above where it started."""
    rows = _run_trajectory()
    bio = [float(r["biomass"]) for r in rows]
    assert bio[-1] > bio[0]
    for x, y in zip(bio, bio[1:]):
        assert y >= x - 1e-12


# ── mass is conserved through the shared store, across the two timescales ──────
def test_mass_conserved_across_timescales():
    """The two rates are coordinated through ONE shared store, and nothing is lost
    across the timescales: the fast process is the sole source (it injects rate*dt
    per base tick), and the slow process only MOVES mass between molecules and
    biomass within the pool. So at every emitted tick the total in the shared store
    (molecules + biomass) equals the cumulative fast injection, which for rate=1.0,
    interval=1.0 equals the elapsed time exactly. Deterministic — no RNG anywhere."""
    rows = _run_trajectory()
    for r in rows:
        total = float(r["molecules"]) + float(r["biomass"])
        assert abs(total - float(r["time"])) < 1e-9, (
            f"shared-store total {total} != cumulative fast injection {r['time']}")
    # and the exact final split is a deterministic regression pin.
    last = rows[-1]
    assert abs(float(last["time"]) - 20.0) < 1e-9
    assert abs(float(last["molecules"]) - 8.12) < 1e-9
    assert abs(float(last["biomass"]) - 11.88) < 1e-9


def test_biomass_is_a_coarse_slow_clock_staircase():
    """Biomass only advances on the slow clock (interval 5), so over a 20-tick run it
    changes just a handful of times and holds flat between slow firings — a coarse
    staircase, not the fast pool's per-tick motion. Deterministic pins on the three
    visible slow conversions."""
    rows = _run_trajectory()
    bio = [float(r["biomass"]) for r in rows]
    slow_changes = _n_changes(bio)
    # three visible slow conversions over the run (at t=10, 15, 20) ...
    assert slow_changes == 3, f"expected 3 slow conversions, saw {slow_changes}"
    # ... far fewer than the fast pool's per-tick updates.
    assert _n_changes([float(r["molecules"]) for r in rows]) > 3 * slow_changes
    # exact staircase levels the slow clock settles onto (deterministic).
    levels = sorted(set(round(b, 2) for b in bio))
    assert levels == [0.0, 3.0, 7.2, 11.88]
