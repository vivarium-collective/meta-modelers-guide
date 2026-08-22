"""molecular -- Fig 6/7 draft processes (grain-swap equivalence, molecular
mechanism contracts) PLUS study 5 `molecular-interfaces`'s `GrayScott`
reaction-diffusion field process. Two independent things share this package
only because they share the "molecular" name in the guide's figures: the
drafts are typed/unit-bearing contracts with no mechanism; `GrayScott` is a
real numpy/scipy `fields`-store process (chemical Gray-Scott
autocatalysis + differential diffusion, with an optional thermal/Arrhenius
channel) -- pure numpy/scipy, independent of the CPM (`cpm/`), condensate
(`condensate/`), and protocell (`protocell/`) processes.

Was a flat `meta_modelers_guide/molecular.py` module (the Fig 6/7 drafts
only) before this package was introduced; that content now lives unchanged
in `drafts.py` and is re-exported here so nothing that referenced these
classes by name (e.g. `local:CoarseGrainedMetabolism` in build_core's
registry, or `check_conformance(core, "CoarseGrainedMetabolism", ...)`)
notices the split.

Re-exports both `drafts.py`'s DraftProcess classes and `gray_scott.py`'s
`GrayScott` so `meta_modelers_guide.core._iter_own_process_classes` (which
walks only this package's immediate submodules via `pkgutil.iter_modules`)
finds them: it inspects `dir(module)` on whatever `pkgutil` yields for
`meta_modelers_guide.molecular`, which is this `__init__` module itself, not
`drafts`/`gray_scott` beneath it. Mirrors
`meta_modelers_guide/condensate/__init__.py`'s re-export of `CahnHilliard`
and `meta_modelers_guide/protocell/__init__.py`'s re-export of `Protocell`.
"""
from __future__ import annotations

from .drafts import (
    CatalyzedReactionNetwork,
    CoarseGrainedMetabolism,
    MolecularMechanism,
)
from .gray_scott import GrayScott

__all__ = [
    "CatalyzedReactionNetwork",
    "CoarseGrainedMetabolism",
    "MolecularMechanism",
    "GrayScott",
]
