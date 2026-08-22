# Study 5: `molecular-interfaces` (spatial) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build study 5 of `the-cellular-interface-multicellular` — the **molecular interface made spatial** (paper §Molecular interface, Fig 7): a reaction-diffusion enzymatic network where local molecular reactions + differential diffusion produce emergent spatial structure (Turing patterning) — the **chemical** molecular channel — plus a genuinely-coupled **thermal** channel (temperature grading the pattern via Arrhenius), with a causal negative control, on the hardened bar.

**Architecture:** A pure-numpy **Gray-Scott** reaction-diffusion process `GrayScott` over a `fields` store: two species `u`,`v` under `U + 2V → 3V`, `V → P` with `Dv < Du` (differential diffusion) turning a near-uniform noisy seed into Turing spots. An optional `temperature` field modulates the reaction rate by an Arrhenius factor `rate(T)=exp(−Ea·(1/T−1/Tref))` — the thermal channel. The **causal control is the equal-diffusion knockout** (`Du=Dv`, chemistry ON) which suppresses the Turing instability → stays uniform. No cpm/cobra/spatio_flux.

**Tech Stack:** Python, `numpy` (RD physics), `scipy.ndimage.label` (domain count), `process_bigraph`, matplotlib + imageio/Pillow (GIF), Plotly (metrics).

**Spec:** `docs/superpowers/specs/2026-08-21-cellular-interface-multicellular-design.md` (study 5 row). Paper §Molecular interface / Fig 7.
**API map:** `docs/superpowers/api-maps/2026-08-21-molecular-interfaces-api-map.md` — every value below is verified there with a run.

## Global Constraints

- **Worktree discipline:** all work in `~/code/meta-modelers-guide--cpm-multicellular` on branch `study5-molecular-interfaces`. Never commit in the canonical checkout. Verify `git branch --show-current` before each commit. Tests: `PYTHONPATH=~/code/meta-modelers-guide--cpm-multicellular` prepended; interpreter `~/code/meta-modelers-guide/.venv/bin/python`.
- **Physics (verified):** Gray-Scott `du/dt = Du·lap(u) − u·v² + F·(1−u)`, `dv/dt = Dv·lap(v) + u·v² − (F+k)·v`; canonical `Du=0.16, Dv=0.08, F=0.037, k=0.06`, 128×128 periodic grid, `dt=1.0`, `lap`=periodic 5-point. Near-uniform seed = `u≈1, v≈0` + ~2% noise + a few nucleation patches; deterministic RNG (`np.random.default_rng(seed)`). Metric = `v.var()`. Reuse CahnHilliard's **delta-write** (`field_new − field_read` into the additive `fields` store; verified against a reference trajectory). Stability: standard RD CFL, keep the run's dt/D in the verified regime.
- **Pattern-vs-uniform (verified):** reaction ON with `Du≠Dv` → `v_var` 0.0026 → ~0.0117 (Turing spots, ~11 domains). **Equal-diffusion control** (`Du=Dv=0.12`, chemistry ON) → `v_var == 0` (the load-bearing causal control — isolates diffusion-driven instability as the cause). Reaction-off control → `v_var == 0` (secondary).
- **Thermal channel (verified):** an Arrhenius factor `exp(−Ea·(1/T−1/Tref))` multiplying the reaction term grades the pattern (`Ea=0.6`: `v_var` 0.0142→0.0066 as T 0.92→1.08; domains 55→1). Realize it as an optional `temperature` field/scalar in `GrayScott`; when absent, rate factor = 1 (pure chemical). This is a REAL second modality — frame it as such.
- **Metric convention:** `v_var` is the seed-robust pass/fail metric (multi-seed [0.01163, 0.01191], tight); `n_domains` (`scipy.ndimage.label` on `v>thr`) is seed-sensitive (~[10,19]) → report as a RANGE, never a point. Multi-seed convention (mirror `tests/test_cellcell_multiseed.py`): pattern forms (`v_var` above a floor) every seed; the equal-diffusion control stays ~0 every seed.
- **CONSISTENCY EDIT (mandatory, risk #1):** `investigation.yaml`'s `what_this_does_not_demonstrate` currently says "Every study here realizes ONLY the chemical port." Adding the thermal channel makes that false. Task 6 MUST update that block to carve study 5 out (study 5 adds a thermal channel; **electrostatic + mechanical** remain the named gap) and update `docs/superpowers/deferrals.md` accordingly.
- **Databases hook (prose only):** the paper's original claim — PDB/Reactome/ChEBI/GO as "partial specifications of molecular interfaces and their types" — is realized as PROSE framing + typed-port annotation in the study.yaml (name the species/reactions with a ChEBI/Reactome-style identifier as a gesture). A live DB fetch or a real Reactome-fragment mapping is a named DEFERRAL, not scoped in.
- **No cpm/cobra/spatio_flux.** Tests `pytest.importorskip("process_bigraph")` at the composite level; the pure-physics test needs only numpy/scipy. Mirror `tests/test_cahn_hilliard.py`.
- **Hardened conventions:** biology-first study.yaml; cite the paper by SECTION TITLE (§Molecular interface) with `§` anchors; no sibling-counting; honest toy-scope; constants-ledger/units/deferrals followed.

---

## File Structure

- Create: `meta_modelers_guide/molecular/__init__.py` + `meta_modelers_guide/molecular/gray_scott.py` — `GrayScott(Process)` (new subpackage, mirroring `condensate/`/`protocell/`).
- Create: `meta_modelers_guide/composites/molecular-turing-pattern.composite.json` (chemical, Du≠Dv), `molecular-equal-diffusion-control.composite.json` (Du=Dv, causal control), `molecular-thermal-graded.composite.json` (thermal channel — a raised-temperature run showing a coarser pattern).
- Modify: `meta_modelers_guide/cpm/viz.py` — add `run_gray_scott_frames()` on the shared contract (+ its metrics-panel kind in `_METRICS_PANEL_DISPATCH`).
- Create tests: `tests/test_gray_scott_physics.py` (spike), `tests/test_gray_scott.py` (process), `tests/test_molecular_regime.py` (pattern/uniform/thermal/multiseed), `tests/test_gray_scott_viz.py`.
- Modify: `tests/test_composites_build.py` — the molecular composites are pure-numpy; confirm they build with no cpm/cobra/spatio_flux guard.
- Create: `workspace/studies/molecular-interfaces-spatial/study.yaml` (+ `viz/`).
- Modify: `workspace/investigations/the-cellular-interface-multicellular/investigation.yaml` — add `molecular-interfaces-spatial` to `studies` AND update the `what_this_does_not_demonstrate` four-modality block (study 5 adds thermal). Modify `docs/superpowers/deferrals.md` (electrostatic/mechanical channels + real Reactome-fragment mapping).

Tests guard: `import pytest; pytest.importorskip("process_bigraph")` for composite-level tests (numpy/scipy are hard deps already used by shipped code).

---

## Task 1: Gray-Scott physics spike (pattern vs uniform)

**Goal:** prove in a committed test — pure physics, no process — that the reaction-ON `Du≠Dv` arm forms a Turing pattern (`v_var` rises well above 0) while the equal-diffusion control (`Du=Dv`, chemistry ON) AND the reaction-off control both stay uniform (`v_var ≈ 0`), from an identical deterministic seed.

**Files:** Create `tests/test_gray_scott_physics.py`.

- [ ] **Step 1: RED** — implement the Gray-Scott `step` (two-species RD, periodic Laplacian) + the seed builder + the `v_var`/`n_domains` metrics as module-level functions (reused by the process in Task 2). Assert (deterministic `np.random.default_rng(1)` seed):
  - reaction ON, `Du=0.16, Dv=0.08`, ~8000 steps → `v.var()` ends clearly above a floor (e.g. > 0.005; observed ~0.0117) and `n_domains > 1` (a real pattern);
  - **equal-diffusion control** (`Du=Dv=0.12`, chemistry ON), identical seed → `v.var()` ≈ 0 (e.g. < 1e-4);
  - reaction-off control (drop the `u·v²` term) → `v.var()` ≈ 0.
  The contrast (patterned `v_var` ≫ 0 vs controls ≈ 0) must be unambiguous.
- [ ] **Step 2: Run → GREEN** (use observed values if step counts differ). Commit.

---

## Task 2: `GrayScott` process (chemical + optional thermal)

**Goal:** wrap the physics as a `fields`-store process emitting the pattern-formation metric + a `patterned` flag, with the optional thermal (Arrhenius) rate modulation.

**Files:** Create `meta_modelers_guide/molecular/__init__.py` + `gray_scott.py`; Create `tests/test_gray_scott.py`.

**Interface:** config `{grid {nx,ny}, Du, Dv, F, k, dt, steps_per_tick, thr, seed, Ea, Tref}` (Ea/Tref only used when a `temperature` field is present). input/output `{fields: map[array]}` holding `u`, `v` (and optionally `temperature`). Each tick: read `u`,`v` (+ `temperature` if present), advance `steps_per_tick` RD steps (reaction term scaled by the Arrhenius factor when a temperature field is present), emit DELTAS `{"fields": {"u": u_new−u_read, "v": v_new−v_read}}` (CahnHilliard convention — verify the store ends holding the new fields). Observables (`overwrite[float]`): `v_var`, `n_domains`, `patterned` (1.0 iff `v_var > pattern_floor`). Register via `build_core()` (`local:GrayScott`) — mirror `CahnHilliard` discovery from a new `molecular/__init__.py`.

- [ ] **Step 1: RED** — `tests/test_gray_scott.py` (`importorskip("process_bigraph")`): build a Composite with `local:GrayScott` (canonical params, `u`/`v` seeded) run ~8000 steps (via steps_per_tick × ticks) → assert `obs['patterned'] == 1.0` and `v_var > floor`; a second composite with `Du=Dv` → `patterned == 0.0`, `v_var ≈ 0`. Confirm the delta-write leaves the store holding the evolved fields (cross-check like `test_cahn_hilliard.py`).
- [ ] **Step 2: Implement → GREEN.** Commit.

---

## Task 3: Three composites + build guard

**Files:** Create `molecular-turing-pattern.composite.json` (Du≠Dv), `molecular-equal-diffusion-control.composite.json` (Du=Dv, causal control), `molecular-thermal-graded.composite.json` (a `temperature` field raised so the Arrhenius factor coarsens the pattern — the thermal channel). Each: a `fields` store with a STATIC deterministic `u`/`v` seed array (embed it, like study 6's static CH seed) + the `GrayScott` process + `RAMEmitter`. The thermal composite also seeds a `temperature` field.

- [ ] **Step 1:** author the JSONs; verify each builds (`test_composite_builds[molecular-turing-pattern]` etc.). Pure-numpy — no importorskip needed in the build guard (confirm).
- [ ] **Step 2:** full `-m pytest -q` (no regressions). Commit.

---

## Task 4: Tune + assert (pattern / control / thermal / multi-seed)

**Files:** Create `tests/test_molecular_regime.py` (`importorskip("process_bigraph")`).

- [ ] **Step 1: RED**:
  - `test_turing_pattern_forms`: run `molecular-turing-pattern`; assert final `patterned == 1.0`, `v_var > floor`, `n_domains > 1`.
  - `test_equal_diffusion_control_stays_uniform`: run `molecular-equal-diffusion-control`; assert `patterned == 0.0`, `v_var ≈ 0` — the causal control (Turing instability removed).
  - `test_thermal_channel_grades_the_pattern`: run `molecular-thermal-graded` vs the base pattern; assert the raised-temperature run yields a MEASURABLY different pattern (coarser: fewer `n_domains` and/or lower `v_var` per the Arrhenius grading) — a real second modality.
  - `test_pattern_is_multiseed_robust`: across ≥5 seeds, `v_var` above the floor every seed (report the range); `n_domains` reported as a range (seed-sensitive — do NOT assert a point).
- [ ] **Step 2: Run → GREEN** (tune only if needed; the canonical regime works). Record the observed `v_var` range + thermal grading in the ledger. Commit.

---

## Task 5: Visualization (Turing pattern emerging)

**Files:** Modify `meta_modelers_guide/cpm/viz.py`; Create `tests/test_gray_scott_viz.py`.

Add `run_gray_scott_frames(state, core, steps, cadence)` on the shared contract: render the `v` field as a heatmap (a molecular colormap) as the Turing spots emerge from the near-uniform seed; one `_pattern_title` ("Molecular interfaces — reaction-diffusion patterning"); metrics `time`, `v_var`, `n_domains`, register a panel kind in `_METRICS_PANEL_DISPATCH` (plot `v_var` rising). Bake the pattern GIF (+ optionally the thermal-graded one for contrast). Do NOT break the other renderers.

- [ ] **Step 1: RED** — `tests/test_gray_scott_viz.py` (`importorskip("process_bigraph")`): run the pattern composite; ≥6 frames, `v_var` metric present and ends > 0, GIF non-empty, metrics HTML with a Plotly div.
- [ ] **Step 2: Implement → GREEN.**
- [ ] **Step 3: Bake** `viz/molecular-turing-pattern.gif` + `viz/molecular-metrics.html` (and optionally `viz/molecular-thermal-graded.gif`) into `workspace/studies/molecular-interfaces-spatial/viz/`. VIEW frames: spots emerge from near-uniform. Commit code; artifacts land in Task 6.

---

## Task 6: Study + investigation + report (+ four-modality consistency edit)

**Files:** Create `workspace/studies/molecular-interfaces-spatial/study.yaml` (+ `viz/`); Modify `investigation.yaml` + `docs/superpowers/deferrals.md`.

Mirror `workspace/studies/autopoiesis-spatial/study.yaml` (a recent new-bar exemplar). Biology-first:
- Question: does the paper's §Molecular interface (Fig 7) hold spatially — local molecular reactions + differential diffusion producing emergent spatial structure (the chemical channel), with temperature grading it (the thermal channel), as a demonstration that a molecular interface's channels can be composed spatially?
- Lead with the biology (molecular interfaces, the four channels, reaction-diffusion/Turing patterning). Cite the paper by section title (§Molecular interface). Realize the **databases-as-partial-specifications** claim in prose (name the species/reactions with ChEBI/Reactome-style identifiers as typed-port annotation; the paper's original claim that PDB/Reactome/ChEBI/GO are partial specs of molecular interfaces + their types) — a real Reactome-fragment mapping is a named deferral.
- Measured outcomes (from Task 4): pattern forms (`v_var` ~0.0026→~0.0117, ~11 domains) vs equal-diffusion control uniform (`v_var≈0`); the thermal channel grades the pattern; multi-seed `v_var` range; `n_domains` as a range.
- HONEST scope + the FOUR-MODALITY findings: study 5 realizes the **chemical + thermal** channels spatially; **electrostatic + mechanical remain the gap** (consistent with the updated investigation.yaml block). This is a TOY reaction-diffusion demonstration — NOT real molecular structure/conformation (PDB-level) — name what's demonstrated vs not. Cite tests. Cross-link `draft-to-living-cell/molecular-interfaces` (which made ONE molecule's four channels executable at a point; this makes the chemical channel spatial).
- Viz refs: the pattern GIF (+ thermal if baked) + metrics.
- **Consistency edit:** update `investigation.yaml`'s `what_this_does_not_demonstrate` — study 5 adds the thermal channel; electrostatic + mechanical remain the four-modality gap. Update `deferrals.md` (electrostatic/mechanical channels; real Reactome-fragment mapping; live DB fetch).

- [ ] **Step 1:** author study.yaml; wire investigation; update the four-modality block + deferrals.
- [ ] **Step 2:** `python scripts/lint-workspace.py` OK (no new warnings; §Molecular interface anchor, Fig 7); yaml parses.
- [ ] **Step 3:** `vivarium-workbench render-loom --study molecular-interfaces-spatial --max-width 1600 --colors 128` → loom Model figure.
- [ ] **Step 4:** render report; confirm loom + GIF(s) + metrics. Do NOT commit generated `reports/*.html`.
- [ ] **Step 5:** full `-m pytest -q` green; deps-absent skip holds; `bash scripts/check-no-local-paths.sh` OK.
- [ ] **Step 6:** commit study + investigation + deferrals + viz + loom.

---

## Self-Review notes
- **Spec coverage:** study 5 (spatial reaction-diffusion enzymatic network — the chemical channel; electrical/thermal/mechanical as coupled fields) → chemical (Tasks 2–4) + thermal (Task 2/3/4) + the four-modality gap named honestly (Task 6). ✓
- **Causal control:** the equal-diffusion knockout (isolates the Turing mechanism) — Tasks 1 & 4. ✓
- **Consistency:** the four-modality block edit is mandatory (Task 6) — adding thermal must not leave the shared honesty prose stale. ✓
- **Hardened conventions:** multi-seed (`v_var` range, `n_domains` range), §-cited, deferrals updated, pure-numpy (no cpm/cobra/spatio_flux), delta-write reused. ✓
- **Type consistency:** `u`/`v` delta-write; `overwrite[float]` observables; `_METRICS_PANEL_DISPATCH` explicit registration. ✓
