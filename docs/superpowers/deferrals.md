# Deferrals and follow-ups — `the-cellular-interface-multicellular`

Deferred scope evaporates silently when it lives only in per-study "next steps" prose that
nothing aggregates (Part D-9 of the Fable review). This is the one place the dropped and
deferred commitments are collected, so they stay visible as open work rather than quietly
disappearing between spec and study. Each line: **what**, **why deferred**, **where it would
live**.

| # | What | Why deferred | Where it would live |
|---|---|---|---|
| 1 | **Flagship chemotaxis** — the cell moving *up* the sensed gradient ("moves up-gradient" behavior, spec-promised) | The flagship demonstrates the sense → metabolize → secrete loop; directed *control* (the paper's "minimal structure required for control") was scoped out to keep the first composition clean. The cell's modest position drift is CPM thermal fluctuation, not directed motion. | A follow-up variant of `single-cell-in-a-field` adding a gradient-biased motility term; a "moves up-gradient" behavior test in `tests/test_flagship_field.py`. |
| 2 | **viva-cpm mechanical-interface ports** — force / tension / pressure derived from CPM adhesion, volume, and surface energies | The CPM is natively mechanical, but no runtime setters expose these as interface variables in the current build; surfacing them needs an upstream viva-cpm change. | A viva-cpm upstream PR exposing effective forces; a mechanical-interface observable (e.g. shared contact-boundary length in cell-cell, target-vs-actual volume deviation as pressure in growth-division). Names the four-modality gap in `investigation.yaml → what_this_does_not_demonstrate`. |
| 3 | **Cahn-Hilliard interface-work** — a condensate *selectively concentrating or excluding* a second species (study 6's named gap) | The condensate study demonstrates a boundary *forming* (mass-conserved phase separation) but not the boundary *doing work* — the discriminator the paper's §Molecular compositions question turns on (functional regulatable boundary vs transient aggregate). Building selective partitioning is a second mechanism, out of scope for the first pass. | `condensate-cahn-hilliard` + a second species with a selective-partitioning coupling; a pass/fail test that a droplet concentrates/excludes it. Already named as the next step in `biomolecular-complementarity-spatial`. |
| 4 | **Disintegration's mechanistic viability trigger** — FBA maintenance infeasibility as endogenous collapse | The disintegration study uses a phenomenological `viability_threshold` on a diffusing acetate field. The mechanistic version (the LP going infeasible when fixed ATP maintenance cannot be met at zero footprint glucose) already exists in `cell_field.py::_fba` but was not wired in — metabolism was deliberately stripped from the study to isolate the collapse trigger. | A disintegration variant that couples `CpmDisintegration` to a dFBA path and triggers release on FBA maintenance infeasibility, upgrading the paper's "phenomenological → emergent" viability grading from the first case to the second. |
| 5 | **Debris-as-lysate** — shed disintegration particles depositing mass back into a field | Shed pixels currently become inert `map[particle]` markers no other process reads; making them a nutrient source is a new coupling out of scope for the collapse demonstration. | Disintegration particles writing into a shared `fields` store as lysate; composes disintegration with the colony/crossfeed studies (the relational-molecule arc: acetate as waste, food, toxin; debris as nutrient). |
| 6 | **The three non-chemical modalities** — mechanical forces (N), electrical currents (C·s⁻¹), heat transfer (J·s⁻¹) | Every study realizes only the chemical port (mol·s⁻¹). Electrical (gap-junction) and thermal channels have no engine support here; mechanical is item 2. | Future studies once the ports exist; the gap is owned in `investigation.yaml → what_this_does_not_demonstrate` using the paper's port vocabulary. Item 2 is the nearest-term of the three. |
| 7 | **Per-cell interfaces / hierarchical nesting / structural rewrites** | The composition is framework-level (one monolithic coupling process owns the whole CPM world); cells are not processes and division does not mutate the composition graph. Realizing the paper's per-cell-ports architecture is a substantial re-architecture, not a study-level tweak. | A future architecture increment where each cell is a process with its own ports; owned in `investigation.yaml → what_this_does_not_demonstrate`. |

## Not deferred (landed in this hardening pass, for contrast)

- **Multi-seed robustness convention** — established once on `cell-cell-coupling-spatial`'s
  competition headline (`tests/test_cellcell_multiseed.py`): the single-seed 3.69× is the top of a
  seed-1-to-5 band of ~2.9×–3.7× (mean ~3.2×), with the faster competitor winning every seed. The
  convention (process reads `seed` from config, deep-copy state and sweep, assert the qualitative
  claim per seed and report the range) is documented in that test for studies 5/7/9 to copy. The
  remaining studies are *not* retrofitted here — that is follow-up.
- The cross-cutting honesty docs themselves: [`constants-ledger.md`](constants-ledger.md),
  [`units-and-timescales.md`](units-and-timescales.md), and the investigation-level
  `what_this_does_not_demonstrate` scope statement.
