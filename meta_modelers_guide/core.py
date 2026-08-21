"""build_core() — the workspace core that composites and tests run against.

`process_bigraph.allocate_core()` auto-discovers processes/types from *installed
distributions* that depend on bigraph-schema (it scans
``importlib.metadata.packages_distributions()``). That works for sibling
``viva-*`` wrapper packages installed as regular wheels, but it does NOT see this
workspace's own package when it is installed *editable* (``pip install -e .`` —
the way CI and local dev install it): an editable install records only a
``.pth`` shim in its ``RECORD``, so ``packages_distributions()`` never maps this
package back to its distribution and the discovery scan skips it entirely. The
result is that any Process/Step defined IN this package is missing from the
core's link registry, and a composite addressing ``local:<ProcessName>`` fails
at build with::

    Exception: no link found at address: {'protocol': 'local', 'data': '<ProcessName>'}

So we register this workspace's own Process/Step classes explicitly here. The
registration is idempotent (a class already provided by auto-discovery — e.g. in
a non-editable / Docker install — is left untouched), so ``build_core()`` is
correct regardless of how the workspace was installed. A fresh scaffold with no
process classes yet is a clean no-op.
"""
from __future__ import annotations

import importlib
import pkgutil

from process_bigraph import Process, Step, allocate_core

# ``_iter_own_process_classes`` below walks this package's *immediate* submodules
# via ``pkgutil.iter_modules`` and inspects ``dir(module)`` on each. For a
# subpackage like ``meta_modelers_guide.cpm`` that module is the subpackage's
# ``__init__``, not the ``cell_field`` module beneath it — so the subpackage must
# import and re-export its Process classes for the scan to find them (see
# ``meta_modelers_guide/cpm/__init__.py``). This import is a defensive, explicit
# trigger for that registration path (the scan below would also import it lazily,
# but making it explicit here documents the dependency and keeps `local:CpmCellField`
# resolvable even if the scan's traversal strategy changes).
from . import cpm as _cpm  # noqa: F401  (registers CpmCellField)


def _iter_own_process_classes():
    """Yield (name, cls) for each Process/Step subclass defined in THIS package.

    Walks only this package's own top-level modules (resolved from ``__package__``
    so no name is hard-coded). Defensive: an import error in any single module is
    swallowed so one broken module never breaks ``build_core()``. A brand-new
    package with no process classes simply yields nothing.
    """
    package_name = __package__
    if not package_name:
        return
    try:
        package = importlib.import_module(package_name)
    except Exception:
        return
    search_paths = getattr(package, "__path__", None)
    if search_paths is None:
        return
    seen = set()
    for module_info in pkgutil.iter_modules(search_paths, package_name + "."):
        try:
            module = importlib.import_module(module_info.name)
        except Exception:
            # A module that fails to import (e.g. an optional heavy dep missing)
            # must not take down the whole core build.
            continue
        for attr_name in dir(module):
            obj = getattr(module, attr_name, None)
            if not isinstance(obj, type):
                continue
            if not issubclass(obj, (Process, Step)):
                continue
            if obj is Process or obj is Step:
                continue
            # Only register classes actually DEFINED in this package, not ones
            # imported into a module from elsewhere (e.g. the base classes).
            if not getattr(obj, "__module__", "").startswith(package_name):
                continue
            if obj.__name__ in seen:
                continue
            seen.add(obj.__name__)
            yield obj.__name__, obj


def register_workspace_processes(core):
    """Register this workspace's own Process/Step classes into ``core``.

    A name absent from the registry is added. A name already registered is left
    untouched UNLESS it is held by a class from a *foreign* package (i.e. an
    unrelated installed distribution's auto-discovered class that collides on the
    same name — e.g. ``spatio_flux.paper_figures.Transcription`` shadowing this
    guide's own ``Transcription`` draft): the workspace's own class then takes
    precedence, since ``local:<Name>`` in this workspace's composites must resolve
    to this workspace's definition. A class already provided by auto-discovery
    *from this same package* (non-editable/Docker install) matches and is a no-op.
    """
    package_name = __package__ or ""
    for name, cls in _iter_own_process_classes():
        existing = core.link_registry.get(name)
        existing_mod = getattr(existing, "__module__", "") if existing is not None else ""
        if existing is None or not existing_mod.startswith(package_name):
            core.register_link(name, cls)
    return core


def build_core(core=None):
    """Return a process-bigraph core with this workspace's processes registered.

    This is the canonical core for the workspace: composites that address
    ``local:<ProcessName>`` (and the test suite) must build their ``Composite``
    against a core returned from here, not a bare ``allocate_core()``.

    In addition to the workspace's Process/Step classes, this registers the
    biological interface types (``chemical_flux``, ``force``, ``growth_rate`` …)
    the draft-process figures wire their ports to. See ``_types.register_types``.
    """
    if core is None:
        core = allocate_core()
    try:
        from ._types import register_types
        register_types(core)
    except Exception:
        # A missing/broken _types module must never break core construction.
        pass
    register_workspace_processes(core)
    return core
