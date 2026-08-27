"""Fig 1 · a process bigraph is EXECUTABLE — the wired stores actually evolve.

Fig 1 is the definitional figure (a process bigraph = a place graph of stores
with processes wired to them through typed ports). The runnable composite
(meta_modelers_guide.composites.fig01-runnable) puts the smallest honest dynamics
behind that picture: ONE real process (StoreTransfer) wired to TWO scalar
place-graph nodes — source ``store_a`` and sink ``store_b`` — under a first-order
transfer dA/dt = -k*A, dB/dt = +k*A.

These tests assert the claim the figure makes — that a process bigraph is
*executable*: given an update rule the wired stores evolve, here draining the
source into the sink while conserving the total.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.fig01_demo import StoreTransfer

COMPOSITE = (
    Path(__file__).resolve().parent.parent
    / "meta_modelers_guide" / "composites" / "fig01-runnable.composite.json"
)


def _run_trajectory():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


# ── the process has real dynamics (drive the handler directly) ────────────────
def test_transfer_moves_from_source_to_sink():
    core = build_core()
    proc = StoreTransfer({"rate": 0.15}, core=core)
    delta = proc.update({"source": 1.0}, 1.0)
    assert delta["source"] < 0.0        # source drains
    assert delta["sink"] > 0.0          # sink fills
    assert abs(delta["source"] + delta["sink"]) < 1e-12   # transfer conserves
    # the flux is exactly k·source·interval — the write to sink equals the
    # drain from source (the port pair is a conservative transfer, not a source/sink term)
    assert delta["sink"] == 0.15        # k=0.15, source=1.0, interval=1.0
    assert delta["source"] == -0.15


# ── the composite runs and the wired stores evolve ────────────────────────────
def test_source_drains_and_sink_fills_over_the_run():
    rows = _run_trajectory()
    a = [float(r["store_a"]) for r in rows]
    b = [float(r["store_b"]) for r in rows]

    # the stores genuinely evolved (not a static diagram):
    assert a[-1] < a[0] - 0.1, "source store_a should drain appreciably"
    assert b[-1] > b[0] + 0.1, "sink store_b should fill appreciably"

    # source strictly decreases, sink strictly increases, step by step.
    for x, y in zip(a, a[1:]):
        assert y < x + 1e-12
    for x, y in zip(b, b[1:]):
        assert y > x - 1e-12


def test_trajectory_is_the_exact_geometric_decay():
    """The composite is fixed-rate deterministic: with k=0.15 over interval 1.0,
    each step multiplies the source by (1-k)=0.85, so store_a[n] == 0.85**n and
    store_b[n] == 1 - 0.85**n exactly. Pins the real run, not just its direction."""
    rows = _run_trajectory()
    a = [float(r["store_a"]) for r in rows]
    b = [float(r["store_b"]) for r in rows]
    assert len(a) == 21                          # default_n_steps=20 -> ticks 0..20
    for n, (av, bv) in enumerate(zip(a, b)):
        assert av == pytest.approx(0.85 ** n, abs=1e-12)
        assert bv == pytest.approx(1.0 - 0.85 ** n, abs=1e-12)
    assert a[-1] == pytest.approx(0.85 ** 20, abs=1e-12)   # ~0.038760


def test_sink_overtakes_source_at_the_crossover_tick():
    """Source drains and sink fills, so the sink overtakes the source at a
    specific, deterministic tick — the crossover where b first exceeds a.
    0.85**n < 0.5 first at n=5, so store_b overtakes store_a at tick 5."""
    rows = _run_trajectory()
    a = [float(r["store_a"]) for r in rows]
    b = [float(r["store_b"]) for r in rows]
    crossover = next(n for n, (av, bv) in enumerate(zip(a, b)) if bv > av)
    assert crossover == 5
    assert b[4] < a[4]        # sink still below source the tick before
    assert b[5] > a[5]        # sink above source at the crossover


def test_total_is_conserved():
    rows = _run_trajectory()
    total = [float(r["store_a"]) + float(r["store_b"]) for r in rows]
    assert max(total) - min(total) < 1e-9, "the transfer conserves store_a + store_b"
    assert abs(total[0] - 1.0) < 1e-9      # seeded total
    # conserved at the seeded total for EVERY tick, not just endpoints
    for tot in total:
        assert tot == pytest.approx(1.0, abs=1e-9)
