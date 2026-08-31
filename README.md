# A meta-modeler's guide to the cellular interface — executable companion

Runnable companion to the paper *A meta-modeler's guide to the cellular interface and its
composition patterns* (E. Agmon). The paper treats a cell's **interface** — the variables
through which it senses and acts on its environment — as both a modeling choice and a
testable hypothesis about which interactions matter. Composition is an ongoing practice:
connect descriptions where their assumptions agree, cut them apart where they fail. A
cell-level description holds only while its interface stays within **viability bounds**.

Every figure in the paper is specified here as a *draft process* — an interface contract
with no mechanism behind it — and then realized as an executable process-bigraph simulation.
The composition diagrams in the paper are generated from these specifications.

Two investigations carry the argument:

- **[Executable Figures](https://vivarium-collective.github.io/meta-modelers-guide/dashboard/?investigation=paper-figures)** — the eleven figures, each a runnable composite behind its diagram, checked against its caption.
- **[From Draft to Living Cell](https://vivarium-collective.github.io/meta-modelers-guide/dashboard/?investigation=draft-to-living-cell)** — the composition patterns as 2-D spatial models: Cellular Potts cells, dynamic FBA, diffusing fields, a Turing pattern, an emergent membrane.

<!-- BEGIN dashboard -->
> ## 📊 [**Live dashboard →**](https://vivarium-collective.github.io/meta-modelers-guide/dashboard/)
> Browse every investigation & study interactively, or read the [published investigation reports](https://vivarium-collective.github.io/meta-modelers-guide/). Auto-published from `main` on every merge.
<!-- END dashboard -->

## Composition patterns

The patterns run outward from the cell to its environment and neighbours, inward to the
molecular organization that builds the interface, then on to growth, division, and evolution.

| Pattern | Fig | What it shows |
|---|:---:|---|
| [cellular-interface](workspace/studies/cellular-interface/study.yaml) | 3 | the cell's typed exchange ports, before any mechanism |
| [cell-environment-coupling](workspace/studies/cell-environment-coupling/study.yaml) | 4 | a sense/act loop over a diffusing field; the cell reshapes its own gradient |
| [cell-cell-coupling](workspace/studies/cell-cell-coupling/study.yaml) | — | two cells on one shared nutrient store: competition or cross-feeding |
| [disintegration](workspace/studies/disintegration/study.yaml) | 5 | a cell past its viability bound; the cell-level description gives way to molecules |
| [molecular-interfaces](workspace/studies/molecular-interfaces/study.yaml) | 6 | ATP synthase driving four physical channels from one proton flux |
| [biomolecular-complementarity](workspace/studies/biomolecular-complementarity/study.yaml) | 7 | molecular structure as a nested hierarchical composite |
| [autopoiesis](workspace/studies/autopoiesis/study.yaml) | 8 | metabolism, containment, and replication maintaining one another |
| [growth-and-division](workspace/studies/growth-and-division/study.yaml) | 9 | division as a rewrite of the composition |
| [development-and-evolution](workspace/studies/development-and-evolution/study.yaml) | 10–11 | biofilm nesting and selection as rewrites |

*Executable Figures* also covers Figs 1–2 (process bigraphs and orchestration).

## One interface, many mechanisms

The mechanism behind an interface can be replaced as long as the interface is preserved,
because the interface is what other models couple to. The disintegration study realizes one
metabolic interface (`nutrients ⇒ biomass, energy, secretions`) three ways — a lumped yield,
Michaelis–Menten kinetics, and flux-balance analysis on *E. coli*'s `e_coli_core` network
(which overflows carbon to acetate under an oxygen cap) — giving three trajectories behind one
unchanged interface. The [viva-compiler](https://github.com/vivarium-collective/viva-compiler)
installs each mechanism behind the draft's ports and checks that they match.

## Scope

The models are illustrative, not calibrated: plausible constants chosen to show a pattern,
not a fitted organism. The interface check is structural (port names, types, wiring); units
are documentary labels. The playable disintegration and the whole-cell capstone are
hand-assembled in the figures' style, not tuned to a real cell.

## Working with this workspace

    bash scripts/serve.sh                 # open the dashboard locally
    python3 scripts/lint-workspace.py     # validate the workspace
    python scripts/build_executables.py   # materialize every figure's executable

Scaffolded from [viva-template](https://github.com/vivarium-collective/viva-template); the
compilation from interface contract to executable is described in
[`docs/concepts/semantic-to-executable-compilation.md`](docs/concepts/semantic-to-executable-compilation.md).
The [viva-superpowers](https://github.com/vivarium-collective/viva-superpowers) skills
(`/viva-study`, `/viva-investigation`, `/viva-expert`, `/viva-viz`, `/viva-report`) drive the
study → investigation → report → PR flow. Research state lives under `workspace/`, with
locations set by `layout:` in `workspace.yaml`.

## Composites and investigations

Generated from the workspace by `vivarium-workbench gen-readme` (the same sets the dashboard
shows) and refreshed by CI. Regenerate with `vivarium-workbench gen-readme --workspace .`.

### Composites

<!-- BEGIN:composites -->
<!-- generated by `vivarium-workbench gen-readme` — edit the source, not this table -->

| Composite | What it is |
|---|---|
| `A Biological Process Bigraph` | Fig 1c — A biological process bigraph: processes are wired into the store hierarchy, each assigned a specific mechanism declared in its contract. |
| `A Molecular Mechanism` | Fig 6b/6c — a molecular mechanism as a process with typed physical channels. |
| `A Process` | Fig 1a — A process: typed input and output ports plus a configuration whose update method maps inputs to a delta over the outputs. |
| `A Store Hierarchy` | Fig 1b — A store hierarchy: the place graph of biological containment from tissue down to molecules, each store typed with its biological unit. |
| `Biofilm Development — Draft Interface` | Fig 10 (panels c/d) — biofilm development as a hierarchical reorganization. |
| `Biofilm Emergence — Live Topology` | Fig 10b as a genuine place-graph rewrite: biofilm emergence from free motile bacteria. |
| `Cell Disintegration` | Fig 5b — cell disintegration as a grain-swap equivalence. |
| `Cell Division — Draft Interface` | Fig 9 (panel b) — division as a compositional rewrite. |
| `Cell Division — Live Topology` | Fig 9 as a genuine place-graph rewrite: chromosome segregation then cell division via Milner reaction rules over a tree[node] store. |
| `Cell ↔ Environment — Live Coupling` | Fig 4 as a fully runnable temporal study: a real length-9 diffusing chemical grid seeded as a nutrient GRADIENT (low at index 0, high at index 8). The single cell sits at an interior index (4) and se… |
| `Cell–Cell Coupling` | Paper §Cell–cell coupling (no dedicated figure). Two cell agents are wired to one shared environmental nutrient store: each senses the pool and depletes it, so their interfaces are coupled not only t… |
| `Cell–Environment Coupling` | Fig 4b — cell–environment coupling. |
| `Disintegration (playable)` | Fig 5a — cell disintegration as a playable trajectory: a thermal shock pushes the cell past its viability bound; viability collapses, viability-gated metabolism halts, and biomass decays into molecul… |
| `Evolution — Live Topology` | Fig 11 (evolution) as a genuine place-graph rewrite: a wildtype population establishes (organism nodes added), a fitter mutant arises, then a selection sweep adds mutant offspring and prunes wildtype… |
| `Evolution — Living Population` | Fig 11b — evolution by natural selection as a genuine place-graph rewrite you can play forward. |
| `Fig 11b evolution — A few generations later` | Fig 11b, evolution snapshot: t=later — the founder's fitter descendants have reproduced (daughter cells added to the population) with mutated traits; a trait cloud has formed and the environment's op… |
| `Fig 11b evolution — A single founder` | Fig 11b, evolution snapshot: t=0 — one founder cell in the population; the environment's selection optimum sits at the founder's trait. |
| `F₁Fₒ ATP Synthase — Live Four-Channel Transduction` | Fig 6 as a fully runnable temporal study: the F₁Fₒ ATP synthase as a molecular transducer that couples a proton-motive force across four TYPED physical channels. |
| `Grain Swap` | Fig 5b — grain swap on viability. |
| `Grain Swap — Live Viability-Driven Switch` | Fig 5 as a fully runnable temporal study: a cell's viability is driven down by an external stress ramp (StressRamp); a GrainSelector swaps the active grain as viability crosses a threshold — while vi… |
| `Interaction Modalities` | Fig 3a — four interaction-modality cards of the cellular interface: nutrient exchange (chemical flux), motile force (mechanical), growth rate, and electrical signaling. |
| `Nested Cellular Hierarchy — Live Cascade` | Fig 7 as a fully runnable temporal study: a cell's subsystems are a NESTED hierarchy of coupled processes running together. |
| `Nested Molecular Hierarchy` | Fig 7b — molecular compositions as a nested hierarchical composite. |
| `Orchestration — multi-timestepping through a shared store` | Fig 2a made runnable at the smallest honest scale: TWO processes updating at DIFFERENT rates through ONE shared pool store. |
| `Process bigraph — minimal executable demonstration` | Fig 1 made runnable at the smallest honest scale: ONE real process (StoreTransfer) wired to TWO scalar place-graph nodes (store_a the source, store_b the sink). A first-order transfer dA/dt=-k*A, dB/… |
| `Self-Organization & Coarse-Graining` | Fig 8a — self-organization, coarse-graining, and autopoiesis. |
| `The Cellular Interface` | Fig 3b — the minimal cellular interface. |
| `The Cellular Interface — Made to Run` | Fig 3 as a fully runnable temporal study: a bounded cell (local:CellularInterfaceHandler) senses its environmental drivers and exposes typed interface ports. |
| `The Minimal Cell` | Fig 8b — the minimal cell: the three columns of Fig 8a wired into one composite. |
| `The Minimal Cell — Autopoietic Closure (runnable)` | Fig 8 as a fully runnable temporal study: the minimal cell's six coupled processes wired over FLAT scalar building-block pools (the form the ODE handlers actually integrate — membrane, lipids, metabo… |
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

### Investigations

<!-- BEGIN:investigations -->
<!-- generated by `vivarium-workbench gen-readme` — edit the source, not this table -->

| Investigation | Research question |
|---|---|
| [From Draft to Living Cell _(running)_](https://vivarium-collective.github.io/meta-modelers-guide/investigations/draft-to-living-cell.html) | The paper treats a biological interface as a scientific object — something you can compose with other entities, swap the mechanism behind, and watch emerge from the inside. |
| [Executable Figures _(complete)_](https://vivarium-collective.github.io/meta-modelers-guide/investigations/paper-figures.html) | The meta-modeler's guide argues its case through eleven figures — each a BioRender illustration (panel a) paired with a process-bigraph diagram (panel b) that names the composition behind the biology. |
<!-- END:investigations -->
