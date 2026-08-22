# Study 9: `development-and-evolution` (spatial) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build study 9 (the capstone) of `the-cellular-interface-multicellular` — spatial **development** (a growing CPM colony self-organizing core-vs-rim heterogeneity: the "collective interface") and **evolution** (a heritable per-cell trait, inherited-with-mutation on division, shifting under shared-field selection), reusing study 8's colony. On the hardened bar.

**Architecture:** A new `CpmEvolution` process that SUBCLASSES/extends `CpmGrowthDivision` (study 8) — reusing its dFBA-growth + native `divide_cells` + biomass-partition + lineage/generation bookkeeping UNCHANGED — and ADDS a per-cell heritable trait `self.vmax[cid]` (that cell's dFBA glucose-uptake vmax). On division, each daughter inherits the parent's trait ± a Gaussian mutation (seeded RNG), using the existing creation-order `zip(dividing, new_ids)` parent→daughter pairing (verified in study 8). It emits a radial core-vs-rim heterogeneity metric (development) + the population mean/variance of the trait (evolution). Selection is implicit: higher-vmax cells grow/divide more on the shared depleting field → their trait proliferates.

**Tech Stack:** Python, `process_bigraph`, `cpm` (native `divide_cells`), `cobra` (`e_coli_core` dFBA), `spatio_flux` (`DiffusionAdvection`), numpy, matplotlib/imageio (GIF), Plotly (metrics). Reuses study 8 — no new dependency.

**Spec:** `docs/superpowers/specs/2026-08-21-cellular-interface-multicellular-design.md` (study 9 row). Paper Fig 10c–f (development / divide-evolve).
**API map:** `docs/superpowers/api-maps/2026-08-22-development-and-evolution-api-map.md` — every value below is verified there with a run.

## Global Constraints

- **Worktree discipline:** all work in `~/code/meta-modelers-guide--cpm-multicellular` on branch `study9-development-evolution`. Never commit in the canonical checkout. Verify `git branch --show-current` before each commit. Tests: `PYTHONPATH=~/code/meta-modelers-guide--cpm-multicellular` prepended; interpreter `~/code/meta-modelers-guide/.venv/bin/python`.
- **Reuse study 8:** `CpmGrowthDivision` already partitions biomass proportionally + records a real lineage/generation genealogy (the review's "resets state" complaint was fixed in study 8). Study 9 ONLY adds the heritable trait + mutation + the dev/evo observables — do NOT reinvent the growth/division loop.
- **Heritable trait:** per-cell `self.vmax[cid]` (glucose-uptake vmax), used in that cell's dFBA. On division (inside the existing `zip(dividing, new_ids)` creation-order pairing): `self.vmax[daughter] = self.vmax[parent] + rng.normal(0, mut_sigma)` (clamp to a sane positive range, e.g. [0.2, 20]); the PARENT keeps its trait. Verified: pairing is correct (99% of |child−parent| within 3σ over 69 division events).
- **CONFIG/SEED TRAP #1 (verified):** a `mut_sigma: 0.0` FLOAT override is SILENTLY DROPPED by bigraph_schema (schema default retained) — the classic zero-config trap. So the **no-mutation control MUST be a BOOLEAN flag** (`mutate: false`), NOT `mut_sigma=0.0`. (Or apply the Protocell/GrayScott zero-restore workaround — but a boolean is cleaner here.)
- **CONFIG/SEED TRAP #2 (verified):** the base hardcodes `potts.seed=1`; for a real multi-seed study the `seed` config MUST be threaded into BOTH `load_world` (the CPM potts seed) AND the mutation RNG — otherwise "5 seeds" is one trajectory. Verify both vary.
- **Multi-seed convention = FRACTION, not a single-seed headline (verified):** evolution is stochastic. Report the mean-trait shift as the fraction of seeds it rises: **selection ON → up in ≥4/5 seeds** (one seed can reverse — that's honest); **no-mutation control → 0/5** (mean stays exactly the founder value, variance 0); **no-selection control → ~2/5** (undirected drift). Assert these fractions/invariants with margin (mirror `tests/test_cellcell_multiseed.py`).
- **Development metric:** radial core-vs-rim heterogeneity — bin cells (or lattice pixels) by distance from the colony centroid; compute the rim/core local-glucose ratio (or per-cell growth-rate gradient). It EMERGES from shared-field coupling (early ~1.0 → late >1.0, e.g. 1.003→1.096 at vmax 1.5). It is shallow at vmax 1.5 (weak depletion) — state that honestly; sharpening it accelerates crowding (see the same-knob caveat).
- **The two halves pull the same knob (honest framing):** development heterogeneity and evolution both intensify with stronger field depletion, and the trait shift IS selection through differential division on the shared field — the colony saturates the lattice by ~gen 4–6, so both must be demonstrable within that window (or a larger grid / leaner field for more generations). The claim must state: selection operates via differential division on the shared depleting field.
- **Deps:** cpm + cobra + spatio_flux (reuses study 8's dFBA path). Tests `pytest.importorskip("cpm")`, `("spatio_flux")`, `("cobra")`.
- **Hardened conventions:** biology-first study.yaml; cite the paper by SECTION TITLE + `§` anchor; no sibling-counting; honest toy-scope; constants-ledger/units/deferrals followed (add kirschner2005 "facilitated variation" — mutating ports/couplings, not a parameter — as a named deferral).

---

## File Structure

- Create: `meta_modelers_guide/cpm/evolution.py` — `CpmEvolution(CpmGrowthDivision)` (heritable trait + mutation-on-division + seed threading + dev/evo observables).
- Create: `meta_modelers_guide/composites/development-evolution-spatial.composite.json` (selection ON), `development-evolution-no-mutation.composite.json` (`mutate: false` control), `development-evolution-no-selection.composite.json` (fitness-neutral trait control).
- Modify: `meta_modelers_guide/cpm/viz.py` — add `run_evolution_frames()` (colony colored by per-cell trait) on the shared contract (+ metrics-panel kind).
- Create tests: `tests/test_cpm_evolution_spike.py` (trait inheritance + selection shift), `tests/test_cpm_evolution.py` (process), `tests/test_dev_evo_regime.py` (dev heterogeneity + evo multi-seed), `tests/test_evolution_viz.py`.
- Modify: `tests/test_composites_build.py` — add `CpmEvolution` → `importorskip("cpm")` + `importorskip("cobra")` (dFBA).
- Create: `workspace/studies/development-and-evolution-spatial/study.yaml` (+ `viz/`).
- Modify: `workspace/investigations/the-cellular-interface-multicellular/investigation.yaml` (add the study) + `docs/superpowers/deferrals.md` (facilitated-variation / port-mutation deferral).

Tests guard: `import pytest; pytest.importorskip("cpm"); pytest.importorskip("spatio_flux"); pytest.importorskip("cobra")`.

---

## Task 1: Heritable-trait inheritance + selection spike

**Goal:** prove — in a committed test — that a per-cell heritable trait is inherited-with-mutation on division via the correct parent→daughter pairing, and that under selection the population mean trait SHIFTS up while a no-mutation control does NOT.

**Files:** Create `tests/test_cpm_evolution_spike.py`.

- [ ] **Step 1: RED** — build a minimal `CpmEvolution` (or a focused harness lifting the trait logic) over the study-8 colony with per-cell `vmax` used in dFBA, mutation-on-division (seeded RNG), and the creation-order pairing. Assert (deterministic seed, ~45 ticks):
  - **inheritance correctness:** across division events, `|vmax[daughter] − vmax[parent]|` is ~N(0,σ)-distributed (e.g. 99% within 3σ) — the pairing propagates traits, not scrambles them;
  - **selection shifts the mean:** with `mutate: true` and vmax affecting uptake, the population mean vmax ENDS above the founder value (for a seed you observe it rises; the multi-seed fraction is Task 4);
  - **no-mutation control:** with `mutate: false` (BOOLEAN — not mut_sigma=0.0), the mean vmax stays EXACTLY the founder value and variance is 0.
- [ ] **Step 2: Run → GREEN.** Confirm the `seed` config threads into both `load_world` and the RNG (two different seeds give two different trajectories). Commit.

---

## Task 2: `CpmEvolution` process

**Goal:** the process extending `CpmGrowthDivision` with the heritable trait + dev/evo observables.

**Files:** Create `meta_modelers_guide/cpm/evolution.py`; Create `tests/test_cpm_evolution.py`.

**Interface:** subclass `CpmGrowthDivision`; config adds `{mutate (bool, default true), mut_sigma (float, default ~0.3), vmax0 (founder trait), vmax_min, vmax_max, seed}`. Override the per-cell dFBA to use `self.vmax[cid]` (not a global `glucose_vmax`); initialize `self.vmax[founder]=vmax0`; on division, in the existing pairing loop, set daughter vmax = clamp(parent vmax + (rng.normal(0,mut_sigma) if mutate else 0)), parent keeps its trait. Thread `seed` into `load_world` potts seed + the mutation RNG. Add observables (`overwrite[...]`): `mean_vmax`, `var_vmax`, `rim_core_ratio` (the radial heterogeneity metric — bin live cells by distance from the colony centroid, rim mean vs core mean of local glucose or growth), plus keep the inherited `n_cells`/`generation`/`max_generation`. Register via `build_core()` (`local:CpmEvolution`).

- [ ] **Step 1: RED** — `tests/test_cpm_evolution.py`: build a Composite with `local:CpmEvolution`; run; assert `mean_vmax` ends > `vmax0` under selection (`mutate: true`), `rim_core_ratio` > 1 (heterogeneity emerged), `n_cells` compounds; a `mutate: false` composite ends `mean_vmax == vmax0`, `var_vmax == 0`.
- [ ] **Step 2: Implement → GREEN.** Reuse the study-8 growth/division body; only ADD the trait + observables. Commit.

---

## Task 3: Three composites + build guard

**Files:** Create `development-evolution-spatial.composite.json` (`mutate: true`, trait affects uptake — selection ON), `development-evolution-no-mutation.composite.json` (`mutate: false`), `development-evolution-no-selection.composite.json` (trait fitness-NEUTRAL — e.g. a flag decoupling vmax from the dFBA uptake so mutation still varies the trait but it confers no fitness → undirected drift). Grid sized (per the API map) for ~4–6 generations before crowding; glucose field per study 8. Static/deterministic seed.

- [ ] **Step 1:** author the JSONs; verify each builds. Extend the build guard: `if "CpmEvolution" in raw: importorskip cpm + cobra`.
- [ ] **Step 2:** full `-m pytest -q` (no regressions). Commit.

---

## Task 4: Tune + assert development + evolution (multi-seed)

**Files:** Create `tests/test_dev_evo_regime.py`.

- [ ] **Step 1: RED**:
  - `test_development_heterogeneity_emerges`: run `development-evolution-spatial`; assert `rim_core_ratio` starts ~1.0 and ENDS clearly > 1 (core more depleted than rim) — development.
  - `test_evolution_shifts_trait_under_selection` (multi-seed FRACTION): across ≥5 seeds, the selection-ON colony's `mean_vmax` ends above `vmax0` in **≥4/5** seeds (report the Δ range; one seed may reverse — assert the fraction, not every seed).
  - `test_no_mutation_control_is_static`: across seeds, `mutate: false` → `mean_vmax == vmax0` and `var_vmax == 0` every seed (0/5 shift).
  - `test_no_selection_control_drifts`: the fitness-neutral trait drifts undirected — the mean does NOT consistently rise (e.g. up in ≤ ~2/5, no directional selection signal) — isolating SELECTION (not mutation alone) as the cause of the directional shift.
- [ ] **Step 2: Run → GREEN** (tune grid/generations/σ only if the signal isn't legible in the window; record the observed multi-seed fractions + Δ ranges in the ledger). Commit.

---

## Task 5: Visualization (the colony evolving)

**Files:** Modify `meta_modelers_guide/cpm/viz.py`; Create `tests/test_evolution_viz.py`.

Add `run_evolution_frames(state, core, steps, cadence)` on the shared contract: render the colony over the glucose field with each cell FILLED by a color mapping its TRAIT (`vmax`) on a continuous scale — so the audience watches the trait distribution shift (selection) AND the colony develop (core/rim). `metrics`: `time`, `mean_vmax`, `var_vmax`, `rim_core_ratio`, `n_cells`; register a panel kind (plot `mean_vmax` rising + `rim_core_ratio`). Do NOT break the other renderers.

- [ ] **Step 1: RED** — `tests/test_evolution_viz.py`: run `development-evolution-spatial`; ≥6 frames, `mean_vmax` present and ends > start, GIF non-empty, metrics HTML with a Plotly div.
- [ ] **Step 2: Implement → GREEN.**
- [ ] **Step 3: Bake** `viz/development-evolution-spatial.gif` + `viz/development-evolution-metrics.html` into `workspace/studies/development-and-evolution-spatial/viz/`. VIEW frames: colony grows, trait-color shifts toward higher-vmax, core/rim visible. Commit code; artifacts land in Task 6.

---

## Task 6: Study + investigation + report

**Files:** Create `workspace/studies/development-and-evolution-spatial/study.yaml` (+ `viz/`); Modify `investigation.yaml` + `deferrals.md`.

Mirror `workspace/studies/autopoiesis-spatial/study.yaml` (new-bar exemplar). Biology-first:
- Question: does the paper's development/evolution (Fig 10c–f) hold spatially — a growing CPM colony forming core-vs-rim heterogeneity (a collective interface) while a heritable per-cell trait evolves under shared-field selection — reusing the study-8 colony? Cite the paper by section title. Cite stewart2008/flemming2016 (biofilm physiological heterogeneity) for development; the adaptation-ladder (regulation/learning/evolution) framing.
- Measured outcomes: development `rim_core_ratio` ~1.0 → >1 (emergent, shallow at vmax 1.5 — honest); evolution mean_vmax shifts up in ≥4/5 seeds under selection (Δ range), 0/5 no-mutation, ~2/5 no-selection drift. Cite tests.
- HONEST findings (foreground): the DUAL control (no-mutation → static; no-selection → undirected drift) isolates SELECTION as the cause of the directional trait shift; selection operates via **differential division on the shared depleting field** (the two halves pull the same knob). TOY evo-devo scope: development = shared-field core/rim heterogeneity (NOT morphogenesis/signalling); evolution = ONE scalar heritable trait under resource selection (NOT genome/regulatory-network evolution; kirschner2005 facilitated variation — mutating ports/couplings — is a named DEFERRAL). Cross-link `draft-to-living-cell/development-and-evolution`.
- Viz refs: the GIF + metrics.
- Add the study to investigation.yaml; add the facilitated-variation deferral to `deferrals.md`.

- [ ] **Step 1:** author study.yaml; wire investigation; add the deferral.
- [ ] **Step 2:** `python scripts/lint-workspace.py` OK (no new warnings; § anchor); yaml parses.
- [ ] **Step 3:** `vivarium-workbench render-loom --study development-and-evolution-spatial --max-width 1600 --colors 128` → loom Model figure.
- [ ] **Step 4:** render report; confirm loom + GIF + interactive metrics. Do NOT commit generated `reports/*.html`.
- [ ] **Step 5:** full `-m pytest -q` green; deps-absent skip holds; `bash scripts/check-no-local-paths.sh` OK.
- [ ] **Step 6:** commit study + investigation + deferrals + viz + loom.

---

## Self-Review notes
- **Spec coverage:** study 9 (development + evolution) → development (Task 2/4) + evolution (Tasks 1–4) reusing study 8; the DUAL control isolates selection. ✓
- **Config/seed traps addressed:** no-mutation control is a BOOLEAN flag (not mut_sigma=0.0); `seed` threaded into both load_world + RNG (Global Constraints + Tasks 1–2). ✓
- **Multi-seed = fraction** (selection ≥4/5, no-mutation 0/5, no-selection ~2/5), honest not single-seed headline. ✓
- **Honest scope:** toy evo-devo, same-knob caveat, facilitated-variation deferral. ✓
- **Reuse:** subclass `CpmGrowthDivision`, add only the trait — no reinvented growth/division. ✓
