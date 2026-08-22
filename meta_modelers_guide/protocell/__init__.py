"""protocell -- study 7 `autopoiesis`'s membrane-persistence process: a scalar
membrane-density field `phi` under reaction-diffusion, closed under a
self-limiting internal-maintenance loop gated on the boundary's own topology.
Pure numpy/scipy over a `fields` store, independent of the CPM (`cpm/`) and
condensate (`condensate/`) processes -- they never interact.

Re-exports ``Protocell`` and ``ProtocellV2`` so
``meta_modelers_guide.core._iter_own_process_classes`` (which walks only this
package's immediate submodules via ``pkgutil.iter_modules``) finds the classes
when it imports this subpackage: it inspects ``dir(module)`` on whatever
``pkgutil`` yields for ``meta_modelers_guide.protocell``, which is this
``__init__`` module itself, not ``autopoiesis`` beneath it. Mirrors
``meta_modelers_guide/condensate/__init__.py``'s re-export of ``CahnHilliard``
exactly. ``ProtocellV2`` is the genuinely-local-mechanism autopoiesis (an
interior precursor field, no global closure observer in the update); see
``autopoiesis.py``'s v2 notes.
"""
from __future__ import annotations

from .autopoiesis import Protocell, ProtocellV2, ProtocellV2Open

__all__ = ["Protocell", "ProtocellV2", "ProtocellV2Open"]
