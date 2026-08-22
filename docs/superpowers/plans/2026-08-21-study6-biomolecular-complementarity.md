# Study 6: `biomolecular-complementarity` (spatial) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build study 6 of `the-cellular-interface-multicellular` — differential-adhesion **cell sorting** (Steinberg's hypothesis = the paper's Fig 8 complementarity/selectivity, made spatial): a mixed checkerboard of two CPM cell types demixes into separated domains under adhesion energetics alone — plus a minimal, independent **Cahn-Hilliard** phase-field as the honestly-framed "condensate" phase-separation analogue. With GIFs + synced metrics and a study + report.

**Architecture:** A pure-CPM world-owning process `CpmSorting` (modeled on `CpmColonyField` but STRIPPED of dFBA/field/cobra) owns one CPM world of two interleaved cell types, steps it each tick, and emits a heterotypic-interface sorting metric + a cohesion guard + per-cell type/COM/volume. Separately and uncoupled, a tiny `CahnHilliard` process evolves a scalar field φ by `∂φ/∂t = M∇²(φ³ − φ − κ∇²φ)` (spinodal decomposition, mass-conserved). Two composites, two GIFs. No metabolism, no shared field between the two.

**Tech Stack:** Python, `process_bigraph`, `cpm` (viva-cpm; Rust `cpm_core` — contact-energy sorting), numpy (Cahn-Hilliard + metrics), matplotlib + imageio/Pillow (GIF), Plotly (metrics). **No cobra, no spatio_flux, no dFBA.**

**Spec:** `docs/superpowers/specs/2026-08-21-cellular-interface-multicellular-design.md` (study 6 row: "differential-adhesion cell sorting (Steinberg = complementarity made spatial) + phase separation for condensates").
**API map:** `docs/superpowers/api-maps/2026-08-21-biomolecular-complementarity-api-map.md` — every value below is verified there with a run snippet.

## Global Constraints

- **Worktree discipline:** all work in `~/code/meta-modelers-guide--cpm-multicellular` on branch `study6-biomolecular-complementarity`. Never commit in the canonical checkout. Verify `git branch --show-current` before each commit. Tests run with `PYTHONPATH=~/code/meta-modelers-guide--cpm-multicellular` prepended; interpreter `~/code/meta-modelers-guide/.venv/bin/python`.
- **Pure adhesion energetics — no metabolism:** `CpmSorting` uses ONLY `cpm`. No `fields` input/output, no cobra, no dFBA, no spatio-flux. Its tests carry `pytest.importorskip("cpm")` only. (`CahnHilliard` is pure numpy over a `fields` store — no spatio-flux dependency; its tests need no importorskip beyond `numpy`, but keep an `importorskip("cpm")`-free posture — it doesn't touch cpm.)
- **Verified sorting regime (use verbatim):** two types; contact matrix `J(1,1)=J(2,2)=2.0` (homotypic, favorable), `J(1,2)=11.0` (heterotypic, costly), `J(0,1)=J(0,2)=8.0` (medium, cohesive); `temperature=10.0`, `neighbor_order=2`, `lambda_volume=2.0`, `target_volume=25`, an 8×8 checkerboard of 5×5-px cells on a 70×70 lattice, ~600 MCS in `mcs=10` chunks. Sorting condition: `J(1,2) > ½(J(1,1)+J(2,2))`. `T=1` freezes (no sorting); `T≥200` boils cells into medium (metric trap — see cohesion guard).
- **Sorting metric = heterotypic-interface FRACTION** (not raw count): count 4-neighbor lattice edges where both pixels are cells (`>0`) of DIFFERENT type → `hetero`; count all edges where both are cells → `total_intercell`; metric = `hetero/total_intercell`. (Raw hetero-count is not robust because `total_intercell` rises as cells compact.) Verified 1.000 → ~0.116.
- **COHESION GUARD (mandatory):** `hetero_frac` alone falsely reads ~0.000 when the clump DISSOLVES into medium. Emit total cell-pixel count beside it; the "sorted" claim is gated on BOTH `hetero_frac` dropping (< ~0.2) AND cell-pixels retained (within ~10% of t0). Every regime assertion checks both.
- **Cahn-Hilliard:** `mu = phi**3 - phi - kappa*lap(phi)`; `phi = phi + dt*M*lap(mu)` with `lap` = 5-point periodic Laplacian. `M=1, kappa=0.5, dt=0.002` (STABLE); `dt=0.05` → NaN (the ∇⁴ term's stability limit is ~`dt < dx⁴/(16 M kappa)`). Seed near-critical noise (mean 0, ±0.025). Mass-conserved (`mean(phi)` constant). Uncoupled from CPM — do NOT couple φ to the cells.
- **Full import-path / registration:** in-repo `CpmSorting` and `CahnHilliard` register via `build_core()` auto-scan (`core.register_link`); addressed `local:CpmSorting`, `local:CahnHilliard`.
- **Shared-grid contract:** arrays `(ny,nx)`=(rows,cols); `snapshot()` flat `x+y*nx` → reshape `(ny,nx)`. `cell_types()`/`cell_coms()`/`cell_volumes()` are LISTS indexed by id, `[0]`=medium.
- **`overwrite[...]` on absolute observables:** `hetero_frac`, `cell_pixels`, `n_type1`, `n_type2`, per-cell `type`/`position`/`volume` are per-tick absolute readings → `overwrite[...]`. For CH, `phi` is a `map[array]`/array field the process replaces (not a delta) — follow the field-write convention its composite uses.
- **Toy-real:** the sorting regime and CH params are tuned, not fitted — narrow cohesive-and-mobile window; honest caveats REQUIRED (regime is chosen; CH is an independent uncoupled analogue; sorting plateaus at a residual two-domain boundary, frame as "~9× interface collapse", not "to zero").
- **Tests** carry the appropriate guards; no local absolute home-dir paths in committed docs — CI (`scripts/check-no-local-paths.sh`) rejects them; use `~` / `<worktree>`.

---

## File Structure

- Create: `meta_modelers_guide/cpm/sorting.py` — `CpmSorting(Process)` (2-type world, sorting metric + cohesion guard).
- Create: `meta_modelers_guide/processes/cahn_hilliard.py` (or `meta_modelers_guide/cpm/`-adjacent per repo layout — put it where `build_core()` scans it) — `CahnHilliard(Process)`.
- Create: `meta_modelers_guide/composites/cell-sorting-spatial.composite.json` — the sorting composite.
- Create: `meta_modelers_guide/composites/condensate-cahn-hilliard.composite.json` — the CH composite.
- Modify: `meta_modelers_guide/cpm/viz.py` — add `run_sorting_frames()` (two-color demixing) + `run_cahn_hilliard_frames()` (φ heatmap) + metrics.
- Create tests: `tests/test_cpm_sorting_spike.py`, `tests/test_cpm_sorting.py`, `tests/test_cahn_hilliard.py`, `tests/test_sorting_regime.py`, `tests/test_sorting_viz.py`.
- Modify: `tests/test_composites_build.py` — add guards: `CpmSorting` → `importorskip("cpm")`; `CahnHilliard` → no special dep (pure numpy) but confirm it builds.
- Create: `workspace/studies/biomolecular-complementarity-spatial/study.yaml` (+ `viz/`).
- Modify: `workspace/investigations/the-cellular-interface-multicellular/investigation.yaml` — add `biomolecular-complementarity-spatial` to `studies`.

---

## Task 1: Sorting spike + metric + cohesion guard

**Goal:** prove in a REAL cpm world that a mixed 2-type checkerboard demixes — `hetero_frac` drops from ~1.0 to < 0.2 while the clump stays cohesive — and lock the metric + cohesion helpers as a committed test.

**Files:** Create `tests/test_cpm_sorting_spike.py`.

- [ ] **Step 1: Write the failing test (RED)** — seed the verified checkerboard (8×8 of 5×5-px, types `1 if (r+c)%2==0 else 2`, abutting, on 70×70), the verified J matrix + `T=10`, run ~600 MCS. Assert `hetero_frac` t0 > 0.8, t_end < 0.2, AND `cell_pixels` t_end within 10% of t0 (cohesion). Include the metric + cohesion helpers:

```python
# tests/test_cpm_sorting_spike.py
"""Differential-adhesion cell sorting (Steinberg): a mixed 2-type checkerboard demixes
under CPM contact energetics — heterotypic interface collapses while the clump stays
cohesive (the guard that a dissolved clump isn't misread as 'sorted')."""
from __future__ import annotations
import numpy as np
import pytest
pytest.importorskip("cpm")
from cpm.schema import load_world

NX = NY = 70

def _checkerboard(n=8, size=5, x0=15, y0=15):
    cells = []
    for r in range(n):
        for c in range(n):
            t = 1 if (r + c) % 2 == 0 else 2
            x, y = x0 + c * size, y0 + r * size
            cells.append({"type": t, "target_volume": 25.0, "lambda_volume": 2.0,
                          "target_surface": 0.0, "lambda_surface": 0.0,
                          "seed_block": [x, y, 0, x + size, y + size, 1]})
    return cells

def _world():
    return load_world({
        "potts": {"dims": [NX, NY, 1], "boundary": "noflux", "neighbor_order": 2,
                  "temperature": 10.0, "seed": 1},
        "cells": _checkerboard(),
        "contact": [{"a": 0, "b": 1, "j": 8.0}, {"a": 0, "b": 2, "j": 8.0},
                    {"a": 1, "b": 1, "j": 2.0}, {"a": 2, "b": 2, "j": 2.0},
                    {"a": 1, "b": 2, "j": 11.0}],
    })

def hetero_frac(w):
    lat = np.array(w.snapshot()).reshape(NY, NX); types = w.cell_types()
    hetero = total = 0
    for arr in (lat[:, :-1], lat[:-1, :]):
        pass  # explicit loop below for clarity
    for i in range(NY):
        for j in range(NX):
            a = lat[i, j]
            if a == 0: continue
            for di, dj in ((0, 1), (1, 0)):
                ii, jj = i + di, j + dj
                if ii < NY and jj < NX and lat[ii, jj] > 0:
                    b = lat[ii, jj]
                    total += 1
                    if types[a] != types[b]: hetero += 1
    return hetero / total if total else 0.0

def cell_pixels(w):
    return int((np.array(w.snapshot()) > 0).sum())

def test_checkerboard_demixes_and_stays_cohesive():
    w = _world()
    f0, p0 = hetero_frac(w), cell_pixels(w)
    assert f0 > 0.8                                  # starts well-mixed
    for _ in range(60):
        w.step(10)                                    # ~600 MCS
    f1, p1 = hetero_frac(w), cell_pixels(w)
    assert f1 < 0.2                                   # sorted: heterotypic interface collapsed
    assert abs(p1 - p0) < 0.10 * p0                   # cohesion guard: clump did NOT dissolve
```

- [ ] **Step 2: Run** — `PYTHONPATH=$PWD ~/code/meta-modelers-guide/.venv/bin/python -m pytest tests/test_cpm_sorting_spike.py -v`. If sorting doesn't reach < 0.2 in 600 MCS, extend steps or re-check the J matrix against the API map (do NOT change the verified regime without noting why). Expected: GREEN.
- [ ] **Step 3: Commit.**

---

## Task 2: `CpmSorting` process

**Goal:** the world-owning process that runs the sorting world and emits the metric + cohesion guard + per-cell observables.

**Files:** Create `meta_modelers_guide/cpm/sorting.py`; Create `tests/test_cpm_sorting.py`.

**Interfaces:**
- Consumes (config): `grid {nx,ny}`; `checkerboard {n, size, x0, y0}` (or an explicit `cells` list); the J `contact` matrix; `temperature`, `target_volume`, `lambda_volume`, `mcs`.
- Consumes (ports): none (no field input).
- Produces (ports): `hetero_frac: overwrite[float]`, `cell_pixels: overwrite[float]`, `n_type1: overwrite[float]`, `n_type2: overwrite[float]`, per-cell `type: overwrite[map[float]]`, `position: overwrite[map[list]]`, `volume: overwrite[map[float]]`.

Model on `colony_field.py` for world construction + per-cell reads, but REMOVE the field/dFBA/cobra path entirely. Each tick: `world.step(mcs)`; compute `hetero_frac` + `cell_pixels` (reuse Task 1's helpers — factor them into the module); emit per-cell type/COM/volume (list-indexed ids skip 0). Register in `__init__.py` for `build_core()` discovery; address `local:CpmSorting`.

- [ ] **Step 1: RED** — `tests/test_cpm_sorting.py` (`importorskip("cpm")`): build a Composite with `local:CpmSorting`, run ~600 MCS, assert `obs['hetero_frac']` ended < 0.2, `obs['cell_pixels']` cohesive vs its start, `n_type1`/`n_type2` constant (== 32 each for the 8×8 board).
- [ ] **Step 2: Implement → GREEN.**
- [ ] **Step 3: Commit.**

---

## Task 3: `CahnHilliard` process (independent condensate analogue)

**Goal:** a minimal, uncoupled Cahn-Hilliard phase-field process — spinodal decomposition of a scalar φ, mass-conserved, numerically stable.

**Files:** Create the process module (where `build_core()` scans it); Create `tests/test_cahn_hilliard.py`.

**Interface:** config `{grid {nx,ny}, M (1.0), kappa (0.5), dt (0.002), steps_per_tick}`; a `fields` store holding `phi` (array). Each tick, advance φ `steps_per_tick` times: `lap` = periodic 5-point Laplacian; `mu = phi**3 - phi - kappa*lap(phi)`; `phi = phi + dt*M*lap(mu)`. Emit the new φ (field replacement) + observables `phi_var: overwrite[float]`, `phi_mean: overwrite[float]`, `phi_min`/`phi_max: overwrite[float]`.

- [ ] **Step 1: RED** — `tests/test_cahn_hilliard.py`: seed φ with mean-0 ±0.025 noise (fixed via `np.random.default_rng(0)` — deterministic, NOT unseeded), advance enough steps (e.g. 20000 total across ticks), assert `phi_var` rose from ~0 to > 0.3 (phase-separated), `abs(phi_mean_end - phi_mean_0) < 1e-3` (mass conserved), `-1.05 < phi_min` and `phi_max < 1.05` (bounded domains). Guard: assert no NaN.
- [ ] **Step 2: Implement → GREEN.** Pin `dt=0.002`; document the ∇⁴ stability limit in a comment; assert-guard against NaN in the update.
- [ ] **Step 3: Commit.**

---

## Task 4: Two composites + build guard

**Goal:** author the sorting and CH composites in the discovered `composites/` dir (loom Model figures bake automatically).

**Files:** Create `meta_modelers_guide/composites/cell-sorting-spatial.composite.json`, `meta_modelers_guide/composites/condensate-cahn-hilliard.composite.json`; Modify `tests/test_composites_build.py`.

- **cell-sorting-spatial:** `state` = one `CpmSorting` (`local:CpmSorting`, the verified checkerboard + J matrix + T=10) + `RAMEmitter`. No fields.
- **condensate-cahn-hilliard:** `state` = a `fields` store with `phi` (mean-0 ±0.025 noise, 64×64 or so) + one `CahnHilliard` (`local:CahnHilliard`, M=1/κ=0.5/dt=0.002) + `RAMEmitter`.
- Build guard: add `if "CpmSorting" in raw: pytest.importorskip("cpm")`. `CahnHilliard` is pure numpy — it needs no importorskip (it builds anywhere); confirm it does.

- [ ] **Step 1:** author both JSONs; verify each builds — `... -m pytest "tests/test_composites_build.py::test_composite_builds[cell-sorting-spatial]" "tests/test_composites_build.py::test_composite_builds[condensate-cahn-hilliard]" -v`.
- [ ] **Step 2:** update the build guard.
- [ ] **Step 3:** full `-m pytest -q` (no regressions). Expected: GREEN.
- [ ] **Step 4: Commit.**

---

## Task 5: Tune + assert both regimes

**Goal:** lock both demonstrating claims in tests: sorting (hetero_frac collapses ~9× AND clump cohesive) and CH (φ phase-separates AND mass conserved).

**Files:** Create `tests/test_sorting_regime.py`.

- [ ] **Step 1: RED** — `tests/test_sorting_regime.py` (`importorskip("cpm")`):
  - `test_sorting_demixes_cohesively`: run `cell-sorting-spatial` ~600 MCS; assert `hetero_frac` start > 0.8, end < 0.2, AND `cell_pixels` end within 10% of start (BOTH — the cohesion gate).
  - `test_cahn_hilliard_phase_separates_mass_conserved`: run `condensate-cahn-hilliard`; assert `phi_var` rose > 0.3, `phi_mean` conserved (< 1e-3 drift), bounded, no NaN.
- [ ] **Step 2: Run → tune** only if needed (the API-map regime already passes; sorting run length / CH steps_per_tick are the knobs). Record final constants + observed values in the ledger.
- [ ] **Step 3: Commit.**

---

## Task 6: Visualization (both)

**Goal:** a sorting GIF (two cell colors demixing over ~600 MCS) + a CH GIF (φ field phase-separating), each with a synced metrics panel.

**Files:** Modify `meta_modelers_guide/cpm/viz.py`; Create `tests/test_sorting_viz.py`.

- `run_sorting_frames(state, core, steps, cadence)`: color each cell by its TYPE (two colors + medium background) from `snapshot()` + `cell_types()`; `metrics` = `time`, `hetero_frac`, `cell_pixels`.
- `run_cahn_hilliard_frames(state, core, steps, cadence)`: render φ as a diverging heatmap (`RdBu`, −1..+1); `metrics` = `time`, `phi_var`.
- Reuse `frames_to_gif`; extend `metrics_panel` (branch on shape) for the hetero_frac curve + the φ_var curve; keep `include_plotlyjs`. Do NOT break flagship/colony/disintegration/growth-division viz paths (confirm their viz tests pass).

- [ ] **Step 1: RED** — `tests/test_sorting_viz.py`: for BOTH composites, ≥6 frames, metric arrays present, GIF non-empty, metrics HTML with a Plotly div; the sorting metrics' `hetero_frac` ends below its start.
- [ ] **Step 2: Implement → GREEN.**
- [ ] **Step 3: Bake** `viz/cell-sorting-spatial.gif`, `viz/cell-sorting-metrics.html`, `viz/condensate-cahn-hilliard.gif`, `viz/condensate-metrics.html` into `workspace/studies/biomolecular-complementarity-spatial/viz/`. Commit code; artifacts land with the study in Task 7.

---

## Task 7: Study + investigation + report

**Goal:** author the study, wire it in, bake the loom Model figure(s), render the report.

**Files:** Create `workspace/studies/biomolecular-complementarity-spatial/study.yaml` (+ `viz/`); Modify `workspace/investigations/the-cellular-interface-multicellular/investigation.yaml`.

Mirror `workspace/studies/cell-cell-coupling-spatial/study.yaml` (schema_version 4). Content:
- Name `biomolecular-complementarity-spatial`, title "Biomolecular Complementarity, Spatial".
- Question: does Fig 8's complementarity/selectivity hold spatially — two CPM cell types with differential adhesion self-sorting into separated domains (Steinberg = "like binds like" made spatial), alongside an independent Cahn-Hilliard condensate phase-separation — from cpm alone?
- Measured outcomes: sorting `hetero_frac` 1.0 → ~0.12 (a ~9× interface collapse) with the clump cohesive (cell-pixels ~1600→~1518); CH φ_var ~0 → ~0.5, mass conserved.
- Cite tests: `test_cpm_sorting_spike`, `test_cpm_sorting`, `test_cahn_hilliard`, `test_sorting_regime`, `test_sorting_viz`.
- HONEST caveats (REQUIRED): the sorting J-regime is chosen/tuned, not fitted (narrow cohesive-and-mobile window: `T=1` freezes, `T≥200` dissolves); sorting plateaus at a residual two-domain boundary — frame as "heterotypic interface collapses ~9×", not "to zero"; the metric is gated by a cohesion guard so a dissolved clump isn't misread as sorted; the Cahn-Hilliard condensate is an INDEPENDENT, UNCOUPLED second demonstration (φ is not coupled to the CPM cells), numerically stiff (pinned `dt=0.002`). Cross-link to the `draft-to-living-cell` analogue study `biomolecular-complementarity`.
- Viz refs: `image:` → the two GIFs; `html:` → the two metrics panels.

- [ ] **Step 1:** author `study.yaml`; add to the investigation's `studies:`.
- [ ] **Step 2:** `python scripts/lint-workspace.py` → OK (only the pre-existing dash-in-name warning). Verify YAML parses (`yaml.safe_load`) — watch single-quote escaping in block scalars.
- [ ] **Step 3:** bake the loom Model figure(s): `vivarium-workbench render-loom --study biomolecular-complementarity-spatial --max-width 1600 --colors 128`.
- [ ] **Step 4:** render the report; confirm the study section shows the loom Model figure(s) + both GIFs + interactive metrics. Do NOT commit generated `reports/*.html`.
- [ ] **Step 5:** full `-m pytest -q` green; deps-absent CI skip holds; `bash scripts/check-no-local-paths.sh` → OK.
- [ ] **Step 6: Commit** study + investigation + viz artifacts.

---

## Self-Review notes

- **Spec coverage:** study 6 row (differential-adhesion sorting + condensate phase-separation) → sorting core Tasks 1–2, CH Task 3, both demonstrated Tasks 4–7. ✓
- **Cohesion guard** (the metric trap): mandated in Global Constraints + asserted in Tasks 1 and 5 (both `hetero_frac` drop AND cell-pixel retention). ✓
- **CH honesty:** independent + uncoupled, numerically stiff (pinned dt), framed as a second demonstration — Task 3 + Task 7 caveats. ✓
- **No cobra/spatio_flux:** `CpmSorting` is cpm-only; `CahnHilliard` is numpy-only; guards + build-guard reflect this (Task 4). ✓
- **Type consistency:** `hetero_frac`/`cell_pixels`/`n_type*` `overwrite[float]`; per-cell `overwrite[map[...]]`; the metric + cohesion helpers defined once (Task 1) and reused (Task 2). ✓
- **CI:** tests carry `importorskip("cpm")` where cpm is used; no local absolute home-dir paths in committed docs. ✓
