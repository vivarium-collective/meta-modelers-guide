"""Semantic→executable compilation for this workspace.

The compiler itself now lives in the standalone **viva-compiler** package
(``pip install viva-compiler``); this module is a thin adapter that wires in this
workspace's **ontology-aware** type-compatibility hook and re-exports the API under
the names the workspace already uses. See viva-compiler's README and
``docs/concepts/semantic-to-executable-compilation.md``.

* a **draft process** is an effect *signature*;
* an executable **Process** is a *handler*;
* a **handler environment** installs a handler per signature;
* :func:`compile_composite` is the functor ``⟦C⟧_H``.

The only workspace-specific choice is :func:`_type_compatible`: two differently-named
interface types conform when they denote the same ontology term (Phase 5). Everything
else — conformance, interface preservation, rewrite handlers (law 2′) — is
viva-compiler's, unchanged.
"""
from __future__ import annotations

from viva_compiler import (
    CompileError,
    ConformanceReport,
    Signature,
    check_conformance as _check_conformance,
    check_wiring_conformance,
    compile_composite as _compile_composite,
    default_type_compatible,
    interface_of,
    is_rewrite,
    signature_of,
)
from viva_compiler.compiler import _refined_ports, _iter_processes, _draft_name

from .ontology import ontology_compatible

__all__ = [
    "CompileError", "ConformanceReport", "Signature",
    "signature_of", "check_conformance", "check_wiring_conformance",
    "compile_composite", "interface_of", "is_rewrite",
]

# Backward-compatible alias (the workspace + tests use the underscore name).
_is_rewrite = is_rewrite


def _type_compatible(core, sig_t, handler_t) -> bool:
    """This workspace's type check: viva-compiler's default (equality / ``_inherit``
    subtype) OR ontology equality — two differently-named interface types that
    denote the same ontology term are compatible (Phase 5)."""
    return default_type_compatible(core, sig_t, handler_t) or ontology_compatible(sig_t, handler_t)


def check_conformance(core, draft_name, handler_name, allow_refine=None):
    """Conformance with this workspace's ontology-aware type check."""
    return _check_conformance(core, draft_name, handler_name,
                              allow_refine=allow_refine, type_compatible=_type_compatible)


def compile_composite(semantic_state, handler_env, core):
    """The functor ``⟦C⟧_H`` with this workspace's ontology-aware type check."""
    return _compile_composite(semantic_state, handler_env, core, type_compatible=_type_compatible)
