# Semantic → Executable Compilation (algebraic effect system)

Status: approved design · 2026-08-15

## Goal

Harden the `paper-figures` investigation by demonstrating that the **semantic**
(draft-process) figures **compile down to executable** process-bigraph composites
with real (non-draft) simulation dynamics — in a principled, law-backed way. The
framing is an **algebraic effect system**.

## The framework

- **Effect signature = a draft process.** A `DraftProcess` declares an operation
  signature: typed input/output ports (`op : (in:τ) ⇒ (out:τ)`) plus a contract
  (`senses`/`affects`/`constraints` = pre/post/invariants). No `update` → inert.
  A semantic composite is a *term* over these operations, wired through a typed
  store (the context).
- **Handler = an executable Process.** A handler `H` for signature `S` is a real
  `Process` with `ports(H) ⊇ ports(S)` and a genuine `update`.
- **Handler environment.** A map assigning each signature a handler + config
  (+ optional initial-store overrides).
- **Compilation = the functor `⟦C⟧_H`.** Walk semantic composite `C`; replace each
  `local:<Draft>` node with its handler `local:<Handler>` (config-instantiated),
  **leaving every store and wire untouched**.

### Laws (tested)

1. **Conformance** `H ⊢ S`: `⟦C⟧_H` defined only if every signature port is present
   on the handler with a compatible type.
2. **Interface preservation (homomorphism)**: the **external interface** —
   process port names + the store leaves they wire to — is preserved by `⟦C⟧_H`.
   Internal **representation refinements** (e.g. a scalar `concentration` field →
   a 2-D grid array for a real spatial handler) are permitted ONLY when declared
   explicitly in the handler env (`refine`), never as an accidental structural
   change. For figures with no `refine`, the store tree is byte-identical
   (the strong form). This is the paper's "same interface, different internal
   organization."
3. **Executability**: `⟦C⟧_H` builds into a `Composite` and produces non-trivial
   dynamics (observables change over steps); `C` was inert.
4. **Handler independence**: two conforming handler sets yield two valid
   executables sharing one interface (Fig 6 grain-swap = coarse FBA vs kinetic).

## Modules (all top-level in `viva_meta_modelers_guide/`)

### `compile.py` (pure; no heavy deps)
- `signature_of(draft_cls) -> Signature{inputs: {port:type}, outputs: {port:type}, contract}`.
- `check_conformance(sig, handler_cls) -> ConformanceReport{ok, missing, type_mismatches}`.
  A handler conforms iff for every signature input/output port `p:τ`, the handler
  has port `p` with type `τ` OR a type that resolves compatibly (equal name, or
  handler type inherits the signature type). Extra handler ports are allowed.
- `compile_composite(semantic_state, handler_env, core) -> executable_state`:
  deep-copy; for each node with `_type=="process"` and address `local:<Draft>`
  where `<Draft>` is in `handler_env`: assert conformance (raise `CompileError`
  with the report on failure), set `address = local:<Handler>`, merge
  `config = {**handler_cfg, **node.config}`, drop `_draft`, KEEP `inputs`,
  `outputs`, `_figure`. Apply the env's `init` overrides to matching store leaves'
  `_value`, and `refine` overrides to matching leaves' schema (e.g.
  `{_type: "array", _value: <grid>}`). Never add/remove/rename a store PATH or a
  wire — only a declared `refine`/`init` may change a leaf's schema/value.
- `interface_of(state) -> {ports: set, wired_store_paths: set}` — the EXTERNAL
  interface (law #2 asserts pre == post). Store *schemas* may differ only at
  declared `refine` paths; paths + wiring must be identical.

### `handlers.py` (top-level module → auto-registered as `local:<ClassName>`)
Toy-real `Process` subclasses, one per signature used by the target figures. Each:
- exposes the **exact draft port names** (so wiring transfers verbatim);
- has a `config_schema` of real parameters (rates, yields…) with defaults;
- `update(state, interval)` computes genuine dynamics (ODE step / stoichiometry /
  relaxation / stochastic step) — NO fabricated constants; build on pb's `ODE`,
  `GillespieSimulation`, `ReactionStep`, `Grow` where useful.

Handler ↔ signature map (target figures):

| Figure | Signature (draft) | Handler(s) |
|---|---|---|
| 4b | CellularInterface | `CellularInterfaceHandler` (exchange + logistic growth + viability from bounds) |
| 5 | ReactionDiffusion | `SpatialDiffusion` — **real minimal** finite-difference Laplacian on a small grid (env `refine`s `environment.chemical_field` scalar → NxN array) |
| 5 | ProductionDegradation | `ProductionDegradationField` (source/sink on the grid) |
| 5 | MechanicalStress | `MechanicalRelax` |
| 5 | SingleCellProcesses | `SingleCellSpatial` (uptake/secretion at the cell's grid cell; updates mass/shape) |
| 6 | CoarseGrainedMetabolism | `CoarseMetabolism` (lumped uptake→biomass/energy/entropy) |
| 6 | CatalyzedReactionNetwork | `KineticReactionNetwork` (mass-action ODE) — the fine grain |
| 9b | MinimalCellContainment | `ContainmentODE` (lipids→membrane) |
| 9b | MinimalCellMetabolism | `MetabolismLinear` (enzymes+nutrients→metabolites+energy) |
| 9b | GeneExpression | `GeneExpressionODE` (genes→proteins) |
| 9b | MinimalCellReplication | `ReplicationODE` (genes+energy→genes) |
| 9b | Diffusion | `DiffusionRelax` (non-spatial metabolite mixing → mean) |
| 9b | Reactions | `MassActionReactions` |

### `handler_envs.py`
`ENVS: dict[str, HandlerEnv]` keyed `"fig04b"`, `"fig05"`, `"fig06-coarse"`,
`"fig06-kinetic"`, `"fig09b"`. Each `HandlerEnv` = `{draft_name: {address, config,
init}}`. `fig06-coarse` handles `CoarseGrainedMetabolism`; `fig06-kinetic` handles
`CatalyzedReactionNetwork` — both over the same Fig 6 interface.

## Materialized executables
`scripts/build_executables.py` runs `compile_composite(load(semantic), ENVS[k])`
and writes `composites/<name>.composite.json`:
`fig04b-executable`, `fig05-executable`, `fig06-executable-coarse`,
`fig06-executable-kinetic`, `fig09b-executable`. Discoverable + `/viva-run`-able.

## Study
`workspace/studies/fig-compilation/` in `paper-figures`: baseline = a semantic
composite; variants = the compiled executables; runs emit time-series; report
card + `behavior_tests`: conformance-passes, compiles, runs-with-dynamics,
interface-preserved, fig6-two-handlers-one-interface. Add to investigation
`studies:` list.

## Concept doc
`docs/concepts/semantic-to-executable-compilation.md`: the definition above,
mapping to process-bigraph, conformance rules, Fig 6 worked example, add-a-handler
guide.

## Tests — `tests/test_compilation.py`
Per env: conformance holds; `compile_composite` builds; N-step run changes ≥1
observable; `interface_of(pre)==interface_of(post)`; fig06 coarse+kinetic both
conform and share interface.

## Non-goals
Bridging external solvers (COBRA/tellurium) — noted as the future handler-swap
path (same signatures). Real spatial PDE for Fig 5 — toy non-spatial relaxation now.
