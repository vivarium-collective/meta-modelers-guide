# A meta-modeler's guide — made executable

**A cellular interface is not just a modeler's convenience — it is a testable
biological hypothesis about which interactions govern a cell's fate, and staying
alive is what makes the boundary real.**

Every figure of *A meta-modeler's guide to the cellular interface* is written twice:
once as an inert, typed interface contract, and once as a running simulation the
compiler installs behind the *identical* ports. A cellular description stays valid
only while its exchange variables sit inside a **viability bound** — that boundary is
the locus of minimal agency, and composition is not a fixed final architecture but an
ongoing practice: **connect** two interfaces where their assumptions hold (environment
and cell–cell coupling), **cut the model open** at the interface when those
assumptions fail and the right description drops to molecules (disintegration), and
**coarse-grain** a resolved network back into a lumped exchange when organization
re-emerges (autopoiesis, and disintegration's grain-swap run in reverse).

Because the boundary provably does not move under compilation, mechanisms of any
grain become swappable behind it: a lumped yield, saturating Michaelis–Menten
kinetics, or a genome-derived FBA solver are three interpretations of one unchanged
interface. And structural events like cell division are not special cases bolted on —
they are first-class **rewrites of the composition itself**.

- 🔬 **[Explore the live dashboard →](https://vivarium-collective.github.io/meta-modelers-guide/dashboard/)** — every draft, executable, and study, browsable, no install.
- 📄 **[From Draft to Living Cell — the investigation report →](https://vivarium-collective.github.io/meta-modelers-guide/investigations/draft-to-living-cell.html)**

---

## The flagship exhibit: Fig 6 is disintegration — playable, and three grains deep

The sharpest single view is **Fig 6 — disintegration**. It is two things at once.

**Playable.** A scripted thermal shock pushes the cell outside its viable band:
viability collapses, viability-gated metabolism halts, and biomass decays into
molecular debris — a cell-to-molecular **level shift** you can step through in the
Composite Explorer. Play it: `fig05-disintegration-dynamics`.

**Structural, three grains deep.** The metabolic interface behind that collapse,

    nutrients ⇒ biomass, energy, entropy, secretions

is realized by **three different mechanisms overlaid on one unchanged boundary** —
three grains of the same disintegration/coarse-graining pattern (law 4):

| Grain | What it is | Distinct behavior |
|---|---|---|
| `CoarseMetabolism` | a lumped linear yield | biomass tracks nutrients, no byproducts |
| `KineticMetabolism` | saturating Michaelis–Menten kinetics | biomass saturates as nutrients rise |
| `FBAMetabolism` | **real COBRApy flux-balance analysis** on `e_coli_core` | with an O₂/respiratory cap, carbon **overflows to acetate** — only the genome-derived network puts a secretion byproduct on the interface |

Three grains, three genuinely different trajectories, **one interface that never
moves** — and it is the disintegration collapse that forces the description down to
this molecular grain in the first place.

**The interface is enforced, not just described.** That guarantee traces back to the
**cellular interface itself** (Fig 4, law 1 conformance): a fourth, *non-conforming*
handler — `NonConformingMetabolism`, a concrete impostor that renames `biomass` to
`growth` with the wrong type and drops `energy`/`entropy`/`secretions` — is refused at
compile time with a **`CompileError` that names every missing port**. The impostor
itself lives in the metabolism code that disintegration exercises, cross-referenced
here: conformance is not a convention you are trusted to follow; it is a typing
judgment the compiler enforces at the boundary Fig 4 draws.

**And composition is rewritten, not just connected.** The same discipline extends to
structural change: cell **division** (Fig 10, growth-and-division) is a genuine,
mass-conserving place-graph rewrite — one cell node becomes two — checked by a fifth
law (rewrite preservation), not a special case bolted onto the interface.

## The compiler and its laws

The compiler `compile_composite(C, H, core)` walks a semantic composite `C`, and for
each draft node installs its handler from the environment `H`, **leaving every store
and every wire untouched**. It is a thin adapter over the standalone
[`viva-compiler`](https://github.com/vivarium-collective/viva-compiler) package
(this workspace injects an ontology-aware type check). Four laws — every one enforced
in `tests/test_compilation.py`:

1. **Conformance.** Compilation is *defined only if* the handler supplies every
   interface port of the signature with a compatible type. A non-conforming handler
   raises `CompileError`. *(the impostor above)*
2. **Interface preservation.** The compiled composite has the *same* interface as the
   draft — identical port names and identical store paths they wire to. The mechanism
   changes; the boundary is byte-identical (unless the environment *declares* a
   representation refinement, e.g. a scalar field → a spatial grid for Fig 5).
   *(`test_env_conforms_compiles_and_runs`)*
3. **Executability.** The compiled composite builds into a running `Composite` and
   produces non-trivial dynamics — while the semantic draft, actually run, does
   nothing. *(every study pairs its mechanism against a `draft-is-inert` control)*
4. **Handler independence.** Any two conforming handler environments yield two valid
   executables that *share one interface* — the swap is invisible from outside.
   *(`test_fig6_handler_independence`: Fig 6's three mechanisms)*

And a fifth, **Law 2′ (rewrite preservation)**: a handler marked as a structural
rewrite is checked against the node's *wiring* rather than a placeholder signature,
and still preserves the interface — this is how cell **division** becomes a
first-class event that turns one cell node into two (`test_fig10_division_is_event_driven`).

## The 9 studies, in the paper's own order

**contract → coupling → cut-open / mechanism-swap → molecular grain → composition →
rewrite → the whole cell.**

1. **[cellular-interface](workspace/studies/cellular-interface/study.yaml)** (Fig 4) —
   the cell's typed exchange ports (chemical mol·s⁻¹, mechanical N, electrical A,
   thermal W, growth hr⁻¹, viability), with *no* mechanism yet. Home of law 1: the
   impostor above is rejected here.
2. **[cell-environment-coupling](workspace/studies/cell-environment-coupling/study.yaml)**
   (Fig 5) — the interface closes into a genuine sense/act loop over a real diffusing
   spatial field; the cell reshapes the gradient it depends on (niche construction).
3. **[cell-cell-coupling](workspace/studies/cell-cell-coupling/study.yaml)** (no
   figure of its own) — two cells wired over one shared nutrient store negotiate
   viability: competition starves the weaker cell; cross-feeding (a different
   handler, same interface) keeps both alive.
4. **[disintegration](workspace/studies/disintegration/study.yaml)** (Fig 6, **the
   flagship**) — the interface cut open: the playable viability collapse plus the
   three-grain metabolism swap above.
5. **[molecular-interfaces](workspace/studies/molecular-interfaces/study.yaml)**
   (Fig 7) — one level further down: an F1Fo ATP-synthase mechanism drives all four
   physical channels from one coupled proton flux.
6. **[biomolecular-complementarity](workspace/studies/biomolecular-complementarity/study.yaml)**
   (Fig 8) — six place-graph levels deep, interface preserved at the deepest nesting
   in this codebase.
7. **[autopoiesis](workspace/studies/autopoiesis/study.yaml)** (Fig 9) — metabolism,
   containment, and replication compile into mutual closure toward a minimal cell:
   the grain-swap pattern coarse-grained back up.
8. **[growth-and-division](workspace/studies/growth-and-division/study.yaml)**
   (Fig 10a,b) — growth drives the cell's own DNA past a threshold; crossing it fires
   a genuine, mass-conserving place-graph rewrite — one cell node becomes two.
9. **[development-and-evolution](workspace/studies/development-and-evolution/study.yaml)**
   (Fig 10c-f) — biofilm nesting and selection as event-driven rewrites, explicitly
   caveated (gate: `needs_calibration`) — the paper's own "open and substantial
   challenge."

A closing **capstone**, assembled by hand in the figures' style (not
compiler-emitted), carries the disintegration grain-swap up to one whole cell: it
takes up nutrients and grows, divides once when its biomass crosses a threshold, then
— under a scripted thermal shock that pushes it out of the viable band — loses
viability and disintegrates into molecular debris. Because metabolism is swappable
behind its fixed interface, **that whole cell runs three ways** (coarse / kinetic /
FBA give three distinct life histories).

## What this is — and what it is not

Honesty about scope is part of the claim:

- **Conformance is structural** — port names, types, and wiring. It is *not* a check of
  units, invariants, or runtime behavior. Units are name-only labels on ports
  (documentary, not machine-enforced); the compiler guarantees the ports line up, not
  that a mechanism honors its contract's *intended* behavior once running.
- **Constants are illustrative, not calibrated** — handlers are "toy-real" (see
  glossary): plausible numbers, not fitted parameters. The dynamics demonstrate the
  *pattern* (ultrasensitivity, closure, division, disintegration), not a
  quantitatively validated organism.
- **The playable disintegration composite and the whole-cell capstone are both
  assembled by hand** in the figures' style (`fig05-disintegration-dynamics`,
  `wholecell.py`) — neither is compiler-emitted from a study's drafts, and the whole
  cell is not tuned to any real cell's physiology.
- **`development-and-evolution` is the most caveated study** (gate:
  `needs_calibration`) — selection is a single fixed-constant ODE and the "new port"
  a scripted config ramp, honestly labeled as pattern demonstrations of what the
  paper itself calls "an open and substantial challenge."
- **The compiler is the binding stage only.** It installs one conforming mechanism per
  draft. It does not fit parameters, discover mechanisms, or reconcile mechanisms that
  disagree.

## Glossary

- **Draft** — an interface with a behavior contract but *no dynamics*: typed ports +
  intent, an inert update. It builds and renders, but does nothing if run.
- **Handler** — an executable process that implements a draft's interface with real
  dynamics. The compiler installs one handler per draft.
- **Conformance** — a handler conforms to a signature when it supplies every interface
  port with a compatible type. Non-conforming handlers are refused (`CompileError`).
- **Toy-real** — a mechanism that runs and produces the *right qualitative behavior*
  from plausible, illustrative constants rather than fitted ones: real dynamics,
  uncalibrated magnitudes.
- **Grain** — the level of description at which an interface is realized (a lumped
  process vs. a resolved network). A *grain swap* changes the mechanism's resolution
  while the interface stays fixed — Fig 6.

---

## Working with this workspace

Everything below is the plumbing — the workspace, dashboard, and skills that produce
the exhibits above. The science is the part above the fold.

    bash scripts/serve.sh           # open the dashboard locally
    python3 scripts/lint-workspace.py
    python scripts/build_executables.py   # materialize every figure's executable

This is a Process-Bigraph research workspace scaffolded from
[viva-template](https://github.com/vivarium-collective/viva-template). The compiler
lives in the standalone [`viva-compiler`](https://github.com/vivarium-collective/viva-compiler)
package; the full derivation (the algebraic-effects framing, the conformance
judgment, and the worked Fig 6 example) is in
[`docs/concepts/semantic-to-executable-compilation.md`](docs/concepts/semantic-to-executable-compilation.md).

> 🤖 **Using an AI coding assistant (Claude Code / Cursor / …)?** Hand it
> **[docs/first-run-agent-guide.md](docs/first-run-agent-guide.md)** — a gated runbook
> that takes an agent from a clean clone to a running vivarium-workbench with one of
> this workspace's composites open in the viewer, then on to authoring studies and
> contributing.

### Reports

- [From Draft to Living Cell](https://vivarium-collective.github.io/meta-modelers-guide/investigations/draft-to-living-cell.html) — the full investigation: 9 studies, in the paper's own order, from the typed interface to the living, dividing, dying whole cell.
- [Model-building under contract](docs/model-building-under-contract.html) — a worked, self-explaining walkthrough of the agentic loop building one `draft-to-living-cell` model under contract (tests locked → build → result → audit), with real metrics.

### Skills (the viva-superpowers Claude Code plugin)

The [viva-superpowers](https://github.com/vivarium-collective/viva-superpowers) plugin
provides skills that drive the canonical PR flow:

- `/viva-study <slug>` — start a study (8-section spec, `phase: Design|Build|Simulate|Evaluate|Decide`).
- `/viva-investigation <slug>` — group related studies into an investigation (DAG via `pipeline_gate.prerequisites`).
- `/viva-expert <tool>` — wrap a simulator as a process-bigraph Process or Step (sibling repo + tests + report). Pass `--lightweight` to write in-workspace instead.
- `/viva-expert <name> <tools…>` — wire wrapped simulators into a composite.
- `/viva-viz` — generate a Visualization from a natural-language description.
- `/viva-report` — regenerate `workspace/reports/index.html`.

Decide-phase studies can record `followup_proposals[]`; seed a child study from any
proposal with `/viva-study seed-from-followup <parent>/<proposal_id>`.

### Layout

Project code lives at the repo root; research state is grouped under `workspace/`
(the `.pbg/` machine state stays at the root like `.git/`). Directory locations come
from the `layout:` map in `workspace.yaml` — edit it to move things.

- `workspace.yaml` — canonical state (validated against `.pbg/schemas/workspace.schema.json`).
- `meta_modelers_guide/` — the Python package (`core.py` exposes `build_core()`; `compile.py`, `handlers*.py`, `handler_envs.py`, `wholecell.py`, `structural.py`).
- `scripts/` — `lint-workspace.py`, `serve.sh`, `build_executables.py`, helpers.
- `workspace/studies/`, `workspace/composites/`, `workspace/references/`, `workspace/datasets/` — research artifacts.
- `workspace/notes/` — friction logs, walkthroughs, ADRs. **Files under `notes/` survive cleanup sweeps by default** (see `workspace/notes/README.md`).
- `.pbg/schemas/` — JSON schemas the lint + dashboard validate against.

### Cleanup conventions

Cleanup PRs (`chore(cleanup): …`, `chore(repo): trim …`) routinely remove generated
files, one-shot scripts, and stale planning docs. Two locations are off-limits to bulk
cleanup: `workspace/notes/**` and `workspace/references/notes/**` (per-paper literature
notes, used by the findings protocol). If a specific file is genuinely obsolete, delete
it in its own commit with a one-line justification per file.

<!-- BEGIN dashboard -->
> ## 📊 [**Live dashboard →**](https://vivarium-collective.github.io/meta-modelers-guide/dashboard/)
> Browse every investigation & study interactively, or read the [published investigation reports](https://vivarium-collective.github.io/meta-modelers-guide/). Auto-published from `main` on every merge.
<!-- END dashboard -->

<!-- BEGIN:dashboard -->
<!-- generated by `vivarium-workbench gen-readme` — edit the source, not this table -->

> ### 🔬 [Explore the interactive read-only dashboard →](https://vivarium-collective.github.io/meta-modelers-guide/dashboard/)
>
> Every composite, study, and result — browsable in your browser, no install required.
> Published from `main` by the `publish-dashboard` workflow (allow a few minutes after the first push).
<!-- END:dashboard -->

### Composites & investigations

These two tables are generated from the workspace by `vivarium-workbench gen-readme` —
the same sets the dashboard shows — and kept fresh by CI (`workspace-ci` runs
`gen-readme --check`). Regenerate any time with
`vivarium-workbench gen-readme --workspace .`.

#### Composites

<!-- BEGIN:composites -->
<!-- generated by `vivarium-workbench gen-readme` — edit the source, not this table -->

| Composite | What it is |
|---|---|
| `A Biological Process Bigraph` | Fig 1c — A biological process bigraph: processes are wired into the store hierarchy, each assigned a specific mechanism declared in its contract. |
| `A Molecular Mechanism` | Fig 6b/6c — a molecular mechanism as a process with typed physical channels. |
| `A Process` | Fig 1a — A process: typed input and output ports plus a configuration whose update method maps inputs to a delta over the outputs. |
| `A Store Hierarchy` | Fig 1b — A store hierarchy: the place graph of biological containment from tissue down to molecules, each store typed with its biological unit. |
| `Biofilm Development — Draft Interface` | Fig 10 (panels c/d) — biofilm development as a hierarchical reorganization. |
| `Biofilm Development — Live Topology` | Fig 10 (biofilm) as a genuine place-graph rewrite: a founder cell colonizes (sibling cell nodes added one at a time up to capacity), then the mature community secretes extracellular matrix (an ECM no… |
| `Cell Disintegration` | Fig 5b — cell disintegration as a grain-swap equivalence. |
| `Cell Division — Draft Interface` | Fig 9 (panel b) — division as a compositional rewrite. |
| `Cell Division — Live Topology` | Fig 9 as a genuine place-graph rewrite: chromosome segregation then cell division via Milner reaction rules over a tree[node] store. |
| `Cell–Cell Coupling` | Paper §Cell–cell coupling (no dedicated figure). Two cell agents are wired to one shared environmental nutrient store: each senses the pool and depletes it, so their interfaces are coupled not only t… |
| `Cell–Environment Coupling` | Fig 4b — cell–environment coupling. |
| `Disintegration (playable)` | Fig 5a — cell disintegration as a playable trajectory: a thermal shock pushes the cell past its viability bound; viability collapses, viability-gated metabolism halts, and biomass decays into molecul… |
| `Evolution — Draft Interface` | Fig 11 (panels e/f) — evolution reshapes the composition itself. |
| `Evolution — Live Topology` | Fig 11 (evolution) as a genuine place-graph rewrite: a wildtype population establishes (organism nodes added), a fitter mutant arises, then a selection sweep adds mutant offspring and prunes wildtype… |
| `Grain Swap` | Fig 5b — grain swap on viability. |
| `Interaction Modalities` | Fig 3a — four interaction-modality cards of the cellular interface: nutrient exchange (chemical flux), motile force (mechanical), growth rate, and electrical signaling. |
| `Nested Molecular Hierarchy` | Fig 7b — molecular compositions as a nested hierarchical composite. |
| `Self-Organization & Coarse-Graining` | Fig 8a — self-organization, coarse-graining, and autopoiesis. |
| `The Cellular Interface` | Fig 3b — the minimal cellular interface. |
| `The Minimal Cell` | Fig 8b — the minimal cell: the three columns of Fig 8a wired into one composite. |
| `cell-sorting-spatial` | The sorting study flagship: a mixed 8x8 checkerboard of alternating-type 5x5-px CPM cells (64 cells total, 32 type-1 / 32 type-2, on a 70x70 lattice) demixes under differential-adhesion contact energ… |
| `cellcell-compete` | Two competitor CPM cells (CpmColonyField) share one 60x60 glucose field and race for the same nutrient via independent per-cell dFBA. Both cells run the microaerobic e_coli_core role ('competitor'):… |
| `cellcell-compete-div` | M7b dividing-population competition: two DIVIDING founder LINEAGES race for one glucose pool supplied at a fixed level from the boundary (Dirichlet BC value 8.0, chemostat-like), each cell growing by… |
| `cellcell-compete-div-slowmono` | M7b competition CONTROL (slow-lineage monoculture): the cellcell-compete-div slow lineage (glucose_vmax 4) ALONE under the byte-identical boundary glucose supply (Dirichlet 8.0), maintenance (0.10) a… |
| `cellcell-compete-mm` | Cell-cell (colony) interface-substitutability twin of cellcell-compete: BYTE-IDENTICAL CpmColonyField ports and the same 60x60 shared glucose field, but each cell's INTERNAL per-cell metabolism is sw… |
| `cellcell-crossfeed` | A tuned two-role cross-feeding pair (CpmColonyField) on a shared 60x60 grid demonstrating a metabolic handoff. |
| `cellcell-crossfeed-knockout` | Secretor-knockout necessity control for the cross-feeding regime: the cellcell-crossfeed composite with the glucose->acetate SECRETOR cell removed entirely, so no acetate is ever produced anywhere on… |
| `cellcell-crossfeed-realistic` | M7a realistic-diffusivity control for the cross-feeding regime. |
| `cellcell-executable-compete` | Executable compilation of cellcell-coupling under handler environment 'cellcell-compete' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `cellcell-executable-crossfeed` | Executable compilation of cellcell-coupling under handler environment 'cellcell-crossfeed' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `cellular-interface-spatial` | The spatial translation of the cellular-interface study. |
| `condensate-cahn-hilliard` | The condensate study flagship: a scalar field phi on a 64x64 fields grid, seeded with near-critical noise (mean 0, uniform +/-0.025 -- the exact np.random.default_rng(0).uniform(-0.025, 0.025, size=(… |
| `development-evolution-no-mutation` | Identical to development-evolution-spatial except mutate=false (a BOOLEAN flag, not a mut_sigma=0.0 float override, which bigraph_schema silently drops): the heritable vmax trait cannot vary across d… |
| `development-evolution-no-selection` | Identical to development-evolution-spatial except selection=false: the vmax trait still mutates on division (raw variance builds up, var_vmax > 0) but every cell's dFBA glucose uptake uses the FIXED… |
| `development-evolution-spatial` | A growing CPM colony (CpmEvolution, study 8's dFBA growth/division reused unchanged) carrying a heritable per-cell glucose-uptake trait (vmax) that mutates on division (Gaussian, sigma=0.3) and IS un… |
| `disintegration-spatial` | The disintegration study flagship: a single coherent CPM cell (CpmDisintegration, no metabolism/cobra path) sits centered on a shared 60x60 fields grid inside a radial acetate gradient -- the stresso… |
| `fig01-process-bigraph` | Fig 1 — Process bigraph (Fig 1b): place-graph nodes n1..n6 with processes p1, p2, p3 connecting them through typed ports — the process-graph replacement for the Milner link graph's hyperedges (Fig 1a… |
| `fig01b-store` | Fig 1b — A store: a typed container that holds a unit of shared state, accessible to processes. |
| `fig01c-place-graph` | Fig 1c — The place graph: hierarchical containment relations among stores, independent of process interactions. cell ⊃ {cyto ⊃ {rib, nuc ⊃ DNA}, mem ⊃ chnl}. |
| `fig01d-process` | Fig 1d — A process: typed input and output ports plus a configuration that maps inputs to outputs. |
| `fig02b-composite-process` | Fig 2b — Composite process — the `cell`: cyto ⊃ {rib, nuc ⊃ DNA}, mem ⊃ chnl, with grow / express / transport processes and nutrient/signal inputs + shape output. |
| `fig03b-executable` | Executable compilation of fig03b-cellular-interface under handler environment 'fig03b' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig03b-executable-alt` | Alternate executable compilation of fig03b-cellular-interface: the SAME typed cellular-interface contract realized by a SECOND, independent handler (CooperativeCellularInterfaceHandler) with a differ… |
| `fig04-executable` | Executable compilation of fig04-cell-environment under handler environment 'fig04' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig05-executable-coarse` | Executable compilation of fig05-disintegration under handler environment 'fig05-coarse' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig05-executable-fba` | Executable compilation of fig05-disintegration under handler environment 'fig05-fba' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig05-executable-kinetic` | Executable compilation of fig05-disintegration under handler environment 'fig05-kinetic' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig06-executable` | Executable compilation of fig06-molecular-mechanism under handler environment 'fig06' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig07-executable` | Executable compilation of fig07-nested-hierarchy under handler environment 'fig07' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig08a-executable` | Executable compilation of fig08a-coarse-graining under handler environment 'fig08a' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig08b-executable` | Executable compilation of fig08b-minimal-cell under handler environment 'fig08b' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig09-executable` | Executable compilation of fig09-division under handler environment 'fig09' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig10-executable` | Executable compilation of fig10-development under handler environment 'fig10' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig11-executable` | Executable compilation of fig11-evolution under handler environment 'fig11' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `growth-division-spatial` | A single CPM cell (CpmGrowthDivision) grows via per-cell dFBA on an abundant, uniform 60x60 glucose field (spatio-flux DiffusionAdvection) and divides at a volume threshold using the native engine ca… |
| `molecular-equal-diffusion-control` | The molecular-interfaces study's causal control for molecular-turing-pattern: IDENTICAL Gray-Scott setup (same 128x128 grid, same static np.random.default_rng(1) seed_uv(n=128, seed=1) u/v seed, same… |
| `molecular-thermal-graded` | The molecular-interfaces study's thermal-channel demonstration: the same molecular-turing-pattern Gray-Scott setup (128x128 grid, static np.random.default_rng(1) seed_uv(n=128, seed=1) u/v seed, cano… |
| `molecular-turing-pattern` | The molecular-interfaces study flagship: a Gray-Scott reaction-diffusion system on a 128x128 fields grid, seeded near-uniform (u~=1, v~=0 plus small Gaussian noise, plus 5 small nucleation patches of… |
| `overview-multiscale-composite` | Fig 1b — The multiscale draft composite: tissue ⊃ {fields, cell_population, cells ⊃ cell ⊃ molecules}. Molecular ODEs, FBA metabolism, structural packing, growth/division, and tissue-scale diffusion… |
| `protocell-autopoietic` | The autopoiesis study flagship: a scalar membrane-density field phi on a 64x64 fields grid, seeded with a deterministic Gaussian-annulus ring (the exact seed_annulus(n=64) draw from meta_modelers_gui… |
| `protocell-autopoietic-v2` | v2 GENUINELY-LOCAL autopoiesis (peer-review M4 answer) -- the mechanism-level realization. |
| `protocell-autopoietic-v2-open` | v2-OPEN -- the EXTERNALLY-DRIVEN (open-system) variant of protocell-autopoietic-v2, the explicitly named remaining EMERGE step, built and MEASURED. Same two local fields on a 64x64 periodic grid (mem… |
| `protocell-vesicle-control` | The autopoiesis study negative control: IDENTICAL seed and process wiring to protocell-autopoietic (same static Gaussian-annulus phi seed, same Protocell process, same canonical D/k_decay/thr/dt/step… |
| `single-cell-in-a-field` | The flagship spatial sense/act loop: a single CPM cell (CpmCellField) sits in a left-low-to-right-high glucose gradient on a shared 60x60 fields grid, diffusing under spatio-flux DiffusionAdvection. |
| `single-cell-in-a-field-chemotaxis` | CHEMOTAXIS variant of the flagship: the same single CPM cell (CpmCellField) in the same left-low-to-right-high glucose gradient on the shared 60x60 spatio-flux field, but now the cell ACTS on what it… |
| `single-cell-in-a-field-mm` | Interface-substitutability twin of the flagship: BYTE-IDENTICAL cell<->field ports, but the internal metabolism behind CpmCellField is swapped from constraint-based dynamic-FBA (e_coli_core, O2-cappe… |
| `single-cell-in-a-field-o2uncapped` | O2-UNCAPPED mechanism control for the flagship single-cell-in-a-field: byte-for-byte identical to that composite EXCEPT the CpmCellField oxygen bound is lifted (oxygen_vmax = 1000.0, so EX_o2_e is ef… |
| `single-cell-in-a-field-steadystate` | M7d steady-state regime for the flagship single-cell-in-a-field — byte-for-byte identical to the flagship EXCEPT the CpmCellField adds three cell-independent steady-state terms so the pure-transient… |
| `whole-cell` | The composed whole cell — the paper figure mechanisms (thermal environment, uptake, a selectable Fig 5 metabolism [coarse \| kinetic \| FBA], a viability monitor, DNA-threshold division Fig 10-1, and d… |
<!-- END:composites -->

#### Investigations

<!-- BEGIN:investigations -->
<!-- generated by `vivarium-workbench gen-readme` — edit the source, not this table -->

| Investigation | Research question |
|---|---|
| [From Draft to Living Cell _(running)_](https://vivarium-collective.github.io/meta-modelers-guide/investigations/draft-to-living-cell.html) | The paper treats a biological interface as a scientific object — something you can compose with other entities, swap the mechanism behind, and watch emerge from the inside. |
| [Paper Figures (final — download here) _(complete)_](https://vivarium-collective.github.io/meta-modelers-guide/investigations/paper-figures.html) |  |
<!-- END:investigations -->
