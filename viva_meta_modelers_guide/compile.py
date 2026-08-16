"""Compile a semantic (draft-process) composite into an executable one.

This is the algebraic-effect-system core (see
docs/concepts/semantic-to-executable-compilation.md):

* a **draft process** is an effect *signature* (typed ports + contract, no update);
* an executable **Process** is a *handler* for a signature;
* a **handler environment** assigns each signature a handler (+ config, + declared
  store refinements/inits);
* :func:`compile_composite` is the functor ``⟦C⟧_H`` — it swaps each draft node
  for its handler while preserving the place-graph (stores) and every wire.

Laws (enforced/asserted here and in tests/test_compilation.py):
1. conformance  — a handler must supply every signature port with a compatible type;
2. interface preservation — wiring + store paths are untouched (only declared
   ``refine``/``init`` may change a leaf's schema/value);
3. executability — the compiled state builds + runs (checked in tests);
4. handler independence — two conforming envs give two executables sharing one
   interface (Fig 6 grain-swap).
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field


class CompileError(Exception):
    """Raised when a handler environment does not conform to the semantic composite."""


# ── signatures ───────────────────────────────────────────────────────────────
def _ports(cls, kind: str) -> dict:
    """Return a class's ``inputs``/``outputs`` port dict, config-independently.

    Draft processes and the workspace handlers both declare fixed ports, so we
    can introspect uninitialised (call with the class as ``self``); fall back to a
    throwaway instance for processes whose ports method reads ``self``.
    """
    fn = getattr(cls, kind)
    try:
        return dict(fn(cls))
    except Exception:
        try:
            return dict(fn(cls.__new__(cls)))
        except Exception:
            return {}


@dataclass
class Signature:
    name: str
    inputs: dict
    outputs: dict


def signature_of(core, draft_name: str) -> Signature:
    cls = core.link_registry[draft_name]
    return Signature(draft_name, _ports(cls, "inputs"), _ports(cls, "outputs"))


# ── conformance (the H ⊢ S judgment) ─────────────────────────────────────────
@dataclass
class ConformanceReport:
    draft: str
    handler: str
    missing: list = field(default_factory=list)          # (dir, port)
    type_mismatches: list = field(default_factory=list)  # (dir, port, sig_type, handler_type)

    @property
    def ok(self) -> bool:
        return not self.missing and not self.type_mismatches

    def __str__(self) -> str:
        if self.ok:
            return f"{self.handler} ⊢ {self.draft}  ✓"
        parts = [f"{self.handler} ⊬ {self.draft}"]
        for d, p in self.missing:
            parts.append(f"  missing {d} port '{p}'")
        for d, p, st, ht in self.type_mismatches:
            parts.append(f"  {d} port '{p}': signature {st} vs handler {ht}")
        return "\n".join(parts)


def check_conformance(core, draft_name: str, handler_name: str,
                      allow_refine: set | None = None) -> ConformanceReport:
    """A handler conforms iff it supplies every signature port with a compatible
    type. ``allow_refine`` names ports whose type may legitimately differ because
    the env refines the store they wire to (e.g. a scalar field → grid array)."""
    allow_refine = allow_refine or set()
    sig = signature_of(core, draft_name)
    hcls = core.link_registry[handler_name]
    h_in, h_out = _ports(hcls, "inputs"), _ports(hcls, "outputs")
    rep = ConformanceReport(draft_name, handler_name)
    for direction, sig_ports, h_ports in (("input", sig.inputs, h_in),
                                          ("output", sig.outputs, h_out)):
        for port, sig_t in sig_ports.items():
            if port not in h_ports:
                rep.missing.append((direction, port))
            elif not _type_compatible(core, sig_t, h_ports[port]) and port not in allow_refine:
                rep.type_mismatches.append((direction, port, sig_t, h_ports[port]))
    return rep


def _type_compatible(core, sig_t, handler_t) -> bool:
    if sig_t == handler_t:
        return True
    # allow a handler type that inherits the signature type (a subtype)
    try:
        schema = core.access(handler_t) or {}
        return schema.get("_inherit") == sig_t or sig_t in (schema.get("_inherit") or [])
    except Exception:
        return False


# ── the compile functor ⟦C⟧_H ────────────────────────────────────────────────
def compile_composite(semantic_state: dict, handler_env: dict, core) -> dict:
    """Return the executable state for ``semantic_state`` under ``handler_env``.

    ``handler_env`` maps a draft class name to
    ``{"handler": <ClassName>, "config": {...}, "init": {path: value},
       "refine": {path: {"_type": ..., "_value": ...}}}``.
    Raises :class:`CompileError` if any handled node fails conformance.
    """
    out = deepcopy(semantic_state)
    refine_ports_by_draft = _refined_ports(semantic_state, handler_env)

    def walk(node):
        if not isinstance(node, dict):
            return
        for key, val in node.items():
            if not isinstance(val, dict):
                continue
            if val.get("_type") == "process":
                _compile_node(val, handler_env, core, refine_ports_by_draft)
            elif "_type" not in val:
                walk(val)

    walk(out)
    _apply_store_overrides(out, handler_env)
    return out


def _draft_name(node: dict) -> str | None:
    addr = str(node.get("address", ""))
    return addr.split(":")[-1] if addr.startswith("local:") else None


def _compile_node(node, handler_env, core, refine_ports_by_draft) -> None:
    draft = _draft_name(node)
    if draft is None or draft not in handler_env:
        return
    spec = handler_env[draft]
    handler = spec["handler"]
    # A *rewrite* handler (Fig 10 division/development/evolution) is an
    # event-driven graph rewrite whose draft signature is a placeholder — its
    # real contract is the ports the node WIRES (e.g. Divide's ``biomass ⇒
    # biomass_1, biomass_2, cell_count``), not the stub class signature. For such
    # handlers, conformance is checked against the node's wiring (law 2′). The
    # interface itself is still preserved: the daughter/biofilm/variant subtrees
    # the rewrite fills are already declared in the semantic composite, so
    # ``interface_of`` is unchanged; the handler animates a pre-declared
    # post-structure via a discrete event.
    if _is_rewrite(core, handler):
        rep = check_wiring_conformance(core, node, handler)
    else:
        rep = check_conformance(core, draft, handler,
                                allow_refine=refine_ports_by_draft.get(draft, set()))
    if not rep.ok:
        raise CompileError(str(rep))
    node["address"] = f"local:{handler}"
    node["config"] = {**spec.get("config", {}), **(node.get("config") or {})}
    node.pop("_draft", None)


def _is_rewrite(core, handler_name: str) -> bool:
    """A handler declares itself a rewrite handler with a class-level ``REWRITE``."""
    cls = core.link_registry.get(handler_name)
    return bool(getattr(cls, "REWRITE", False))


def check_wiring_conformance(core, node, handler_name: str) -> ConformanceReport:
    """Rewrite-handler conformance: the handler's ports must be exactly the ports
    the *node* wires (name-bijection per direction), so the composite builds and
    every wire has a port. Types are the store leaves' own types, trusted here."""
    hcls = core.link_registry[handler_name]
    h_in, h_out = set(_ports(hcls, "inputs")), set(_ports(hcls, "outputs"))
    n_in = set((node.get("inputs") or {}).keys())
    n_out = set((node.get("outputs") or {}).keys())
    rep = ConformanceReport(_draft_name(node) or "?", handler_name)
    for p in n_in - h_in:
        rep.missing.append(("wired-input", p))
    for p in n_out - h_out:
        rep.missing.append(("wired-output", p))
    for p in h_in - n_in:
        rep.missing.append(("handler-input-not-wired", p))
    for p in h_out - n_out:
        rep.missing.append(("handler-output-not-wired", p))
    return rep


def _refined_ports(semantic_state, handler_env) -> dict:
    """Map draft name → set of its port names whose wired store is refined."""
    refined_paths = {tuple(p.split("."))
                     for spec in handler_env.values()
                     for p in (spec.get("refine") or {})}
    out: dict[str, set] = {}
    for node in _iter_processes(semantic_state):
        draft = _draft_name(node)
        if draft is None or draft not in handler_env:
            continue
        ports = set()
        for wiring in (node.get("inputs") or {}), (node.get("outputs") or {}):
            for port, path in wiring.items():
                if tuple(path) in refined_paths:
                    ports.add(port)
        if ports:
            out[draft] = ports
    return out


def _iter_processes(state):
    for val in state.values() if isinstance(state, dict) else []:
        if isinstance(val, dict):
            if val.get("_type") == "process":
                yield val
            elif "_type" not in val:
                yield from _iter_processes(val)


def _apply_store_overrides(state, handler_env) -> None:
    # NOTE: process-bigraph realize initialises a typed leaf from ``_default``,
    # NOT ``_value`` (the draft composites' ``_value: 0.0`` is inert). So an
    # ``init`` override must set ``_default`` to take effect at build.
    for spec in handler_env.values():
        for path, value in (spec.get("init") or {}).items():
            _set_leaf(state, path.split("."), {"_default": value})
        for path, schema in (spec.get("refine") or {}).items():
            _set_leaf(state, path.split("."), schema)


def _set_leaf(state, path, patch) -> None:
    node = state
    for key in path[:-1]:
        node = node.get(key, {}) if isinstance(node, dict) else {}
    leaf = node.get(path[-1]) if isinstance(node, dict) else None
    if isinstance(leaf, dict):
        leaf.update(patch)


# ── interface (law #2) ────────────────────────────────────────────────────────
def interface_of(state: dict) -> dict:
    """The EXTERNAL interface: every process's port names + the store paths they
    wire to. Compilation must leave this identical (schemas may differ only at
    declared refine paths)."""
    ports, wired = set(), set()
    for node in _iter_processes(state):
        for wiring in (node.get("inputs") or {}), (node.get("outputs") or {}):
            for port, path in wiring.items():
                ports.add(port)
                wired.add(tuple(path))
    return {"ports": ports, "wired_store_paths": wired}
