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


def test_total_is_conserved():
    rows = _run_trajectory()
    total = [float(r["store_a"]) + float(r["store_b"]) for r in rows]
    assert max(total) - min(total) < 1e-9, "the transfer conserves store_a + store_b"
    assert abs(total[0] - 1.0) < 1e-9      # seeded total
