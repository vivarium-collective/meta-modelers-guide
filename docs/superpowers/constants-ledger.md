# Constants ledger — `the-cellular-interface-multicellular`

The five spatial studies share one coupling-process family but tune different regime
parameters. Those choices used to live only in each study's prose (and, for the
cross-study picture, in the reviewer's head — Part D-7 of the Fable review). This is the
single table of what each study sets and why, so a value that legitimately differs across
studies (e.g. `grow_per_biomass` 300 vs 40 vs 30) reads as a deliberate regime choice, not
drift.

All values are **toy-real**: plausible, hand-tuned magnitudes chosen for legible dynamics
over a short run, not fitted to a named organism or medium. For the dimensional footing
(what a tick / a lattice pixel / `box_volume_L` actually map to) see
[`units-and-timescales.md`](units-and-timescales.md). Values are harvested from the
committed composites under `<repo>/meta_modelers_guide/composites/*.composite.json`.

## Per-study regime table (one row per study)

| Study | Composite(s) | Metabolism | Key regime parameters | Field / diffusion | Run |
|---|---|---|---|---|---|
| **cell-environment-coupling-spatial** (flagship) | `single-cell-in-a-field` (+ `-mm`, `-o2uncapped`) | e_coli_core dFBA, O2-capped | `glucose_km` 0.5, `glucose_vmax` 3.5, `oxygen_vmax` 2.5, `box_volume_L` 0.3, `grow_per_biomass` 300, `mcs` 3, T 10 | glucose D 0.4, acetate D 0.6; 60×60 gradient | 20 ticks |
| **cell-cell-coupling-spatial** — compete | `cellcell-compete` | e_coli_core dFBA per cell, O2-capped | competitor `glucose_vmax` **10.0 vs 4.0**, `oxygen_vmax` 15, `box_volume_L` 0.3, `grow_per_biomass` 40, `mcs` 3 | glucose D 0.4, acetate D 0.6; 60×60 uniform 3.0 | 20 ticks |
| **cell-cell-coupling-spatial** — crossfeed | `cellcell-crossfeed` (+ `-knockout`) | secretor + consumer dFBA | secretor `glucose_vmax` 10 / `oxygen_vmax` 5; consumer `acetate_vmax` 20 / `oxygen_vmax` 20; `grow_per_biomass` 30, `box_volume_L` 0.3 | glucose D 0.4, **acetate D 15.0** (D-ratio 37.5×); 20 mM depot cols 0–18 | 20 ticks |
| **disintegration-spatial** | `disintegration-spatial` | **none** (no cobra path) | `viability_threshold` 0.5, `resorb_per_tick` 6.0, `max_particles_per_tick` 8, `mcs` 3, `stressor_field: acetate` | acetate D 4.0, debris `diffusion_rate` 1.0; radial gradient peak 1.5 (r 5→18) | 20–24 ticks |
| **growth-and-division-spatial** | `growth-division-spatial` | e_coli_core dFBA | `glucose_vmax` **1.5**, `glucose_km` 0.5, `oxygen_vmax` 15, `box_volume_L` 0.3, `grow_per_biomass` 40, `vol_threshold` 80, `reset_target` 40, `mcs` 3 | glucose D 0.4, acetate D 0.6; 60×60 uniform abundant | 36 ticks (÷3) |
| **biomolecular-complementarity-spatial** — sorting | `cell-sorting-spatial` | **none** (contact energy only) | J-triple **homotypic 2 / heterotypic 11 / medium 8**, T 10, `mcs` 10; 8×8 checkerboard, 5×5 px, 70×70 | no field | ~600 MCS |
| **biomolecular-complementarity-spatial** — condensate | `condensate-cahn-hilliard` | **none** (phase field) | `M` 1.0, `kappa` 0.5, `dt` 0.002 (pinned); 64×64 near-critical φ | φ scalar field | 10000 steps |

## Where values legitimately differ across studies, and why

- **`grow_per_biomass` 300 (flagship) vs 40 (compete / growth-division) vs 30 (crossfeed).**
  This constant converts a per-tick FBA biomass increment into a CPM target-volume increment.
  The regimes operate at different biomass scales: the single-cell flagship keeps biomass
  small (~0.1 → ~0.37 total over 20 ticks), so it needs a large multiplier to grow the
  lattice volume 32 → 110 px; the colony competition drives biomass into the hundreds
  (237.9 winner), so a small multiplier (40) already saturates the lattice. The value tracks
  the biomass scale of each regime, not an independent physical quantity.

- **`glucose_vmax` 3.5 (flagship) / 10 vs 4 (compete) / 10 (crossfeed secretor) / 1.5
  (growth-division).** Uptake capacity is the *independent variable* in two studies: the
  compete regime's whole result is the 10-vs-4 asymmetry, and growth-division deliberately
  detunes it down to 1.5 so the division staircase stays legible (at 10.0 every cell
  re-crosses `vol_threshold` almost every tick and the lattice floods). Same parameter, three
  different experimental roles.

- **`oxygen_vmax` 2.5 (flagship) vs 5 (crossfeed secretor) vs 15 (compete / growth-division)
  vs 20 (crossfeed consumer).** The O2 cap is what forces mixed-acid acetate overflow. It is
  tightened (2.5, 5) where acetate secretion is the point (flagship plume; crossfeed handoff)
  and loosened (15) where overflow is incidental and growth speed matters (compete,
  growth-division). The crossfeed consumer's 20 is on acetate uptake, a different exchange.

- **acetate diffusion 0.6 (most) vs 15.0 (crossfeed).** Only the crossfeeding regime needs
  the byproduct plume to travel across the gap between two footprints within 20 ticks, so its
  acetate D is raised to 15.0 (D-ratio 37.5× over glucose). This is directionally defensible —
  acetate is the smaller molecule — but ~20× larger than the real aqueous acetate/glucose
  ratio (~2×); see the study's own limitation and [`units-and-timescales.md`](units-and-timescales.md).

- **`box_volume_L` 0.3 everywhere metabolic.** Held constant across all dFBA studies (the
  code default is 1e-6; every composite overrides it to 0.3). It is the single knob mapping
  cobra's mmol·gDW⁻¹·hr⁻¹ fluxes into field-concentration deltas — see
  [`units-and-timescales.md`](units-and-timescales.md). Keeping it fixed keeps the flux→field
  conversion comparable across studies.

- **disintegration and sorting/condensate run no metabolism at all.** Disintegration is
  deliberately about the viability-collapse trigger (a phenomenological `viability_threshold`
  on a diffusing acetate field), and the complementarity study's two regimes are contact-energy
  sorting and a Cahn-Hilliard phase field — neither has a cobra path, so their rows carry no
  FBA constants by design.

## Sorting J-matrix (the differential-adhesion regime)

| contact | J | meaning |
|---|---|---|
| type1–type1, type2–type2 | 2.0 | homotypic contact is cheap |
| type1–type2 | 11.0 | heterotypic contact is expensive |
| medium–type1, medium–type2 | 8.0 | contact with medium sits between |

Temperature 10 (Metropolis fluctuation scale). This J-triple satisfies Steinberg's sorting
inequality J(1,2) > ½·(J(1,1)+J(2,2)), i.e. 11 > 2 — a qualitative, theory-grounded anchor.
Outside a narrow window the demonstration fails in two documented ways: T=1 freezes the mixed
state, T≥200 dissolves the cells into medium.
