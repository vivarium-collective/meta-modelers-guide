"""The disintegration-spatial debris scatter must be reproducible.

Upstream ``BrownianMovement`` draws its Brownian steps from NumPy's *global*
RNG, so the shed-debris positions were run-to-run non-deterministic and a
``seed`` in the composite config was silently ignored. The composite now
addresses ``SeededBrownianMovement`` (seed pinned in config), so two builds of
the same spec, each run the same number of ticks, must produce byte-identical
particle positions.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from process_bigraph import Composite

pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")

from meta_modelers_guide.core import build_core  # noqa: E402

SPEC = (
    Path(__file__).resolve().parent.parent
    / "meta_modelers_guide" / "composites" / "disintegration-spatial.composite.json"
)


def _positions_after(n_ticks):
    spec = json.loads(SPEC.read_text())
    comp = Composite({"state": spec["state"]}, core=build_core())
    comp.run(n_ticks)
    particles = comp.state.get("particles", {}) or {}
    # Sort by particle id for a stable, order-independent comparison.
    return [tuple(particles[pid]["position"]) for pid in sorted(particles)]


def test_debris_scatter_is_reproducible():
    # Run far enough past release (~tick 7) that debris has been shed and moved.
    a = _positions_after(16)
    b = _positions_after(16)
    assert a, "expected debris particles to have been shed by tick 16"
    assert len(a) == len(b)
    assert np.allclose(np.array(a), np.array(b)), "debris scatter is not reproducible"
