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

    Idempotent: a name already present in ``core.link_registry`` (e.g. provided
    by auto-discovery in a non-editable install) is left untouched.
    """
    for name, cls in _iter_own_process_classes():
        if name not in core.link_registry:
            core.register_link(name, cls)
    return core


# ── Reused modules inherited into the shared workspace core ──────────────────
# Model-sourcing "reuse" made literal: importing a catalogued module folds its
# processes AND its custom types into the ONE core every study runs on, instead
# of each task spinning up a parallel module-specific core (the bug that left
# spatial-competition / cell-jostling running against mismatched cores). Each
# entry is (import_name, register) where ``register(core, module)`` contributes
# that module's registrations. Absent modules are skipped (e.g. viva-cpm's Rust
# wheel may not be built in every environment) so the core still builds; a
# registration error on a module that IS installed is allowed to surface.
def _inherit_viva_munk(core, mod):
    # viva_munk.core_import(core) registers viva_munk's processes + pymunk types
    # AND (its own dependency) spatio-flux's types into the passed-in core.
    mod.core_import(core)


def _inherit_spatio_flux(core, mod):
    # Processes (DynamicFBA, …) are discovered by allocate_core once imported;
    # register_types adds spatio-flux's custom types (fields, bounds, particle…).
    importlib.import_module("spatio_flux.visualizations")  # fire viz Step discovery
    mod.register_types(core)


def _inherit_cpm(core, mod):
    # viva-cpm (dist ``pbg-cpm``, import ``cpm``) exposes no register hook and its
    # Rust-backed CPMProcess is not auto-discovered, so register it explicitly.
    # Its ports use only base types (list/map/integer/float + overwrite), so no
    # cpm-specific type registration is needed.
    from cpm.processes.cpm_process import CPMProcess
    if "CPMProcess" not in core.link_registry:
        core.register_link("CPMProcess", CPMProcess)


_REUSED_MODULES = (
    ("viva_munk", _inherit_viva_munk),
    ("spatio_flux", _inherit_spatio_flux),
    ("cpm", _inherit_cpm),
)


def inherit_reused_modules(core):
    """Fold each installed reused module's processes + types into ``core``.

    A module that isn't installed is skipped (import failure is not an error —
    the workspace core must build without every optional dependency present).
    Registration is idempotent, so calling this on an already-populated core is
    safe.
    """
    for import_name, register in _REUSED_MODULES:
        try:
            mod = importlib.import_module(import_name)
        except ImportError:
            continue
        register(core, mod)
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
    # Inherit reused modules (viva-munk, spatio-flux, …) into the shared core so
    # every study runs on one core with all sourced modules present.
    inherit_reused_modules(core)
    try:
        from ._types import register_types
        register_types(core)
    except Exception:
        # A missing/broken _types module must never break core construction.
        pass
    register_workspace_processes(core)
    return core
