# tests/test_mass_balance.py
"""Closed field mass-balance control (P1-d) — the paper's own conservation-law
demand ("constrained by conservation laws such as mass and energy balance")
and the flagship spatial study's explicit unmet next-step ("Track field-wide
mass ... as an explicit closed balance rather than reporting
depletion/secretion as separate totals").

Runs the flagship ``single-cell-in-a-field`` composite for a short window and
asserts, per field species, that the ledger closes:

    initial_field_mass + Σ(every writer's own reported net exchange) == final_field_mass

within a tight numerical tolerance. See ``meta_modelers_guide/analysis/mass_balance.py``
for exactly what this control does and does not verify.

This is a standing regression guard — it is expected to PASS on correct code,
not a bug hunt. Skipped when the optional cobra/cpm/spatio_flux dependencies
are absent, matching ``tests/test_flagship_field.py``.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from meta_modelers_guide.core import build_core

pytest.importorskip("cobra")  # entire module skips without COBRApy
pytest.importorskip("cpm")  # + the spatial frameworks (absent from base CI)
pytest.importorskip("spatio_flux")

from meta_modelers_guide.analysis.mass_balance import field_mass_balance  # noqa: E402

COMP = (
    Path(__file__).resolve().parent.parent
    / "meta_modelers_guide"
    / "composites"
    / "single-cell-in-a-field.composite.json"
)

N_TICKS = 15
# Tight: the ledger sums the exact same delta arrays process-bigraph applies
# to the shared grid, so a closed ledger should agree to floating-point
# precision, not physical/model tolerance.
TOL = 1e-6


def test_flagship_field_mass_balance_closes():
    core = build_core()
    state = json.loads(COMP.read_text())["state"]

    ledgers = field_mass_balance(
        state,
        core,
        N_TICKS,
        writer_process_names=["cell", "diff"],
        species=["glucose", "acetate"],
    )

    glucose = ledgers["glucose"]
    acetate = ledgers["acetate"]

    # The ledger must close for both species: nothing unaccounted for.
    assert glucose.is_closed(TOL), (
        f"glucose mass-balance residual {glucose.residual!r} exceeds tolerance "
        f"{TOL!r} (initial={glucose.initial_mass!r}, final={glucose.final_mass!r}, "
        f"writer_net_exchange={glucose.writer_net_exchange!r})"
    )
    assert acetate.is_closed(TOL), (
        f"acetate mass-balance residual {acetate.residual!r} exceeds tolerance "
        f"{TOL!r} (initial={acetate.initial_mass!r}, final={acetate.final_mass!r}, "
        f"writer_net_exchange={acetate.writer_net_exchange!r})"
    )

    # Sanity checks on what the ledger actually shows, not just that it closes:
    # the cell sinks glucose (net uptake) and sources acetate (net secretion)
    # over a run long enough to metabolize (matches test_flagship_field.py).
    assert glucose.writer_net_exchange["cell"] < 0.0
    assert acetate.writer_net_exchange["cell"] > 0.0

    # DiffusionAdvection under Neumann BC should conserve total mass on its
    # own -- its net contribution to each species' ledger should be ~0,
    # distinct from (and much smaller than) the cell's net exchange.
    assert abs(glucose.writer_net_exchange["diff"]) <= TOL
    assert abs(acetate.writer_net_exchange["diff"]) <= TOL
