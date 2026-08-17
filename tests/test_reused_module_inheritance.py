"""Guard: build_core() inherits REUSED modules into the shared workspace core.

Model-sourcing "reuse" means a catalogued module contributes its processes +
types to the ONE core every study runs on — not a per-task module-specific core.
``viva_meta_modelers_guide.core.build_core`` implements this via
``inherit_reused_modules`` (viva-munk, spatio-flux). If that inheritance is ever
dropped, composites that reuse those modules (spatial-competition = spatio-flux
dFBA, cell-jostling = viva-munk physics) break with ``no link found at address``.
This test makes that regression fail fast.

Each module is checked only when it is importable, so an environment missing an
optional module (e.g. viva-cpm's Rust wheel) skips that assertion instead of
failing.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


def _find_workspace_root() -> Path:
    for start in (Path.cwd(), Path(__file__).resolve().parent):
        node = start
        for _ in range(8):
            if (node / "workspace.yaml").is_file():
                return node
            if node.parent == node:
                break
            node = node.parent
    return Path.cwd()


_WS_ROOT = _find_workspace_root()
if str(_WS_ROOT) not in sys.path:
    sys.path.insert(0, str(_WS_ROOT))


# (import_name, a Process/Step the module registers that must land in the core)
_REUSED = [
    ("spatio_flux", "DynamicFBA"),
    ("viva_munk", "GrowDivide"),
    ("cpm", "CPMProcess"),
]


def _build_core():
    return importlib.import_module("viva_meta_modelers_guide.core").build_core()


@pytest.mark.parametrize("import_name,process_name", _REUSED)
def test_reused_module_process_inherited(import_name, process_name):
    try:
        importlib.import_module(import_name)
    except ImportError:
        pytest.skip(f"{import_name} not installed — inheritance not applicable")
    core = _build_core()
    assert process_name in core.link_registry, (
        f"build_core() did not inherit {import_name}'s `{process_name}` into the "
        f"shared workspace core; composites reusing {import_name} will fail with "
        f"'no link found at address'. Ensure inherit_reused_modules() runs in "
        f"viva_meta_modelers_guide.core.build_core()."
    )


def test_spatio_flux_types_inherited():
    """community_dfba wires ports to spatio-flux's custom types (fields, …);
    inheritance must register those, not only the processes."""
    try:
        importlib.import_module("spatio_flux")
    except ImportError:
        pytest.skip("spatio_flux not installed")
    core = _build_core()
    schema = core.access("fields")
    assert schema is not None, (
        "spatio-flux type `fields` did not resolve in the shared core — "
        "inherit_reused_modules must register spatio-flux's types (register_types)."
    )
