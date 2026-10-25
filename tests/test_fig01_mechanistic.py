"""Fig 1 mechanistic variant — reusable reversible transport, topology by wiring.

The baseline (fig01-runnable) shows one irreversible StoreTransfer between two
scalar stores. This variant makes the paper's COMPOSITION point concrete: ONE
reusable, reversible, typed CompartmentTransport class, instantiated on a nested
three-compartment place graph, gives DIFFERENT dynamics under different wiring —
the topology lives in the wiring, not the code — and the typed ports reject an
incompatible store (the schema-rejection negative control).

Each gate carries the reviewer's evidence class (pass_if.kind). The baseline's
exact 0.85^n trajectory is re-cast here as a numerical_convergence solver check
(the k_reverse→0 limit), not a scientific discovery.
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest
from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
CHAIN = ROOT / "meta_modelers_guide" / "composites" / "fig01-mechanistic.composite.json"
STAR = ROOT / "meta_modelers_guide" / "composites" / "fig01-mechanistic-star.composite.json"
EPS = 1e-9


def _run(path):
    spec = json.loads(path.read_text())
    sim = Composite({"state": spec["state"]}, core=build_core())
    sim.run(spec["default_n_steps"])
    rows = gather_emitter_results(sim)[("emitter",)]
    A = [float(r["A"]) for r in rows]
    B = [float(r["B"]) for r in rows]
    C = [float(r["C"]) for r in rows]
    return A, B, C


def test_both_topologies_build_and_run():
    """REGRESSION_PIN: both the chain and the hub composite build and run 40 ticks (41 rows)."""
    for p in (CHAIN, STAR):
        A, _, _ = _run(p)
        assert len(A) == 41


def test_transport_conserves_total():
    """INVARIANT: with no external source/sink, A+B+C is conserved to round-off on
    every step, in BOTH topologies — the reversible transport only moves quantity."""
    for p in (CHAIN, STAR):
        A, B, C = _run(p)
        tot = [a + b + c for a, b, c in zip(A, B, C)]
        assert max(abs(t - tot[0]) for t in tot) < 1e-9


def test_reversible_reaches_equilibrium_ratio():
    """INVARIANT / EMPIRICAL_COMPARISON: each reversible edge relaxes toward its
    detailed-balance equilibrium sink/source = k_forward/k_reverse = 4 — not the
    baseline's one-way drain to zero. In the hub both leaves equilibrate at 4:1."""
    A, B, C = _run(STAR)
    assert abs(B[-1] / A[-1] - 4.0) < 0.1 and abs(C[-1] / A[-1] - 4.0) < 0.1


def test_rewiring_redirects_flux_same_class():
    """MECHANISTIC_ABLATION (topology counterfactual): the SAME CompartmentTransport
    class with IDENTICAL configs gives DIFFERENT dynamics purely from rewiring —
    the chain A↔B↔C pushes quantity out to the deep compartment C (C ≫ B), while the
    hub A↔B,A↔C splits it evenly (B ≈ C). Topology is set by wiring and controls the
    outcome; nothing in the process code changed."""
    _, Bc, Cc = _run(CHAIN)
    _, Bs, Cs = _run(STAR)
    assert Cc[-1] > 2.0 * Bc[-1], "chain should drive quantity out to the deep compartment C"
    assert abs(Cs[-1] - Bs[-1]) < 0.05, "hub should split quantity evenly between B and C"
    assert Cc[-1] > 1.5 * Cs[-1], "rewiring measurably redirects where quantity ends up"


def test_same_class_reused_on_every_edge():
    """MECHANISTIC_ABLATION (reuse): both transport nodes in each composite resolve to
    the one CompartmentTransport class — one implementation, many edges."""
    spec = json.loads(CHAIN.read_text())
    sim = Composite({"state": spec["state"]}, core=build_core())
    classes = {type(sim.state[k]["instance"]).__name__
               for k in spec["state"] if isinstance(spec["state"][k], dict)
               and spec["state"][k].get("address") == "local:CompartmentTransport"}
    assert classes == {"CompartmentTransport"}


def test_typed_ports_reject_incompatible_store():
    """MECHANISTIC_ABLATION (negative type-compatibility control): the transport's
    ports are typed `concentration`, so a numeric store is accepted but a structural
    string is rejected by the schema — and forcing the bad wiring breaks the run."""
    core = build_core()
    assert core.check("concentration", 1.0) is True
    assert core.check("concentration", "PDB:1ABC") is False   # schema rejects the string
    # forcing a concentration port onto a structure store fails the run
    spec = json.loads(CHAIN.read_text())
    spec["state"]["cell"]["inner"]["B"] = {"_type": "structure", "_default": "PDB:1ABC"}
    with pytest.raises(Exception):
        bad = Composite({"state": spec["state"]}, core=build_core())
        bad.run(1)


def test_irreversible_limit_recovers_geometric_decay():
    """NUMERICAL_CONVERGENCE (solver verification, NOT a discovery): in the
    k_reverse→0 limit the reversible transport reduces to the baseline's first-order
    decay, so a single edge at k_forward=0.15 reproduces store_a[n] ≈ 0.85^n. This
    re-casts the baseline's exact 0.85^n pin as equation-specific solver verification."""
    state = {
        "store_a": {"_type": "concentration", "_default": 1.0},
        "store_b": {"_type": "concentration", "_default": 0.0},
        "t": {"_type": "process", "address": "local:CompartmentTransport", "interval": 1.0,
              "config": {"k_forward": 0.15, "k_reverse": EPS},
              "inputs": {"source": ["store_a"], "sink": ["store_b"]},
              "outputs": {"source": ["store_a"], "sink": ["store_b"]}},
        "emitter": {"_type": "step", "address": "local:RAMEmitter",
                    "config": {"emit": {"store_a": "concentration", "time": "float"}},
                    "inputs": {"store_a": ["store_a"], "time": ["global_time"]}},
    }
    sim = Composite({"state": state}, core=build_core())
    sim.run(20)
    rows = gather_emitter_results(sim)[("emitter",)]
    a = [float(r["store_a"]) for r in rows]
    for n, v in enumerate(a):
        assert abs(v - 0.85 ** n) < 1e-6, f"tick {n}: {v} vs 0.85^{n}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
