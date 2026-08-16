# Semantic → executable compilation, as an algebraic effect system

This workspace turns the compositional figures of *A meta-modeler's guide to the
cellular interface* into two layers and a **compiler** between them:

- a **semantic layer** — the figures, built from *draft processes* (typed ports +
  a behavior contract, **no dynamics**); and
- an **executable layer** — the same figures with each draft replaced by a real
  simulation **Process**, which **builds and runs**.

The compiler is defined, and made principled, as an **algebraic effect system**.

## The correspondence

| Algebraic effects | process-bigraph | here |
|---|---|---|
| operation / effect signature | a `DraftProcess` (class-level ports + contract, inert `update`) | `signature_of(draft)` |
| effectful term | a composite of draft nodes wired through a typed store | a `*.composite.json` figure |
| handler (interpretation of an operation) | an executable `Process` with matching ports + a real `update` | classes in `handlers*.py` |
| handler set / installation | a **handler environment** (signature → handler + config) | `handler_envs.py` (`ENVS`) |
| running a handled computation | building + running the `Composite` | `Composite(state).run(n)` |

A **draft process is an effect signature**: `op : (in : τ) ⇒ (out : τ)` where the
contract (`senses` / `affects` / `constraints`) records the operation's intended
pre/post/invariants. It declares *what* is exchanged, never *how* — its `update`
is inert. A **handler** interprets that operation with real dynamics.

## The compiler `⟦C⟧_H`

`compile_composite(C, H, core)` (in `compile.py`) is a functor from semantic
composites to executable ones. It walks `C`, and for each draft node `local:<S>`
with `S ∈ H`:

1. checks conformance `H(S) ⊢ S` (below), raising `CompileError` otherwise;
2. rewrites the node's `address` to the handler and merges its `config`;
3. leaves **every store and every wire untouched** (a declared `refine`/`init`
   may change only a leaf's schema/value — see law 2).

Because the place-graph and wiring are never touched, the cell's **interface** is
preserved by construction; only its *internal realization* changes. That is the
paper's central claim, made mechanical.

## The typing judgment: conformance `H ⊢ S`

A handler `H` conforms to signature `S` iff for **every** input/output port `p : τ`
of `S`, `H` has a port `p` whose type is `τ` (or a subtype, or — when the
environment `refine`s the store `p` wires to — a declared refinement of `τ`).
Extra handler ports are allowed. `check_conformance` returns a `ConformanceReport`;
`compile_composite` refuses to compile a non-conforming environment.

## Laws (see `tests/test_compilation.py`)

1. **Conformance.** `⟦C⟧_H` is defined only if `H(S) ⊢ S` for every operation `S`.
2. **Interface preservation (homomorphism).** `interface_of(⟦C⟧_H) = interface_of(C)`
   — the process port names and the store paths they wire to are identical.
   Internal **representation refinements** (e.g. a scalar `concentration` field →
   a grid `array` for a real spatial handler, Fig 5) are allowed *only* when
   declared in the environment's `refine`, never as an accidental structural
   change. With no `refine`, the store tree is byte-identical.
3. **Executability.** `⟦C⟧_H` builds into a `Composite` and produces non-trivial
   dynamics (some observable changes over a run); the semantic `C` is inert.
4. **Handler independence.** Two conforming environments `H₁, H₂` yield two valid
   executables that share one interface. **Fig 6** is the worked example: the one
   `CoarseGrainedMetabolism` signature (`nutrients ⇒ biomass, energy, entropy,
   secretions`) is handled by `CoarseMetabolism` (linear, lumped) *or*
   `KineticMetabolism` (saturating Michaelis–Menten) — different dynamics, one
   interface. This is the paper's Fig 6 grain-swap, executable.

## Worked example — Fig 6

```python
from viva_meta_modelers_guide.core import build_core
from viva_meta_modelers_guide.compile import compile_composite
from viva_meta_modelers_guide.handler_envs import ENVS
from process_bigraph import Composite
import json

core = build_core()
semantic = json.load(open(".../fig06-disintegration.composite.json"))["state"]

for env in ("fig06-coarse", "fig06-kinetic"):
    ex = compile_composite(semantic, ENVS[env], core)   # ⟦C⟧_H
    c = Composite({"state": ex}, core=core); c.run(10)
    print(env, c.state["coarse"]["biomass"])
# fig06-coarse  -> 5.000   (linear yield)
# fig06-kinetic -> 3.333   (saturating kinetics) — same interface, different mechanism
```

Materialize every figure's executable with `python scripts/build_executables.py`
(writes `composites/*-executable*.composite.json`, discoverable + `/viva-run`-able).

## Adding a handler

1. Write an executable `Process` whose `inputs()`/`outputs()` return the **exact
   port names + types** of the target signature (config-independent dicts), with a
   real `update(self, state, interval)` returning per-step deltas. Put it in a
   top-level `handlers*.py` module (auto-registered at `local:<ClassName>`).
2. Add/extend an environment in `handler_envs.py`: `{DraftName: {"handler": ...,
   "config": {...}, "init": {"store.leaf": value}, "refine": {...}}}`. `init`/`refine`
   set `_default` (process-bigraph's realize initialises from `_default`, not
   `_value`).
3. `check_conformance` must be ✓; `compile_composite` must build + run; add the
   case to `scripts/build_executables.py::BUILD` and it is covered by
   `tests/test_compilation.py` automatically.

The same signature can later be handled by a **real external simulator** (COBRA/
dFBA, tellurium/COPASI, …) wrapped as a Process — the swap is exactly a new,
conforming handler, with the interface preserved by law 2.
