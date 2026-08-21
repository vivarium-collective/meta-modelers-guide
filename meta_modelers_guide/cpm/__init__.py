"""viva-cpm coupling processes for the flagship "single cell in a field" composite
and its study-3 N-cell generalization.

Re-exports ``CpmCellField``/``CpmColonyField`` so
``meta_modelers_guide.core._iter_own_process_classes`` (which walks only this
package's immediate submodules via ``pkgutil.iter_modules``) finds the classes
when it imports this subpackage: it inspects ``dir(module)`` on whatever
``pkgutil`` yields for ``meta_modelers_guide.cpm``, which is this ``__init__``
module itself, not ``cell_field``/``colony_field`` beneath it.
"""
from __future__ import annotations

from .cell_field import CpmCellField
from .colony_field import CpmColonyField

__all__ = ["CpmCellField", "CpmColonyField"]
