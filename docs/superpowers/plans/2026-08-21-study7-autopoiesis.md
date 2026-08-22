# Study 7: `autopoiesis` (spatial) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build study 7 of `the-cellular-interface-multicellular` — a minimal **autopoietic protocell** (paper §Self-organized processes, Fig 9): a self-maintaining membrane whose persistence is *caused by* an internal production loop, proven by a **negative-control vesicle** (production off) that decays. The contrast — persists vs collapses — is the finding. On the new (hardened) bar: biology-first, section-cited, multi-seed, honest scope.

**Architecture:** A pure-numpy reaction-diffusion process `Protocell` over a `fields` store: a membrane-density field `phi` evolves by `dphi/dt = D·lap(phi) − k_decay·phi + production`, where `production` (the internal "metabolism") fires ONLY where the membrane still topologically encloses an interior (closure, via `scipy.ndimage.binary_fill_holes`/`label`) and is deposited back onto existing membrane. The **negative control is the single-variable knockout `k_prod = 0`** → pure decay → the boundary dissipates. Persistence is self-limiting (homeostatic), not a tuned setpoint. No cpm / cobra / spatio_flux.

**Tech Stack:** Python, `numpy` (the RD physics), `scipy.ndimage` (closure detector — already imported unguarded by shipped `cpm/disintegration.py`), `process_bigraph` (the field process), matplotlib + imageio/Pillow (GIF), Plotly (metrics).

**Spec:** `docs/superpowers/specs/2026-08-21-cellular-interface-multicellular-design.md` (study 7 row: "a protocell maintaining its own boundary"). Paper §Self-organized processes / autopoiesis.
**API map:** `docs/superpowers/api-maps/2026-08-21-autopoiesis-api-map.md` — every value below is verified there with a run snippet.

## Global Constraints

- **Worktree discipline:** all work in `~/code/meta-modelers-guide--cpm-multicellular` on branch `study7-autopoiesis`. Never commit in the canonical checkout. Verify `git branch --show-current` before each commit. Tests: `PYTHONPATH=~/code/meta-modelers-guide--cpm-multicellular` prepended; interpreter `~/code/meta-modelers-guide/.venv/bin/python`.
- **Physics (verified regime):** `dphi/dt = D·lap(phi) − k_decay·phi + production`; canonical `D=0.02, k_decay=0.01, k_prod=0.03`, 64×64 periodic grid, Gaussian-annulus seed. `lap` = periodic 5-point Laplacian. Stability is MILD (2nd-order CFL, keep `D < 0.25`); NOT Cahn-Hilliard's stiff biharmonic dt. Reuse CahnHilliard's **delta-write** convention (emit `phi_new − phi_read` into the additive `fields` store; verified `store == phi_new`).
- **Closure = production gated on topological enclosure.** Production fires only where the membrane encloses an interior (`binary_fill_holes(phi>thr) & ~(phi>thr)` = interior; deposit proportional to `phi` scaled by enclosed area). A punctured membrane (no enclosed interior) → production shuts off → cannot rebuild from nothing (the viability bound; beer2023 "constraints on shared state that must be maintained for the composition to persist"). This is maintenance-against-decay, NOT puncture self-repair — state that honestly.
- **Boundary-integrity metric = enclosed interior area (px).** GATE the "persists" claim like study 6's cohesion guard: `persists := enclosed_area > 0 AND mass held near seed` — so a filled-in blob (enclosed area 0 but high mass) is NOT misread as a live vesicle. Verified: closed loop plateaus enclosed 556→~276 (mass ~831, homeostasis); control → enclosed 0, mass 0 by step ~101.
- **Negative control** = `k_prod = 0`, everything else identical (the load-bearing single-variable knockout).
- **Multi-seed** (hardened-pipeline convention): the closed loop persists across ≥5 seeds (ends enclosed ∈ [292,294] > 0); the control collapses to 0 every seed. Assert the RANGE, not a single-seed point (mirror `tests/test_cellcell_multiseed.py`).
- **No cpm/cobra/spatio_flux.** Tests need `pytest.importorskip("process_bigraph")` at the composite level; the pure-physics test needs no guard beyond numpy/scipy. Mirror `tests/test_cahn_hilliard.py`.
- **New-bar conventions:** biology-first study.yaml; cite the paper by SECTION TITLE (§Self-organized processes) with `§` anchors; no sibling-counting; honest toy-scope; follow `docs/superpowers/constants-ledger.md` / `units-and-timescales.md` / `deferrals.md`.

---

## File Structure

- Create: `meta_modelers_guide/protocell/__init__.py` + `meta_modelers_guide/protocell/autopoiesis.py` — the `Protocell(Process)` (new subpackage, mirroring `condensate/`).
- Create: `meta_modelers_guide/composites/protocell-autopoietic.composite.json` (closed loop) + `meta_modelers_guide/composites/protocell-vesicle-control.composite.json` (`k_prod=0`).
- Modify: `meta_modelers_guide/cpm/viz.py` — add `run_protocell_frames()` on the shared contract (+ its metrics-panel kind in `_METRICS_PANEL_DISPATCH`).
- Create: `tests/test_protocell_physics.py` (RD spike), `tests/test_protocell.py` (the process), `tests/test_autopoiesis_regime.py` (persist-vs-decay + multi-seed), `tests/test_protocell_viz.py`.
- Modify: `tests/test_composites_build.py` — the protocell composites are pure-numpy; confirm they build without special guards (no cpm/cobra/spatio_flux).
- Create: `workspace/studies/autopoiesis-spatial/study.yaml` (+ `viz/`).
- Modify: `workspace/investigations/the-cellular-interface-multicellular/investigation.yaml` — add `autopoiesis-spatial` to `studies` (do NOT undo the Phase-5 `what_this_does_not_demonstrate` block).

Tests guard: `import pytest; pytest.importorskip("process_bigraph")` for composite-level tests (numpy/scipy are hard deps already used in shipped code).

---

## Task 1: RD protocell physics spike (persist vs decay)

**Goal:** prove in a committed test — pure physics, no process — that the closed loop's membrane PERSISTS (enclosed area plateaus > 0) while the `k_prod=0` control COLLAPSES to enclosed 0, from an identical seed; and that puncturing the steady membrane is fatal.

**Files:** Create `tests/test_protocell_physics.py`.

- [ ] **Step 1: RED** — implement the RD step + closure detector as small module functions (they'll be reused by the process in Task 2), and assert:
  - deterministic seed (`np.random.default_rng(0)` for any noise) → closed loop `enclosed_area` ends > 0 (e.g. > 100) after ~2000 steps, mass held near seed;
  - control (`k_prod=0`, else identical) → `enclosed_area` == 0 by ~step 150, mass → ~0;
  - puncture: take the closed-loop steady state, zero a wedge of the membrane so nothing is enclosed, continue → it does NOT recover (enclosed stays 0) — the viability bound.
  Physics: `phi = phi + dt*(D*lap(phi) - k_decay*phi + production(phi))`; `production` = `k_prod * phi * enclosed_mask_scaled` (fires only where `binary_fill_holes(phi>thr) & ~(phi>thr)` marks interior). Use the canonical params. Keep `D < 0.25` (CFL).
- [ ] **Step 2: Run → GREEN.** If the exact step counts differ, use the observed ones (the CONTRAST — closed>0, control==0 — must be unambiguous). Commit.

---

## Task 2: `Protocell` process

**Goal:** wrap the Task-1 physics as a `fields`-store process emitting the boundary-integrity metric + a gated `persists` flag.

**Files:** Create `meta_modelers_guide/protocell/__init__.py` + `autopoiesis.py`; Create `tests/test_protocell.py`.

**Interface:** config `{grid {nx,ny}, D, k_decay, k_prod, thr, dt, steps_per_tick, seed}`; input/output `{fields: map[array]}` holding `phi`. Each tick: read `phi`, advance `steps_per_tick` internal steps (reuse Task-1 functions), emit the DELTA `{"fields": {"phi": phi_new - phi_read}}` (CahnHilliard convention). Observables (`overwrite[float]`): `enclosed_area`, `membrane_mass`, `persists` (1.0 if `enclosed_area>0 AND membrane_mass > mass_floor`, else 0.0), `collapse_tick` (the tick enclosed first hits 0, else -1). Register via `build_core()` (`local:Protocell`) — mirror how `CahnHilliard` is discovered from `condensate/__init__.py`.

- [ ] **Step 1: RED** — `tests/test_protocell.py` (`importorskip("process_bigraph")`): build a Composite with `local:Protocell` (closed-loop params) + a `phi` field seeded as an annulus; run; assert `obs['persists'] == 1.0` and `enclosed_area > 0` at the end; a second composite with `k_prod=0` ends `persists == 0.0`, `enclosed_area == 0`, `collapse_tick > 0`.
- [ ] **Step 2: Implement → GREEN.** Guard `dt`/`D` (assert `D*dt*4 < 1` CFL; raise loudly otherwise, like CahnHilliard's NaN guard). Commit.

---

## Task 3: Two composites (closed loop + vesicle control)

**Files:** Create `meta_modelers_guide/composites/protocell-autopoietic.composite.json` (`k_prod=0.03`) + `protocell-vesicle-control.composite.json` (`k_prod=0.0`). Each: a `fields` store with `phi` seeded as a static Gaussian-annulus array (embed it, deterministic — like study 6's static CH seed) + one `Protocell` (`local:Protocell`) + `RAMEmitter`.

- [ ] **Step 1:** author both JSONs; verify each builds (`test_composites_build.py::test_composite_builds[protocell-autopoietic]` / `[protocell-vesicle-control]`). Both are pure-numpy — confirm they build with NO cpm/cobra/spatio_flux importorskip (adjust the build guard only if needed).
- [ ] **Step 2:** full `-m pytest -q` (no regressions). Commit.

---

## Task 4: Tune + assert the persist-vs-decay regime + multi-seed

**Files:** Create `tests/test_autopoiesis_regime.py`.

- [ ] **Step 1: RED** — `importorskip("process_bigraph")`:
  - `test_closed_loop_persists`: run `protocell-autopoietic`; assert final `persists == 1.0`, `enclosed_area` > 0 (with the mass-held gate), i.e. homeostasis, not a filled blob.
  - `test_vesicle_control_collapses`: run `protocell-vesicle-control`; assert `persists == 0.0`, `enclosed_area == 0`, `collapse_tick > 0` — the boundary dissipates without the internal loop.
  - `test_persistence_is_multiseed_robust`: across ≥5 seeds, the closed loop ends `enclosed_area > 0` every seed and the control ends `== 0` every seed (assert the range/invariant, tolerant of RNG drift — mirror `test_cellcell_multiseed.py`).
- [ ] **Step 2: Run → GREEN** (tune params only if the contrast isn't crisp; the canonical regime already works). Record the observed persist/collapse numbers + multi-seed range in the ledger. Commit.

---

## Task 5: Visualization (membrane holds vs dissolves)

**Files:** Modify `meta_modelers_guide/cpm/viz.py`; Create `tests/test_protocell_viz.py`.

Add `run_protocell_frames(state, core, steps, cadence)` on the shared contract: render `phi` as a heatmap (a membrane colormap), overlay the enclosed-interior mask (or its contour) so the audience sees the enclosed region; one `_pattern_title` ("Autopoiesis — a self-maintaining membrane"); metrics `time`, `enclosed_area`, `membrane_mass`, register a panel kind in `_METRICS_PANEL_DISPATCH`. Bake TWO GIFs (closed loop holding; control dissolving) so the contrast is the visual. Do NOT break the other renderers.

- [ ] **Step 1: RED** — `tests/test_protocell_viz.py` (`importorskip("process_bigraph")`): for the closed-loop composite ≥6 frames, `enclosed_area` metric present and ends > 0, GIF non-empty, metrics HTML with a Plotly div; for the control, `enclosed_area` ends at 0 (dissolves).
- [ ] **Step 2: Implement → GREEN.**
- [ ] **Step 3: Bake** `viz/protocell-autopoietic.gif`, `viz/protocell-vesicle-control.gif`, `viz/autopoiesis-metrics.html` into `workspace/studies/autopoiesis-spatial/viz/`. VIEW frames: closed membrane holds its ring; control's ring thins and vanishes. Commit code; artifacts land in Task 6.

---

## Task 6: Study + investigation + report

**Files:** Create `workspace/studies/autopoiesis-spatial/study.yaml` (+ `viz/`); Modify `investigation.yaml`.

Mirror `workspace/studies/biomolecular-complementarity-spatial/study.yaml` (the new-bar exemplar). Biology-first:
- Question: does the paper's §Self-organized processes autopoiesis criterion hold spatially — a membrane that PERSISTS because an internal production loop, gated on the boundary staying closed, replenishes it against decay, versus a mere vesicle (no loop) that dissipates?
- Lead with the biology (self-maintaining boundary, operational closure, "a membrane alone is insufficient"). Cite by section title (§Self-organized processes) + beer2023 (viability bounds as constraints on shared state). Demote the composition framing to ≤1 sentence.
- Measured outcomes (from Task 4): closed loop persists (enclosed area plateaus ~276, homeostasis) vs control collapses (enclosed 0 by ~step 101); the negative control is the single-variable `k_prod` knockout; multi-seed range.
- HONEST scope: this is a TOY autopoiesis — closure is demonstrated (persistence CAUSED by the internal loop, provable by the knockout + the fatal-puncture viability bound), NOT real membrane chemistry or metabolism; closure is global+binary (maintenance-against-decay, not graded puncture self-repair — a named deferral, add to `docs/superpowers/deferrals.md`). Cite tests. Cross-link the `draft-to-living-cell` analogue `autopoiesis`. Viz refs to both GIFs + metrics.
- Add `autopoiesis-spatial` to investigation.yaml `studies` (keep the Phase-5 scope block).

- [ ] **Step 1:** author study.yaml; wire investigation; add the graded-repair deferral to `deferrals.md`.
- [ ] **Step 2:** `python scripts/lint-workspace.py` OK (no new warnings); yaml parses.
- [ ] **Step 3:** `vivarium-workbench render-loom --study autopoiesis-spatial --max-width 1600 --colors 128` → loom Model figure.
- [ ] **Step 4:** render report; confirm loom + both GIFs + metrics. Do NOT commit generated `reports/*.html`.
- [ ] **Step 5:** full `-m pytest -q` green; deps-absent skip holds; `bash scripts/check-no-local-paths.sh` OK.
- [ ] **Step 6:** commit study + investigation + viz + deferrals.

---

## Self-Review notes
- **Spec coverage:** study 7 (protocell maintaining its own boundary) → Tasks 2–4 + 6; the closure-caused-persistence proven first (Task 1) and by the knockout (Task 4). ✓
- **Negative control** is load-bearing and single-variable (`k_prod=0`); the persist claim is GATED (enclosed area AND mass) so a filled blob can't pass. ✓
- **Honest scope:** toy autopoiesis, global-binary closure, maintenance-not-self-repair — named + deferred. ✓
- **Hardened conventions:** multi-seed range, §-cited, constants/units/deferrals followed; pure-numpy (no cpm/cobra/spatio_flux); delta-write reused. ✓
- **Type consistency:** `phi` delta-write; `overwrite[float]` observables; `_METRICS_PANEL_DISPATCH` explicit registration (no key-sniffing). ✓
