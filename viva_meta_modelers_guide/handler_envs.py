"""Handler environments — assign each figure's effect signatures (draft classes)
a concrete executable handler + config + initial store values (+ declared store
refinements for spatial handlers). Consumed by compile.py / build_executables.py.

Each env: ``{draft_class_name: {"handler", "config", "init", "refine"}}``.
Fig 6 ships TWO envs over the SAME interface (law #4: handler independence).
"""
from __future__ import annotations

# Per-figure handler environments live beside their handlers (handlers_fig*.py);
# aggregate them here so compile.py / build_executables.py see one ENVS map.
from .handlers_fig04b import ENV as _FIG04B_ENV
from .handlers_fig05 import ENV as _FIG05_ENV
from .handlers_fig09b import ENV as _FIG09B_ENV

ENVS: dict[str, dict] = {
    # Fig 6 grain-swap — same CoarseGrainedMetabolism interface, two handlers.
    "fig06-coarse": {
        "CoarseGrainedMetabolism": {
            "handler": "CoarseMetabolism",
            "config": {"biomass_yield": 0.5, "energy_yield": 0.3,
                       "entropy_rate": 0.1, "secretion_frac": 0.2},
            "init": {"coarse.nutrients": 1.0},
        },
        "CatalyzedReactionNetwork": {
            "handler": "KineticReactionNetwork",
            "config": {"k": 0.2},
            "init": {"molecular.substrates": 1.0, "molecular.catalysts": 1.0},
        },
    },
    "fig06-kinetic": {
        "CoarseGrainedMetabolism": {
            "handler": "KineticMetabolism",
            "config": {"vmax": 1.0, "km": 0.5, "biomass_yield": 0.5,
                       "energy_yield": 0.3, "entropy_rate": 0.1, "secretion_frac": 0.2},
            "init": {"coarse.nutrients": 1.0},
        },
        "CatalyzedReactionNetwork": {
            "handler": "KineticReactionNetwork",
            "config": {"k": 0.2},
            "init": {"molecular.substrates": 1.0, "molecular.catalysts": 1.0},
        },
    },
}

# Figures 4b / 5 / 9b (defined next to their handlers).
ENVS["fig04b"] = _FIG04B_ENV
ENVS["fig05"] = _FIG05_ENV
ENVS["fig09b"] = _FIG09B_ENV
