"""viva-cpm coupling processes for the flagship "single cell in a field" composite.

Re-exports ``CpmCellField`` so ``meta_modelers_guide.core._iter_own_process_classes``
(which walks only this package's immediate submodules via ``pkgutil.iter_modules``)
finds the class when it imports this subpackage: it inspects ``dir(module)`` on
whatever ``pkgutil`` yields for ``meta_modelers_guide.cpm``, which is this
``__init__`` module itself, not ``cell_field`` beneath it.
"""
from __future__ import annotations

from .cell_field import CpmCellField

__all__ = ["CpmCellField"]
