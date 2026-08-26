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
