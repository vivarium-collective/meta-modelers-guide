# Runnable Figures — Deep Scientific Pass

**Status:** approved design (pilots: figs 4 & 5). Date: 2026-08-26.

## Goal

Make each paper figure's composite **fully runnable** and demonstrate the
principle it describes, with: (1) executable dynamics, (2) a dynamic / time-series
visualization, (3) a test that asserts the demonstrated principle, and (4) the
composed a/b figure kept in sync. Roll out figure-by-figure after proving the
recipe on two pilots.

## Background (current state, from the runnability survey)

Every `workspace/studies/fig-0N/study.yaml` baseline points at a **draft**
composite (typed ports, no dynamics) for figs 1–8; figs 9–11 baselines are
already runnable rewrite processes. Separately, `scripts/build_executables.py`
compiles a `figNN-executable` per figure (real handlers + `DynamicsPlot`/
`DynamicsMovie`) via `compile.py`'s functor, but **no study references those
executables**, so the dynamics + time-series viz exist yet are never run or
rendered from a study. Figs 9–11 additionally render a snapshot montage from
their runnable baseline.

## The reusable recipe (per figure)

1. **Runnable composite** — executable dynamics + an emitter + `default_n_steps`
   (the shape figs 9–11 already use), seeded with an initial state that exercises
   the principle. Reuse the existing `figNN-executable` handlers where they exist;
   write new handlers only where the principle is unimplemented.
2. **Wire the study** — the study runs the runnable composite (a run config or a
   runnable baseline), so `default_n_steps` + emitter produce a trajectory.
3. **Dynamic viz** — a `DynamicsPlot` (time-series) or `DynamicsMovie` rendered as
   a study artifact, chosen to make the principle legible over the run.
4. **Test** — a pytest asserting the specific causal claim the figure makes.
5. **Figure sync** — re-render the composed a/b figure if anything visible changed;
   the published b-panel stays the draft *signature*, the runnable model +
   time-series is the demonstration behind it.

## Pilot A — Figure 4: environment → interface ports

**Principle:** the environment's fields drive the cell's interface ports.

- **Dynamics (exist):** `SpatialDiffusion` (D·∇² on a length-9 `map[float]`
  lattice) + `SingleCellSpatial` (reads local field → uptake→mass, traction,
  up-gradient chemotactic drift; writes flux/traction back) — `handlers_fig04.py`.
- **Scenario:** seed `environment.chemical_field` as a nutrient **gradient** (high
  one side). Run: field diffuses; the cell's `uptake` tracks its local
  concentration, `mass` accumulates under supply, the cell **drifts up-gradient**.
- **Viz:** time-series of `{local field, uptake, mass, traction, drift}`.
- **Test** `test_fig04_env_drives_interface`: higher env field ⇒ higher uptake &
  mass gain; net drift is toward the higher-field side.
- **Effort:** mostly plumbing (dynamics already implemented + covered by
  `test_compilation`/`cellular_interface_spatial`); add runnable wiring + viz +
  the dedicated causal test.

## Pilot B — Figure 5: viability slides → coarse⇄fine grain switch

**Principle:** a process is swapped between grains as a function of viability.

- **New process `GrainSelector`:** reads `viability`, writes `active_grain`.
  **Decision: low viability → `fine` grain** (a stressed/declining cell needs the
  detailed model to resolve its regime); viability above threshold → `coarse`
  (the cheap linear model suffices).
- **What slides viability — decision: a simple external stress ramp** (clean,
  controllable), driving viability down across the run.
- **Runnable coarse/fine:** reuse `CoarseMetabolism` (linear yields) as coarse and
  `KineticMetabolism` (Michaelis–Menten) as fine, each **gated** on `active_grain`
  (the inactive grain returns a no-op) so exactly one runs per tick.
- **Demonstration:** viability ramps down; at the threshold `active_grain` flips
  `coarse`→`fine`; the fine process takes over the interface output
  (biomass/energy) at higher fidelity.
- **Viz:** time-series of `{viability, active_grain, biomass}`, switch point marked.
- **Test** `test_fig05_grain_swap`: crossing the viability threshold flips
  `active_grain` and hands control to the other process (previously-active goes
  inert).
- **Effort:** genuine new development — the viability-driven grain switch does not
  exist anywhere today.

## Rollout (after pilots approved)

Apply the recipe to figs 3, 6, 7, 8 (wire existing executables + their
DynamicsPlot/Movie + add a principle test each), then 1 & 2 (need executables
from scratch), then enrich 9–11 with time-series viz. Subagent-driven, one figure
at a time, user approves each. Figs 1 & 2 (pure static diagrams) may reduce to a
minimal illustrative run or be explicitly scoped out.

## Non-goals

- Not changing the published a/b figure *signatures* (the drafts remain the paper
  figures); the runnable models are the demonstration behind them.
- Not a physics-accurate simulator per figure — toy-real dynamics that correctly
  exhibit the stated principle, verified by a test.
