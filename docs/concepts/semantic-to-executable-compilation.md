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

---

## Status: the whole paper is executable

Every one of the 11 figure composites now has a conforming handler environment and
a materialized executable (`scripts/build_executables.py`); each compiles (law 1),
preserves its interface (law 2), and runs with non-trivial dynamics (law 3).
Coverage: Fig 4b, 5, 6, 7, 8, 9a, 9b, 10-1, 10-2, 10-3 (Fig 4a is illustrative).

### Rewrite handlers — the control-flow half (law 2′)

Fig 10 (division, development, evolution) is where composition stops being a static
handler swap. Most Fig 10 drafts still conform normally, but `Divide`'s draft
signature is a placeholder while the composite wires it as `biomass ⇒ biomass_1,
biomass_2, cell_count`. A handler marked `REWRITE = True` (subclass of
`RewriteHandler`) is checked against the node's **wiring** rather than the draft
signature — **law 2′** — and fires a discrete event (`DivisionRewrite`: at a
cell-cycle time the parent biomass partitions into two daughters and `cell_count`
increments). The interface itself is still preserved: the daughter/biofilm/variant
subtrees are pre-declared in the semantic composite, so `interface_of` is unchanged;
the handler animates a pre-declared post-structure. True runtime node-insertion is a
further extension.

### Real external simulators as handlers (Phase 2)

The same signature can be handled by a real engine. `FBAMetabolism`
(`handlers_fig06_fba.py`) bridges **COBRApy** flux-balance analysis to the Fig 6
`CoarseGrainedMetabolism` interface: it sets the nutrient uptake bound from the
incoming flux and solves the LP for max biomass (capped by a network constraint).
Fig 6 now demonstrates law 4 with three handlers over one interface — coarse
(linear, 5.0), kinetic (saturating, 3.33), FBA (LP-constrained, 4.0). `cobra` is an
optional dependency (`pip install -e .[simulators]`); it is imported lazily, so
discovery and materialization work without it and the tests skip when it is absent.

### The whole cell (Phase 4)

`wholecell.py` composes the figures into one multiscale executable —
cell–environment coupling (Fig 5) + viability-gated metabolism (Fig 6) + a
`ViabilityMonitor` (Fig 4 bounds) + division (Fig 10) + disintegration (Fig 6). One
run closes the paper's arc: the cell grows on nutrients, divides when biomass
crosses a threshold (`cell_count` 1→2), then a thermal shock pushes temperature out
of the viability band, viability collapses, and biomass decays into molecular debris
(cell→molecular). `scripts/run_wholecell.py` records the trajectory.

### Ontology-typed interfaces + provenance (Phase 5)

`ontology.py` binds the interface vocabulary to real terms — GO for processes
(metabolism `GO:0008152`, cell division `GO:0051301`, …), PATO for physical
qualities (temperature `PATO:0000146`), CBO for cell behaviours — via an explicit
quantity map and a keyword resolver over process kinds. Conformance is
ontology-aware (`_type_compatible` accepts two differently-named types that denote
the same term), and every materialized executable carries a provenance block naming
each handler's biological-process term.
