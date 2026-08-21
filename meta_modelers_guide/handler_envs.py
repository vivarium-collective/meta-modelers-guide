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
from .handlers_fig07 import ENV as _FIG07_ENV
from .handlers_fig08 import ENV as _FIG08_ENV
from .handlers_fig09a import ENV as _FIG09A_ENV
from .handlers_fig06_fba import ENV as _FIG06_FBA_ENV
from .handlers_fig09b import ENV as _FIG09B_ENV
from .handlers_fig10 import (ENV_DIVISION as _FIG10_DIV,
                             ENV_DEVELOPMENT as _FIG10_DEV,
                             ENV_EVOLUTION as _FIG10_EVO)

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

# Figures 4b / 5 / 7 / 8 / 9a / 9b (defined next to their handlers).
ENVS["fig04b"] = _FIG04B_ENV
ENVS["fig05"] = _FIG05_ENV
ENVS["fig07"] = _FIG07_ENV
ENVS["fig08"] = _FIG08_ENV
ENVS["fig09a"] = _FIG09A_ENV
ENVS["fig09b"] = _FIG09B_ENV
ENVS["fig10-1"] = _FIG10_DIV
ENVS["fig10-2"] = _FIG10_DEV
ENVS["fig10-3"] = _FIG10_EVO
# Fig 6, a THIRD handler over the same interface: real FBA (optional cobra dep).
ENVS["fig06-fba"] = _FIG06_FBA_ENV

# Cell–cell coupling: two cells over ONE shared-nutrient interface (law 4).
#
# NOTE on env↔node keying: viva_compiler.compiler._compile_node keys the handler
# lookup by `_draft_name(node)`, which is parsed purely from the node's `address`
# (e.g. "local:CellAgent" -> "CellAgent") — it does NOT look at the node's own key
# in the composite's state dict, so there is no "CellAgent#a"/"CellAgent#b" or
# per-node-name keying convention to hook into, and node config always overrides
# env config per-key (so per-node config in the composite would silently make an
# env's config dead — NOT a place to carry mechanism asymmetry, since it would
# defeat law 4's "env swaps mechanism" story). Instead the coupling composite uses
# TWO DRAFT ROLES with identical ports/contract — cell_a_proc addresses
# local:CellAgent, cell_b_proc addresses local:RivalCellAgent (see interfaces.py)
# — so each role gets its own env entry below and the asymmetry lives entirely in
# the env layer, where it belongs. The composite's node config carries only
# {"interval": ...}, exactly like every other draft composite in this workspace.
from .handlers_cellcell import NutrientPool  # noqa: F401  (registration side-effect)

# Competition: CellAgent (cell_a) is the stronger competitor (vmax 0.8), RivalCellAgent
# (cell_b) the weaker one (vmax 0.2) — cell_b starves out of the viable band while
# cell_a persists, over the shared pool both draw down.
ENVS["cellcell-compete"] = {
    "SharedNutrientEnv": {"handler": "NutrientPool",
                          "config": {"supply": 0.5, "capacity": 1.0},
                          "init": {"env.nutrient": 1.0}},
    "CellAgent": {"handler": "CompetingCell",
                  "config": {"vmax": 0.8, "km": 0.3, "yield_": 0.5,
                             "maintenance": 0.1, "via_gain": 0.4},
                  "init": {"cell_a.viability": 1.0}},
    "RivalCellAgent": {"handler": "CompetingCell",
                       "config": {"vmax": 0.2, "km": 0.3, "yield_": 0.5,
                                  "maintenance": 0.1, "via_gain": 0.4},
                       "init": {"cell_b.viability": 1.0}},
}

# Cross-feeding: BOTH roles get the SAME symmetric CrossFeedingCell config (vmax 0.6
# each) — cooperation, not competitive strength, is what sustains both cells here.
ENVS["cellcell-crossfeed"] = {
    "SharedNutrientEnv": {"handler": "NutrientPool",
                          "config": {"supply": 0.5, "capacity": 1.0},
                          "init": {"env.nutrient": 1.0}},
    "CellAgent": {"handler": "CrossFeedingCell",
                  "config": {"vmax": 0.6, "km": 0.3, "yield_": 0.5,
                             "maintenance": 0.1, "via_gain": 0.4, "return_frac": 0.7},
                  "init": {"cell_a.viability": 1.0}},
    "RivalCellAgent": {"handler": "CrossFeedingCell",
                       "config": {"vmax": 0.6, "km": 0.3, "yield_": 0.5,
                                  "maintenance": 0.1, "via_gain": 0.4, "return_frac": 0.7},
                       "init": {"cell_b.viability": 1.0}},
}
