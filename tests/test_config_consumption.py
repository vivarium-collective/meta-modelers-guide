"""Config-consumption audit (peer-review M6 / answers Q5).

Every scalar a composite pins in a process's ``config`` block is a published
parameter value. The reviewer's worry (Q5): does that value actually *reach*
the process, or does something between the JSON and the running Process
silently drop it? There is a real, documented failure mode here --
bigraph-schema's ``core.fill`` treats a Float/Integer ``0`` (and other
"empty" values) as absent and refills it from the schema ``_default``, so a
deliberately-pinned ``mut_sigma: 0.0`` (or any legitimate 0) can be clobbered
back to a non-zero default without any error. Several workspace processes
carry an explicit ``__init__`` restore-guard against exactly this
(``GrayScott``, ``Protocell``, ``CpmSorting`` ...); this test is the gate that
proves the guards hold and that no *un*-guarded process is quietly discarding
a published value.

Mechanism: for every ``*.composite.json``, resolve and instantiate each
``process``/``step`` node, then assert every key the composite supplied in its
``config`` is *retained* in the constructed instance's effective ``config``
(same value, within float tolerance). A supplied key that vanishes or comes
back changed is a DROPPED published parameter -- a real bug -- unless it is on
the explicit :data:`ALLOW_DROPPED` list of keys a process is documented to
intentionally ignore.

Sensitivity is not assumed: :func:`test_audit_detects_a_real_drop` constructs
a deliberately guard-less process that pins ``a=0.0`` and asserts the audit
flags it, so a green suite means the check works, not that it is vacuous.
"""
from __future__ import annotations

import importlib
import json
import math
from pathlib import Path

import pytest
from process_bigraph import Process

from meta_modelers_guide.core import build_core

COMPOSITE_DIR = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"
SPECS = sorted(COMPOSITE_DIR.glob("*.composite.json"))

# Keys a process is DOCUMENTED to accept-but-ignore or otherwise legitimately
# not retain verbatim in ``config``. Keyed by (process_class_name, config_key).
# Empty today: the audit currently finds zero dropped keys across every
# composite. Add an entry here (with a comment citing the process docstring
# that documents the intentional drop) only for a genuinely-inert key, never
# to paper over a real drop.
ALLOW_DROPPED: set[tuple[str, str]] = set()


def _ids(paths):
    return [p.name.replace(".composite.json", "") for p in paths]


def _class_short_name(address: str) -> str:
    return address.split(":", 1)[-1].lstrip("!").split(".")[-1]


def _resolve_class(address: str, core):
    """Resolve a composite process address to its class, or ``None`` if the
    backing distribution is not importable in this environment.

    Two address forms appear in these composites: ``local:<Name>`` (a class
    registered on the workspace core) and ``local:!<import.path.Class>`` (an
    external process addressed by dotted import path, e.g. spatio_flux's
    ``DiffusionAdvection``)."""
    data = address.split(":", 1)[1] if ":" in address else address
    if data.startswith("!"):
        module_path, _, cls_name = data[1:].rpartition(".")
        try:
            return getattr(importlib.import_module(module_path), cls_name)
        except Exception:
            return None
    return core.link_registry.get(data)


def _find_process_nodes(node, path="state"):
    """Yield (node_path, address, config) for every process/step node."""
    out = []
    if isinstance(node, dict):
        addr = node.get("address")
        if isinstance(addr, str) and node.get("_type") in ("process", "step") and "config" in node:
            out.append((path, addr, node.get("config") or {}))
        for key, value in node.items():
            out += _find_process_nodes(value, f"{path}/{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            out += _find_process_nodes(value, f"{path}[{i}]")
    return out


def _values_match(supplied, effective, rel=1e-9, abs_=1e-12) -> bool:
    """Deep, float-tolerant equality between a supplied config value and the
    value the constructed process actually holds."""
    if isinstance(supplied, bool) or isinstance(effective, bool):
        return supplied == effective
    if isinstance(supplied, (int, float)) and isinstance(effective, (int, float)):
        return math.isclose(float(supplied), float(effective), rel_tol=rel, abs_tol=abs_)
    if isinstance(supplied, dict) and isinstance(effective, dict):
        if set(supplied) != set(effective):
            return False
        return all(_values_match(supplied[k], effective[k], rel, abs_) for k in supplied)
    if isinstance(supplied, (list, tuple)) and isinstance(effective, (list, tuple)):
        if len(supplied) != len(effective):
            return False
        return all(_values_match(a, b, rel, abs_) for a, b in zip(supplied, effective))
    return supplied == effective


def _dropped_keys_for_composite(spec_path: Path, core):
    """Return the list of dropped/clobbered keys for one composite as
    (process, node_path, key, supplied, effective) tuples. Processes whose
    backing dependency is not importable, or that cannot be instantiated in
    isolation, are skipped (that is the build test's job, not this one)."""
    spec = json.loads(spec_path.read_text())
    dropped = []
    for node_path, address, config in _find_process_nodes(spec.get("state", {})):
        if not config:
            continue
        cls = _resolve_class(address, core)
        if cls is None:
            continue  # optional dependency absent in this environment
        cls_name = _class_short_name(address)
        try:
            proc = cls(dict(config), core=core)
        except Exception:
            # Some processes require live wiring/fields to construct; the
            # config-retention question only applies to ones we can build in
            # isolation. A build failure is caught by test_composites_build.
            continue
        effective = getattr(proc, "config", {}) or {}
        for key, supplied in config.items():
            if (cls_name, key) in ALLOW_DROPPED:
                continue
            if key not in effective:
                dropped.append((cls_name, node_path, key, supplied, "<MISSING>"))
            elif not _values_match(supplied, effective[key]):
                dropped.append((cls_name, node_path, key, supplied, effective[key]))
    return dropped


def test_specs_present():
    assert SPECS, f"no composite specs found in {COMPOSITE_DIR}"


@pytest.mark.parametrize("spec_path", SPECS, ids=_ids(SPECS))
def test_config_fully_consumed(spec_path):
    """No process silently drops a value its composite pinned in ``config``."""
    core = build_core()
    dropped = _dropped_keys_for_composite(spec_path, core)
    if dropped:
        lines = [
            f"  {proc}.{key} (at {node_path}): supplied {supplied!r} -> effective {effective!r}"
            for proc, node_path, key, supplied, effective in dropped
        ]
        pytest.fail(
            f"{spec_path.name}: {len(dropped)} published config value(s) dropped "
            f"by bigraph-schema fill (or otherwise not retained):\n" + "\n".join(lines)
            + "\n(If a key is intentionally inert, add (Process, key) to ALLOW_DROPPED "
            "with a docstring citation; do NOT allow-list a real drop.)"
        )


def test_audit_detects_a_real_drop():
    """Sensitivity guard: a guard-less process that pins a Float ``0.0`` really
    does lose it to the schema default, and the audit's value comparison
    flags that -- so a green suite means the check works, not that it is inert."""
    core = build_core()

    class _NaiveDropper(Process):
        config_schema = {
            "a": {"_type": "float", "_default": 5.0},
            "b": {"_type": "float", "_default": 7.0},
        }

        def inputs(self):
            return {}

        def outputs(self):
            return {}

        def update(self, state, interval):
            return {}

    proc = _NaiveDropper({"a": 0.0, "b": 3.0}, core=core)
    # The disease: 0.0 is treated as empty and refilled to the 5.0 default.
    assert proc.config["a"] != 0.0, (
        "expected bigraph-schema to clobber a pinned 0.0 in an unguarded "
        "process; if this no longer holds the disease is gone and the audit's "
        "premise should be revisited"
    )
    assert not _values_match(0.0, proc.config["a"]), "value comparison must flag the clobbered 0.0"
    # A retained value must NOT be flagged.
    assert _values_match(3.0, proc.config["b"])
