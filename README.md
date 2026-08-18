# A meta-modeler's guide — made executable

**Every figure of *A meta-modeler's guide to the cellular interface* is written twice:
once as an inert, typed interface contract, and once as a running simulation the
compiler installs behind the *identical* ports.**

A biological model here is specified first as an inert, typed **interface contract** —
which quantities a process exchanges and how it wires to the rest of the cell — and
only *then* compiled, by installing one conforming mechanism per contract, with
interface preservation machine-checked. Because the boundary provably does not move,
mechanisms of any grain become swappable behind it: a lumped yield, saturating
Michaelis–Menten kinetics, or a genome-derived FBA solver are three interpretations of
one unchanged interface. And structural events like cell division are not special
cases bolted on — they are first-class **rewrites of the composition itself**.

- 🔬 **[Explore the live dashboard →](https://vivarium-collective.github.io/meta-modelers-guide/dashboard/)** — every draft, executable, and study, browsable, no install.
- 📄 **[From Draft to Living Cell — the investigation report →](https://vivarium-collective.github.io/meta-modelers-guide/investigations/draft-to-living-cell.html)**

---

## The exhibit: one interface, three mechanisms, one impostor rejected

The sharpest single view is **Fig 6 — metabolism**. One typed interface,

    nutrients ⇒ biomass, energy, entropy, secretions

is realized by **three different mechanisms overlaid on one unchanged boundary**:

| Mechanism | What it is | Distinct behavior |
|---|---|---|
| `CoarseMetabolism` | a lumped linear yield | biomass tracks nutrients, no byproducts |
| `KineticMetabolism` | saturating Michaelis–Menten kinetics | biomass saturates as nutrients rise |
| `FBAMetabolism` | **real COBRApy flux-balance analysis** on `e_coli_core` | with an O₂/respiratory cap, carbon **overflows to acetate** — only the genome-derived network puts a secretion byproduct on the interface |

Three mechanisms, three genuinely different trajectories, **one interface that never
moves**. Then the scene the compiler makes visible: a fourth, *non-conforming*
handler — `NonConformingMetabolism`, an impostor that renames `biomass` to `growth`
with the wrong type and drops `energy`/`entropy`/`secretions` — is refused at compile
time with a **`CompileError` that names every missing port**. Conformance is not a
convention you are trusted to follow; it is a typing judgment the compiler enforces.

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

## The 60-second arc

**contract → coupling → mechanism-swap → rewrite → the whole cell.**

1. **Contract** — a cell is drawn as its typed exchange ports (chemical mol·s⁻¹,
   mechanical N, electrical A, thermal W, growth hr⁻¹, viability), with *no* mechanism
   yet (Fig 4).
2. **Coupling** — the interface is made operational by closing a sense/act loop with
   the environment over a real diffusing spatial field (Fig 5).
3. **Mechanism-swap** — one metabolism interface run coarse, kinetic, and as real FBA
   (Fig 6, the exhibit above).
4. **Rewrite** — division fires as a genuine discrete event: one cell node becomes two
   (Fig 10).
5. **The whole cell** — the figures' modules compose into one run that takes up
   nutrients and grows, divides when its biomass crosses a threshold, then — under a
   thermal shock that pushes it out of the viable band — loses viability and
   disintegrates into molecular debris. Because metabolism is swappable behind its
   fixed interface, **that whole cell runs three ways** (coarse / kinetic / FBA give
   three life histories).

## What this is — and what it is not

Honesty about scope is part of the claim:

- **Conformance is STRUCTURAL** — port names, types, and wiring. It is *not* a check of
  units, invariants, or runtime behavior. Units are name-only labels on ports
  (documentary, not machine-enforced); the compiler guarantees the ports line up, not
  that a mechanism honors its contract's *intended* behavior once running.
- **Constants are illustrative, not calibrated** — handlers are "toy-real" (see
  glossary): plausible numbers, not fitted parameters. The dynamics demonstrate the
  *pattern* (ultrasensitivity, closure, division, disintegration), not a
  quantitatively validated organism.
- **The whole cell is an assembled composition** in the figures' style — it wires
  independently-authored figure mechanisms together to show the interfaces *compose*.
  It is not itself compiled from the figure handlers, and it is not tuned to any real
  cell's physiology.
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

- [From Draft to Living Cell](https://vivarium-collective.github.io/meta-modelers-guide/investigations/draft-to-living-cell.html) — the full investigation: eight studies from typed interface to living, dividing, dying whole cell.
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
| `fig04a-interaction-modalities` | Fig 4a — four interaction-modality cards of the cellular interface: nutrient exchange (chemical flux), motile force (mechanical), growth rate, and electrical signaling. |
| `fig04b-cellular-interface` | Fig 4b — the minimal cellular interface. |
| `fig04b-executable` | EXECUTABLE compilation of fig04b-cellular-interface under handler environment 'fig04b' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig05-cell-environment` | Fig 5b — cell–environment coupling. |
| `fig05-executable` | EXECUTABLE compilation of fig05-cell-environment under handler environment 'fig05' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig06-disintegration` | Fig 6b — cell disintegration as a grain-swap equivalence. |
| `fig06-executable-coarse` | EXECUTABLE compilation of fig06-disintegration under handler environment 'fig06-coarse' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig06-executable-fba` | EXECUTABLE compilation of fig06-disintegration under handler environment 'fig06-fba' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig06-executable-kinetic` | EXECUTABLE compilation of fig06-disintegration under handler environment 'fig06-kinetic' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig07-executable` | EXECUTABLE compilation of fig07-molecular-mechanism under handler environment 'fig07' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig07-molecular-mechanism` | Fig 7b/7c — a molecular mechanism as a process with typed physical channels. |
| `fig08-executable` | EXECUTABLE compilation of fig08-nested-hierarchy under handler environment 'fig08' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig08-nested-hierarchy` | Fig 8b — molecular compositions as a nested hierarchical composite. |
| `fig09a-coarse-graining` | Fig 9a — self-organized processes, coarse-graining, and autopoiesis. |
| `fig09a-executable` | EXECUTABLE compilation of fig09a-coarse-graining under handler environment 'fig09a' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig09b-executable` | EXECUTABLE compilation of fig09b-minimal-cell under handler environment 'fig09b' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig09b-minimal-cell` | Fig 9b — minimal cell composition. |
| `fig10-1-division` | Fig 10.1 (panel b) — division as a compositional rewrite. |
| `fig10-1-executable` | EXECUTABLE compilation of fig10-1-division under handler environment 'fig10-1' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig10-2-development` | Fig 10.2 (panels c/d) — biofilm development as a hierarchical reorganization. |
| `fig10-2-executable` | EXECUTABLE compilation of fig10-2-development under handler environment 'fig10-2' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
| `fig10-3-evolution` | Fig 10.3 (panels e/f) — evolution reshapes the composition itself. |
| `fig10-3-executable` | EXECUTABLE compilation of fig10-3-evolution under handler environment 'fig10-3' — draft signatures replaced by conforming Process handlers (see compile.py). Runnable. |
<!-- END:composites -->

#### Investigations

<!-- BEGIN:investigations -->
<!-- generated by `vivarium-workbench gen-readme` — edit the source, not this table -->

| Investigation | Research question |
|---|---|
| [From Draft to Living Cell _(complete)_](https://vivarium-collective.github.io/meta-modelers-guide/investigations/draft-to-living-cell.html) | How far can a cell be built compositionally — assembled from typed interfaces, each specified as a *draft* before any mechanism is chosen, then compiled into something that actually runs — and does t… |
<!-- END:investigations -->
