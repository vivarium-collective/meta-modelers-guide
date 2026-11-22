"""Workspace evaluation hooks for the meta-modelers-guide studies.

The behavior_tests in this workspace were authored with ``measure.expr`` reducer
expressions over emitted observables — e.g. ``last(obs.persists)``,
``max(obs.enclosed_area)``, ``mean(obs.biomass)`` — and a scalar ``pass_if``
comparator (``==`` / ``<`` / ``>`` / ``<=`` / ``>=``). The discovery-engine run
evaluator grades a behavior_test only when its ``measure.kind`` is a run-data
kind; its native reduction for a scalar comparator is the window MEAN, which does
not match a ``last(...)`` / ``max(...)`` intent.

This hook registers a single derived-scalar computer, ``expr_scalar``, that reads
the test's own ``measure.expr``, resolves the inner observable (or arithmetic over
observables) against the run store, and applies the named reducer — returning the
exact scalar the test intends. A behavior_test opts into code grading by setting
``measure: {kind: derived, path: expr_scalar, expr: <reducer(expr)>}`` and keeping
its ``pass_if`` comparator; the evaluator then computes a signed, machine-graded
outcome instead of leaving the test pending in the agent bucket.

Tests whose ``pass_if.op`` is a bespoke semantic predicate (``saturates``,
``ledger_closes``, …) are intentionally NOT routed here — they remain
agent-graded until a dedicated evaluator exists for that predicate.
"""

from __future__ import annotations

import re
from typing import Any, Callable

# Reducers over the ordered series of emitted values (time-ascending).
_REDUCERS: dict[str, Callable[[list[float]], float]] = {
    "last": lambda v: v[-1],
    "final": lambda v: v[-1],
    "first": lambda v: v[0],
    "initial": lambda v: v[0],
    "min": min,
    "max": max,
    "mean": lambda v: sum(v) / len(v),
    "avg": lambda v: sum(v) / len(v),
    "sum": sum,
    "range": lambda v: max(v) - min(v),
    "amplitude": lambda v: max(v) - min(v),
}

_EXPR_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*\((.*)\)\s*$", re.DOTALL)


def _series_values(inner: str, reader: Any) -> list[float]:
    """Resolve ``inner`` (an observable path or arithmetic over observables) to
    the ordered, non-null list of emitted scalar values via the engine resolver."""
    from discovery_engine.study.evaluator.resolver import _resolve_series

    frame = _resolve_series(inner.strip(), reader)
    col = "value" if "value" in frame.columns else frame.columns[-1]
    out: list[float] = []
    for x in frame[col].to_list():
        if x is None:
            continue
        try:
            f = float(x)
        except (TypeError, ValueError):
            continue
        if f == f:  # drop NaN
            out.append(f)
    return out


def expr_scalar(reader: Any, test: dict, ws_root: Any) -> float:
    """Compute the scalar a behavior_test's ``measure.expr`` intends.

    ``expr`` is ``REDUCER(<observable-or-arithmetic>)`` (e.g. ``last(obs.persists)``,
    ``max(obs.a - obs.b)``) or a bare observable path (defaults to ``last``).
    Resolves the inner series from the run store and applies the reducer.
    """
    measure = test.get("measure") or {}
    expr = str(measure.get("expr") or measure.get("formula") or measure.get("path") or "").strip()
    if not expr:
        raise ValueError("expr_scalar: measure has no expr/formula/path")

    m = _EXPR_RE.match(expr)
    if m and m.group(1).lower() in _REDUCERS:
        reducer = m.group(1).lower()
        inner = m.group(2)
    else:
        # Bare observable / arithmetic with no reducer → take the final value.
        reducer = "last"
        inner = expr

    vals = _series_values(inner, reader)
    if not vals:
        raise ValueError(f"expr_scalar: empty series for {inner!r}")
    return float(_REDUCERS[reducer](vals))


def register_derived_scalars(registry: dict) -> None:
    """discovery-engine hook: register this workspace's derived-scalar computers."""
    registry["expr_scalar"] = expr_scalar
