"""Q8 -- the molecular equal-diffusion control is provably single-variable.

The molecular-interfaces study claims that ``molecular-equal-diffusion-control``
isolates *diffusion asymmetry* as the cause of Turing pattern formation: it is
the flagship ``molecular-turing-pattern`` composite with the differential
diffusion (``Dv < Du``) removed (``Du == Dv``) and *nothing else* changed. The
reviewer (Q8) asked us to prove that "nothing else" -- that the control is not
quietly also varying the initial condition (a different ``seed_uv`` draw or
different nucleation patches would confound the comparison).

This test proves it at the level of bytes:

1. The two composites' baked ``t=0`` ``u`` and ``v`` fields are **byte-identical**
   (same 128x128 arrays, same seed_uv(n=128, seed=1) draw, same nucleation
   patches) -- so the initial condition is held fixed exactly, not merely
   "statistically similar".
2. The two GrayScott process configs differ in **exactly** the diffusion
   coefficients ``{Du, Dv}`` and agree on every other key (F, k, dt, seed,
   thr, steps_per_tick, Ea, Tref) -- so the single varied variable is the
   diffusion coefficient (equalized in the control, differential in the
   flagship).

Together these make the control a genuine single-variable causal control.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

COMPOSITE_DIR = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
CONTROL = "molecular-equal-diffusion-control"
FLAGSHIP = "molecular-turing-pattern"


def _spec(name):
    return json.loads((COMPOSITE_DIR / f"{name}.composite.json").read_text())


def _t0_fields(name):
    return _spec(name)["state"]["fields"]


def _grayscott_config(name):
    spec = _spec(name)
    found = {}

    def walk(node):
        if isinstance(node, dict):
            if node.get("_type") == "process" and "GrayScott" in node.get("address", ""):
                found.update(node.get("config", {}))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(spec)
    assert found, f"{name}: no GrayScott process node found"
    return found


def test_t0_fields_are_byte_identical():
    """Same initial condition, held fixed to the byte."""
    control = _t0_fields(CONTROL)
    flagship = _t0_fields(FLAGSHIP)
    assert set(control) == set(flagship) == {"u", "v"}, "unexpected t=0 field set"
    for key in ("u", "v"):
        a = np.array(control[key], dtype=float)
        b = np.array(flagship[key], dtype=float)
        assert a.shape == b.shape == (128, 128), f"{key}: unexpected shape {a.shape} / {b.shape}"
        assert a.tobytes() == b.tobytes(), (
            f"{key}: control and flagship t=0 fields are NOT byte-identical -- the "
            f"equal-diffusion control varies the initial condition as well as the "
            f"diffusion coefficient, so it is not a single-variable control"
        )


def test_only_varied_variable_is_the_diffusion_coefficient():
    """Configs differ in exactly {Du, Dv} and agree on all other keys."""
    control = _grayscott_config(CONTROL)
    flagship = _grayscott_config(FLAGSHIP)
    differing = {k for k in set(control) | set(flagship) if control.get(k) != flagship.get(k)}
    assert differing == {"Du", "Dv"}, (
        f"expected the control to vary ONLY the diffusion coefficients {{Du, Dv}}; "
        f"actual differing keys: {sorted(differing)}"
    )
    # And the control genuinely equalizes diffusion while the flagship is asymmetric.
    assert control["Du"] == control["Dv"], "control must equalize Du == Dv"
    assert flagship["Dv"] < flagship["Du"], "flagship must keep the Turing asymmetry Dv < Du"
