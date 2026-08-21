# The Cellular Interface, Multicellular — a spatial 2D analogy of `draft-to-living-cell`

**Date:** 2026-08-21
**Status:** Approved design (brainstorming complete) → next: implementation plan (writing-plans), flagship first
**Companion:** the existing `draft-to-living-cell` investigation (the 9 composition-pattern studies)
**Source paper:** *A meta-modeler's guide to the cellular interface and its composition patterns* (Agmon), plus *Process Bigraphs and the Architecture of Compositional Systems Biology* (Agmon & Spangler, arXiv:2512.23754 — the spatio-flux worked example).

## Motivation

`draft-to-living-cell` *specified* the paper's interface patterns and ran them with **toy-real** mechanisms (lumped ODEs, scripted events). This new investigation realizes the **same nine interface patterns in real 2D spatial frameworks** — chiefly a Cellular Potts Model (viva-cpm) and spatial dynamic-FBA + reaction-diffusion (spatio-flux) — so each pattern is demonstrated as a *composition of independently-developed frameworks via typed interfaces*, which is the paper's central claim made concrete and multicellular. The two investigations are deliberate analogues: study *N* here is the spatial counterpart of study *N* there.

## Decisions (locked with the user)

- **A new investigation in this repo**: `the-cellular-interface-multicellular`, a sibling to `draft-to-living-cell`, depending on `cpm` (viva-cpm) + `spatio_flux` (both already editable-installed).
- **A complete 9-study analogy**: every study of `draft-to-living-cell` gets a spatial counterpart, using CPM where it fits and other 2D spatial frameworks where they fit better.
- **Other 2D frameworks are in scope**: beyond CPM + spatio-flux, add small in-repo process-bigraph processes for **reaction-diffusion** (Gray-Scott/Turing) and **phase-field / Cahn-Hilliard** (condensates, diffuse interfaces) — no new heavy dependency.
- **Force / mechanical interface** → new **upstream viva-cpm modules** that derive effective forces from CPM adhesion/volume/surface energies and expose mechanical-interface ports (a viva-cpm PR), scheduled **after** the flagship.
- **The CPM↔field coupling bridge lives in this repo first** (`meta_modelers_guide` package), upstreamed to viva-cpm later once general.
- **Flagship-first**: build study 2 (`single-cell-in-a-field`) end-to-end (composite → run → GIF+metrics → study → report) to lock the pattern, then fan out.
- **FBA source**: spatio-flux `DynamicFBA` (spatial, composable) for the multicellular/field studies; the existing `draft-to-living-cell` COBRApy `fig06` path is unchanged. No `viva-cobra` exists.
- **Visualizations**: a new `cpm_viz` module renders CPM lattice frames (+ field heatmap overlay) to an animated **GIF**, beside a **synced time-series panel** sharing the run's time axis.

## Composition architecture — the `CpmFieldBridge` (load-bearing new module)

Two field representations exist: cpm has an internal field (`field_at_cell`, `secretory_types`; `receptor_coupling` wires `field_at_cell → ligand`), and spatio-flux has grid fields with real `DiffusionAdvection` + `DynamicFBA` on `(i,j)`. The bridge composes them:

`CpmFieldBridge` (a process-bigraph `Process` in `meta_modelers_guide/cpm/bridge.py`):
- **Consumes** the CPM cells' `positions` (centers of mass) and `volumes`/`types`.
- **Maps** each cell's COM → grid index `(i,j)` on the spatio-flux field grid.
- **Exposes**, per cell, the spatio-flux field value(s) at that grid cell as the cell's *sensed* signal (`sensed[cid]`), for downstream metabolism/behavior.
- **Routes** each cell's dFBA uptake/secretion back into that grid cell's substrate stores, so `DiffusionAdvection` then spreads it.
- Interface (draft-authored typed ports): in `{positions, volumes, types, fields}`, out `{sensed, field_deltas}`.

Build the bridge once; all four spatial patterns (single-cell, multi-cell competition, development, spatial metabolism) compose on it. This bridge *is* the typed interface the paper is about — the reusable coupling point between the CPM cell agents and the spatial-flux field/metabolism.

## The nine studies (spatial analogy)

Slugs mirror `draft-to-living-cell`. ✅ = framework already installed; ➕ = small new in-repo process.

| # | Study slug | Paper pattern | Spatial realization | Framework |
|---|---|---|---|---|
| 1 | `cellular-interface` | Fig 4 typed ports | one CPM cell as a bounded region exposing typed exchanges spatially (chemical via field, mechanical via adhesion/volume energy, viability via structural integrity) | ✅ cpm |
| 2 | `cell-environment-coupling` **[FLAGSHIP]** | Fig 5 sense/act loop | one CPM cell in a spatio-flux diffusing nutrient field: senses local nutrient (bridge), runs dFBA, secretes, chemotaxes up-gradient | ✅ cpm + spatio-flux |
| 3 | `cell-cell-coupling` | Fig 3 viability negotiation | many CPM cells competing for one shared nutrient field (dFBA each) → spatial competitive exclusion; cross-feeding via secreted byproducts | ✅ cpm + spatio-flux |
| 4 | `disintegration` | Fig 6 level shift | a CPM cell whose structural-integrity constraint releases when a stressor field crosses its viability bound → coherent cell domain dissolves into dispersed pixels/particles | ✅ cpm (→ particles) |
| 5 | `molecular-interfaces` | Fig 7 molecular mechanism | a spatial reaction-diffusion enzymatic network (chemical channel), electrical/thermal/mechanical as coupled fields; cpm SBML subcellular as the molecular pathway | ➕ reaction-diffusion + ✅ spatio-flux/cpm-SBML |
| 6 | `biomolecular-complementarity` | Fig 8 selectivity/condensates | differential-adhesion cell sorting (Steinberg = complementarity made spatial) + phase separation for condensates | ✅ cpm sorting + ➕ Cahn-Hilliard |
| 7 | `autopoiesis` | Fig 9 closure | a protocell maintaining its own boundary: internal metabolism produces membrane components sustaining the boundary that contains the metabolism | ✅ cpm self-maintained cell, or ➕ reaction-diffusion protocell |
| 8 | `growth-and-division` | Fig 10a,b | CPM cell grows (volume target driven by metabolism) and divides at threshold | ✅ cpm |
| 9 | `development-and-evolution` | Fig 10c–f | CPM colony/crypt development (proliferation → structured tissue) + evolution via heritable variation under selection | ✅ cpm crypt/colony |

Each study keeps the honest framing conventions of `draft-to-living-cell` (toy-real vs validated; what's demonstrated vs asserted; explicit caveats), and cross-links to its `draft-to-living-cell` analogue.

## The flagship — `cell-environment-coupling` / `single-cell-in-a-field`

**Question:** does the Fig 5 sense/act loop hold as *real spatial metabolism* — one cell sensing a diffusing nutrient field, running flux-balance at its location, secreting a byproduct, and moving up the gradient — composed from independently-built CPM + spatio-flux processes through one typed bridge?

**Composite** (`meta_modelers_guide/composites/` + a semantic draft + executable):
- `cpm` `CPMProcess` — one cell, 2D lattice (e.g. 50×50), volume target, chemotaxis toward field 0.
- `spatio_flux` `DiffusionAdvection` — the nutrient field on the same grid (Neumann/periodic BC).
- `spatio_flux` `DynamicFBA` — `e_coli_core` (or a small curated model) at the cell's grid cell: nutrient uptake → biomass, secretes a byproduct (e.g. acetate) into the field.
- `CpmFieldBridge` — wires cell COM → grid cell → field-sensed → dFBA substrate stores → field deltas.
- Orchestrated so CPM steps (Monte-Carlo sweeps) and field/dFBA steps interleave via the workspace's process-bigraph engine.

**Observables** (the run's metrics, emitted): cell volume, cell COM (x,y), local nutrient concentration at the cell, dFBA uptake flux, biomass, secreted byproduct, distance moved up-gradient.

**Interface framing:** the cell's ports map to the paper's cellular interface — `sensed nutrient` (chemical-in), `uptake/secretion` (chemical-out), `position/volume/shape` (mechanical/morphological state), `viability` (structural integrity). The bridge is where the CPM description couples to the environmental description — Fig 5's coupling, made spatial.

## Visualization — `cpm_viz` (the GIF + synced metrics ask)

New module `meta_modelers_guide/cpm/viz.py`:
- **Frame renderer**: from a run's emitted lattice snapshots + field, render each frame — cell domain(s) colored by type, field as a heatmap underlay, COM marker — via matplotlib (headless).
- **GIF baker**: assemble frames → an animated GIF (imageio or Pillow), saved as a study visualization asset (`viz/<name>.gif`).
- **Synced metrics panel**: a Plotly (or matplotlib) time-series of the run's observables sharing the same time axis, so the movie and the metrics read together. For the report, a static panel beside the GIF; optionally an interactive Plotly time-series alongside (reusing the `DynamicsPlot` engine from `draft-to-living-cell`).
- The study's `visualizations:` entries reference the GIF (`image:`/embedded) + the metrics figure; the report shows both.
- Emitting lattice snapshots requires the CPM run to record per-step frames — the composite's emitter captures the CPM world state (a compact lattice array) at a chosen cadence.

## Dependencies & mechanics

- Add `cpm` (pbg-cpm) and `spatio_flux` to `pyproject.toml` deps (both editable-installed already; declare them so the workspace is reproducible). Note the CPM engine is a Rust extension (`cpm_core`), installed via maturin — a machine precondition, documented.
- New package subtree `meta_modelers_guide/cpm/`: `bridge.py`, `viz.py`, `composites/`, plus small `reaction_diffusion.py` and `phase_field.py` processes for studies 4–7.
- Studies authored to the workspace schema (as in `draft-to-living-cell`) + validated by `scripts/lint-workspace.py`; interactive/GIF viz baked; report via the workbench.
- `the-cellular-interface-multicellular/investigation.yaml` groups the nine studies with a re-anchored narrative (the spatial realization of the paper's arc).

## Force / mechanical interface (upstream viva-cpm, post-flagship)

New viva-cpm modules (a viva-cpm PR): derive effective forces from the CPM Hamiltonian — surface-tension / adhesion forces (from adhesion energies), pressure (from volume constraint), traction (cell–substrate) — exposed as mechanical-interface ports (`force`, `tension`, `pressure`) on the CPM process or a companion metrics process. Used to give studies 1, 3, 6, 8 a quantified mechanical interface. Specified in its own follow-up once the flagship validates the composition path.

## Increment plan (flagship first)

1. **Flagship** — `CpmFieldBridge` + the `single-cell-in-a-field` composite + `cpm_viz` (GIF + metrics) + the `cell-environment-coupling` study + report. Locks the composition + viz pattern.
2. Fan out to the CPM-native studies reusing the bridge/viz: `cell-cell-coupling` (multi-cell dFBA competition), `growth-and-division`, `development-and-evolution` (crypt/colony).
3. Add the ➕ processes and their studies: `molecular-interfaces` (reaction-diffusion), `biomolecular-complementarity` (sorting + Cahn-Hilliard), `disintegration` (structural-integrity release), `autopoiesis` (self-maintained cell / RD protocell), `cellular-interface` (the bounded-cell interface study).
4. Upstream **viva-cpm force modules**; wire the mechanical interface into the relevant studies.
5. Investigation-level narrative, cross-links to `draft-to-living-cell`, report.

Each increment is its own composite(s) + study + viz + review, following the subagent-driven flow.

## Out of scope

- Calibrating any model to fitted parameters (frameworks stay toy-real; caveats preserved).
- 3D (cpm supports it, but this investigation is deliberately 2D for clarity/viz).
- Replacing or altering `draft-to-living-cell` (this is an additive sibling investigation).
- A `viva-cobra` package (FBA comes from spatio-flux `DynamicFBA` / existing COBRApy).

## Testing

- Each composite: builds and runs to completion; emits the declared observables; interface preserved under compilation where the draft→executable pattern applies.
- `CpmFieldBridge`: a unit test that a cell at a known COM reads the field value at the expected grid cell and that its uptake writes the expected substrate delta.
- The flagship: a behavior test that over the run the cell's local nutrient depletes, biomass rises, byproduct is secreted, and the cell moves up-gradient (net positive displacement toward the source).
- `cpm_viz`: a test that a GIF is produced with N frames and the metrics panel carries the run's series; guarded so a missing optional dep (imageio) degrades gracefully.
- Framework-native studies: reuse viva-cpm's / spatio-flux's own validated behaviors where possible (cite their tests), adding only the composition-level assertions.
