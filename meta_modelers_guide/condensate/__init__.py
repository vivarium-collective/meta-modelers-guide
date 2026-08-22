"""condensate -- the independent, uncoupled Cahn-Hilliard phase-field analogue for
study 6's "condensate" phase-separation regime (as opposed to `cpm/`'s CPM-cell
sorting regime -- the two processes never interact).

Re-exports ``CahnHilliard`` so ``meta_modelers_guide.core._iter_own_process_classes``
(which walks only this package's immediate submodules via ``pkgutil.iter_modules``)
finds the class when it imports this subpackage: it inspects ``dir(module)`` on
whatever ``pkgutil`` yields for ``meta_modelers_guide.condensate``, which is this
``__init__`` module itself, not ``cahn_hilliard`` beneath it. Mirrors
``meta_modelers_guide/cpm/__init__.py``'s re-export of ``CpmSorting`` exactly.
"""
from __future__ import annotations

from .cahn_hilliard import CahnHilliard

__all__ = ["CahnHilliard"]
