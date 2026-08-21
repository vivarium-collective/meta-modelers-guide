# Study 3: `cell-cell-coupling` (spatial) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build study 3 of `the-cellular-interface-multicellular` — N CPM cells sharing one diffusing nutrient field, each running its own dynamic FBA, demonstrating two regimes: **competitive exclusion** (two glucose competitors, the faster out-grows the slower) and **cross-feeding** (a glucose→acetate secretor sustains an acetate-consuming neighbor via a diffusing plume) — composed from independent frameworks, with GIF + synced per-cell metrics and a study + report.

**Architecture:** A new world-owning process `CpmColonyField` owns ONE CPM world holding N cells and loops the flagship's read-field → dFBA → writeback → set-target-volume body over each live cell id (ids `1..n`, skipping id 0 = medium). Each cell carries its own cobra `e_coli_core` model copy with its own exchange bounds (competitor / secretor / consumer). It composes over the shared `fields` grid with spatio-flux `DiffusionAdvection` exactly as the flagship does. The merged flagship `CpmCellField` is left untouched.

**Tech Stack:** Python, `process_bigraph`, `cpm` (viva-cpm; Rust `cpm_core`), `spatio_flux` (`DiffusionAdvection`), `cobra` (`e_coli_core` / `load_model("textbook")`), matplotlib + imageio/Pillow (GIF), Plotly (metrics panel).

**Spec:** `docs/superpowers/specs/2026-08-21-cellular-interface-multicellular-design.md` (study 3 row).
**API map:** `docs/superpowers/api-maps/2026-08-21-cell-cell-coupling-api-map.md` (every API claim below is verified there).

## Global Constraints

- **Worktree discipline:** all work in `~/code/meta-modelers-guide--cpm-multicellular` on branch `study3-cell-cell-coupling`. Never commit in the canonical checkout. Verify `git branch --show-current` before each commit. Tests run with `PYTHONPATH=~/code/meta-modelers-guide--cpm-multicellular` prepended; interpreter `~/code/meta-modelers-guide/.venv/bin/python`.
- **Per-cell values are LISTS indexed by cell id, index 0 = medium.** `world.cell_coms()`, `world.cell_volumes()`, `world.cell_types()` return Python lists; iterate ids `1..n_cells`, never `.get()`/`.keys()`. Per-cell footprint = `snapshot().reshape(ny,nx) == cid`.
- **Full import-path process addresses:** `local:!spatio_flux.processes.diffusion_advection.DiffusionAdvection`. The in-repo `CpmColonyField` registers via `build_core()` and is addressed `local:CpmColonyField`.
- **Shared-grid contract:** all arrays `(ny, nx)`=(rows,cols); x=cols, y=rows; CPM dims == spatio-flux `n_bins`; `snapshot()` is flat `x + y*nx` → reshape `(ny,nx)`; spatio-flux needs square cells (`bounds == n_bins`).
- **`seed_block` half-open, `z0,z1 = 0,1` for 2D** (`z1=0` → empty world); `[x0,y0,z0,x1,y1,z1]`, `x1=x0+width`. Seed blocks must NOT overlap.
- **`DiffusionAdvection.update()` returns DELTAS** the engine applies; `CpmColonyField`'s `fields` output is likewise a summed spatial delta (nonzero only on footprints). Footprints are disjoint (CPM guarantees each pixel belongs to one id) so per-cell deltas sum safely and conserve mass when each cell clamps removal against its own pixels' current sum.
- **Absolute observables use `overwrite[...]`:** per-cell `volume`, `position`, `local_nutrient`, `biomass` are per-tick absolute readings → declare `overwrite`. `acetate_secreted` is a genuine per-tick delta → plain additive `float`.
- **O2 cap forces overflow:** a secretor needs `EX_o2_e.lower_bound = -oxygen_vmax` (~ -15) to emit acetate; unbounded O2 → pure respiration → `EX_ac_e = 0`. A consumer needs O2 uncapped (~ -20) to respire acetate.
- **Trust `sol.fluxes` only when `sol.status == "optimal"`** — an infeasible re-solve returns stale primal values. Guard per cell.
- **Per-cell cobra model copies** (decision from API-map risk #2): each cell owns its own `load_model` instance; do NOT share one model and reset bounds (bound leakage between cells). Only 2–4 cells, so N copies is cheap and safe.
- **Toy-real:** plausible constants, not a fitted organism; keep the honest-framing conventions of `draft-to-living-cell`.

---

## File Structure

- Create: `meta_modelers_guide/cpm/colony_field.py` — `CpmColonyField(Process)` (owns one N-cell world; per-cell dFBA + growth + field writeback).
- Create: `meta_modelers_guide/composites/cellcell-compete.composite.json` — competition regime.
- Create: `meta_modelers_guide/composites/cellcell-crossfeed.composite.json` — cross-feeding regime.
- Modify: `meta_modelers_guide/cpm/viz.py` — add `run_colony_frames()` + multi-cell frame rendering (reuse `frames_to_gif`/`metrics_panel`).
- Create: `tests/test_cpm_colony_two_writer.py` — the two-writer field-delta spike (retires API-map risk #1).
- Create: `tests/test_cpm_colony_field.py` — `CpmColonyField` per-cell dFBA + growth + writeback.
- Create: `tests/test_cellcell_regimes.py` — competition (divergent biomass) + cross-feeding (both viable, acetate handoff) demonstrating metrics.
- Create: `tests/test_cpm_colony_viz.py` — GIF + per-cell metrics panel.
- Create: `workspace/studies/cell-cell-coupling-spatial/study.yaml` (+ `viz/`).
- Modify: `workspace/investigations/the-cellular-interface-multicellular/investigation.yaml` — add `cell-cell-coupling-spatial` to `studies`.

Every new test guards optional frameworks so the base CI image skips cleanly (matching the merged flagship tests):
```python
import pytest
pytest.importorskip("cobra")      # colony dFBA needs COBRApy
pytest.importorskip("cpm")        # + spatial frameworks absent from base CI
pytest.importorskip("spatio_flux")
```

---

## Task 1: Two-writer field-delta spike (retire risk #1)

**Goal:** prove in a REAL `process_bigraph.Composite` that two disjoint CPM-cell footprints writing into the same `map[array]` `fields` store sum correctly and conserve mass — before any dFBA is trusted. Uses a throwaway minimal 2-writer process, not `CpmColonyField`.

**Files:** Create `tests/test_cpm_colony_two_writer.py`.

- [ ] **Step 1: Write the failing test (RED)**

```python
# tests/test_cpm_colony_two_writer.py
"""Two disjoint footprint deltas summed into one shared map[array] fields store
conserve mass — the additive-writer assumption the colony process relies on."""
from __future__ import annotations
import numpy as np
import pytest
from process_bigraph import Composite, Process
from meta_modelers_guide.core import build_core

pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")

NX = NY = 20

class _TwoWriter(Process):
    """Removes 1.0 glucose from each of two disjoint single-pixel footprints per tick."""
    config_schema = {}
    def inputs(self):  return {"fields": "map[array]"}
    def outputs(self): return {"fields": "map[array]"}
    def update(self, state, interval):
        d = np.zeros((NY, NX))
        d[5, 5] = -1.0      # cell-1 pixel
        d[5, 15] = -1.0     # cell-2 pixel (disjoint)
        return {"fields": {"glucose": d}}

def test_two_disjoint_writers_sum_and_conserve():
    core = build_core()
    core.register_process("_TwoWriter", _TwoWriter)
    field = np.full((NY, NX), 10.0)
    state = {
        "fields": {"glucose": field},
        "w": {"_type": "process", "address": "local:_TwoWriter", "config": {},
              "inputs": {"fields": ["fields"]}, "outputs": {"fields": ["fields"]}},
    }
    comp = Composite({"state": state}, core=core)
    before = float(np.sum(comp.state["fields"]["glucose"]))
    comp.run(3)
    g = comp.state["fields"]["glucose"]
    assert g[5, 5] == pytest.approx(7.0)     # 10 - 3*1
    assert g[5, 15] == pytest.approx(7.0)     # both writers applied, independently
    assert float(np.sum(g)) == pytest.approx(before - 6.0)  # 2 pixels * 3 ticks
```

- [ ] **Step 2: Run it** — `PYTHONPATH=$PWD ~/code/meta-modelers-guide/.venv/bin/python -m pytest tests/test_cpm_colony_two_writer.py -v`. If `register_process` is not the exact core API, read `meta_modelers_guide/core.py` and the flagship's registration to use the correct call. Expected: GREEN once the additive semantics hold. If mass is NOT conserved or a writer is lost, STOP — the whole colony design rests on this; ledger the finding.
- [ ] **Step 3: Commit** — `git add tests/test_cpm_colony_two_writer.py && git commit`.

---

## Task 2: `CpmColonyField` — N cells, per-cell dFBA + growth

**Goal:** a world-owning process generalizing the flagship's single-cell loop to N cells with per-cell roles.

**Files:** Create `meta_modelers_guide/cpm/colony_field.py`; Create `tests/test_cpm_colony_field.py`.

**Interfaces:**
- Consumes (config): `grid` `{nx, ny}`; `cells`: list of per-cell dicts `{seed_block, role, glucose_vmax, oxygen_vmax, acetate_vmax, target_volume, lambda_volume}` where `role ∈ {"competitor","secretor","consumer"}`; `contact`: list of `{a,b,j}`; `box_volume_L`, `grow_per_biomass`, `mcs` (as the flagship).
- Consumes (ports): `inputs {fields: map[array]}` (needs `glucose`, and `acetate` for cross-feeding).
- Produces (ports): `outputs` = `fields: map[array]` (summed delta) + per-cell observables keyed by id string: `volume: overwrite[map[float]]`, `position: overwrite[map[list]]`, `local_glucose: overwrite[map[float]]`, `local_acetate: overwrite[map[float]]`, `biomass: overwrite[map[float]]`, `acetate_secreted: map[float]`.

Read `meta_modelers_guide/cpm/cell_field.py` in full first and mirror its structure (world construction, `_footprint`, `_fba`, mass-conservative writeback, growth). Key differences, all verified in the API map:

- Build the world from `spec["cells"] = [ {type:1, target_volume, lambda_volume, target_surface:0, lambda_surface:0, seed_block} for each cell ]`, plus `contact` including a `{a:1,b:1,j:...}` cell↔cell term.
- Hold `self._models = {cid: load_model("textbook") for cid in live_ids}` — one copy per cell; set each cell's static bounds once at init from its role (see below), MM-limit the dynamic uptake per tick.
- Track `self.biomass = {cid: init_biomass}`.
- Per tick: read `glucose`/`acetate` snapshots once; then `for cid in live_ids`: mask footprint `lat==cid`; MM-limit that cell's substrate vmax on its footprint-local mean concentration; solve; guard `sol.status=="optimal"`; accumulate this cell's `fields` delta on its own pixels (per-pixel proportional, clamped against its own pixels' current sum, exactly as flagship); update `self.biomass[cid]`; `world.set_target_volume(cid, max(grow_per_biomass*biomass[cid], 0.0))`. After all cells: one `world.step(mcs)`.
- Roles (verified bounds): `competitor` — glucose on (`EX_glc__D_e.lower_bound=-glucose_vmax`), `EX_o2_e.lower_bound=-oxygen_vmax` (~15), acetate secrete-only. `secretor` — same as competitor (its overflow acetate is the cross-feed source). `consumer` — `EX_glc__D_e.lower_bound=0`, `EX_ac_e.lower_bound=-acetate_vmax` (flip negative → uptake), `EX_o2_e.lower_bound=-20` (uncapped-ish). Read `sol.fluxes["EX_ac_e"]`: >0 secreted (add to `acetate` delta on footprint), <0 consumed (remove from `acetate` on footprint, clamped).
- `live_ids = sorted(set(np.unique(snapshot)) - {0})` — re-derive each tick so a cell that shrank to area 0 (target→0) is simply skipped; never trust a cached id list. Guard growth math with `area = max(fp.sum(), 1)`.

- [ ] **Step 1: Write the failing test (RED)**

```python
# tests/test_cpm_colony_field.py
"""CpmColonyField: two cells read their own footprints on a shared glucose grid,
run dFBA independently, grow from biomass, and write disjoint field deltas."""
from __future__ import annotations
import numpy as np
import pytest
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

pytest.importorskip("cobra"); pytest.importorskip("cpm"); pytest.importorskip("spatio_flux")

NX = NY = 40

def _state(core):
    glucose = np.full((NY, NX), 8.0)
    return {
        "fields": {"glucose": glucose, "acetate": np.zeros((NY, NX))},
        "colony": {"_type": "process", "address": "local:CpmColonyField",
            "config": {
                "grid": {"nx": NX, "ny": NY},
                "box_volume_L": 0.3, "grow_per_biomass": 40.0, "mcs": 3,
                "cells": [
                    {"seed_block": [8, 16, 0, 15, 23, 1],  "role": "competitor",
                     "glucose_vmax": 10.0, "oxygen_vmax": 15.0, "target_volume": 50.0, "lambda_volume": 2.0},
                    {"seed_block": [25, 16, 0, 32, 23, 1], "role": "competitor",
                     "glucose_vmax": 4.0,  "oxygen_vmax": 15.0, "target_volume": 50.0, "lambda_volume": 2.0},
                ],
                "contact": [{"a": 0, "b": 1, "j": 14.0}, {"a": 1, "b": 1, "j": 14.0}],
            },
            "inputs": {"fields": ["fields"]},
            "outputs": {"fields": ["fields"], "volume": ["obs", "volume"],
                        "biomass": ["obs", "biomass"], "local_glucose": ["obs", "local_glucose"]},
        },
    }

def test_two_cells_metabolize_grow_and_deplete_disjointly():
    core = build_core()
    comp = Composite({"state": _state(core)}, core=core)
    g0 = comp.state["fields"]["glucose"].copy()
    comp.run(9)
    obs = comp.state["obs"]
    assert set(obs["biomass"].keys()) == {"1", "2"}          # two live cells, id-keyed
    assert obs["biomass"]["1"] > obs["biomass"]["2"]          # faster competitor has more biomass
    assert obs["volume"]["1"] > obs["volume"]["2"]            # ...and more lattice volume
    g1 = comp.state["fields"]["glucose"]
    assert g1.sum() < g0.sum()                                # glucose consumed overall
    assert g1.min() >= -1e-9                                  # never negative anywhere
```

- [ ] **Step 2: Run → iterate to GREEN.** Fix real API mismatches by reading the flagship + cpm source (do not fabricate signatures). Expected: PASS.
- [ ] **Step 3: Commit.**

---

## Task 3: Two regime composites

**Goal:** author the competition and cross-feeding composites in the discovered `composites/` dir (so the loom Model figure bakes automatically, as the flagship fix established).

**Files:** Create `meta_modelers_guide/composites/cellcell-compete.composite.json`, `meta_modelers_guide/composites/cellcell-crossfeed.composite.json`.

Each composite: a `state` with `fields` (`glucose`, and `acetate` for crossfeed), a `DiffusionAdvection` process (full address; `n_bins=(NX,NY)`, `bounds=(NX,NY)`, per-field diffusion coeffs, neumann BC) over `fields`, a `CpmColonyField` (`local:CpmColonyField`) over the shared `fields` + `obs`, and a `RAMEmitter`. Grid 60×60.

- **compete:** two `competitor` cells, glucose_vmax 10 vs 4, seeded left/right on a glucose field (uniform ~3.0 or a mild gradient). Acetate field optional.
- **crossfeed:** one `secretor` (glucose_vmax 10, oxygen_vmax 15) + one `consumer` (glucose off, acetate_vmax 10, oxygen_vmax 20), seeded a tuned distance apart; glucose field feeds the secretor, `acetate` field (diffusion coeff high enough to reach the consumer) carries the handoff.

- [ ] **Step 1: RED** — extend `tests/test_composites_build.py` is unnecessary (its glob auto-discovers both new composites and its guards already `importorskip("spatio_flux")`/`("cpm")` on `CpmColonyField`). Instead add a focused build+smoke assertion inside Task 4's regime test. For this task, write both JSON files and verify each builds:
  `PYTHONPATH=$PWD ... -m pytest "tests/test_composites_build.py::test_composite_builds[cellcell-compete]" "tests/test_composites_build.py::test_composite_builds[cellcell-crossfeed]" -v`
  (Confirm `CpmColonyField` appears in each composite's addresses so the guard keys on it — if the guard string is `"CpmColonyField"`, the existing `if "CpmCellField" in raw` check will MISS it; update that guard to also match `CpmColonyField`.)
- [ ] **Step 2:** update the `test_composites_build.py` guard so `if "CpmCellField" in raw or "CpmColonyField" in raw: pytest.importorskip("cpm")`.
- [ ] **Step 3:** run the two parametrized build cases → GREEN.
- [ ] **Step 4: Commit.**

---

## Task 4: Tune + assert the two demonstrating regimes

**Goal:** the numbers must actually show competitive exclusion and a cross-feeding handoff over a bounded run.

**Files:** Create `tests/test_cellcell_regimes.py`.

- [ ] **Step 1: Write the failing test (RED)**

```python
# tests/test_cellcell_regimes.py
"""The two cell-cell regimes are legible over a bounded run: competition => divergent
biomass; cross-feeding => both cells viable via an acetate handoff."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pytest
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

pytest.importorskip("cobra"); pytest.importorskip("cpm"); pytest.importorskip("spatio_flux")
COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"

def _run(name, steps):
    core = build_core()
    state = json.loads((COMPOSITES / f"{name}.composite.json").read_text())["state"]
    comp = Composite({"state": state}, core=core)
    comp.run(steps)
    return comp.state["obs"]

def test_competition_excludes_the_slower_cell():
    obs = _run("cellcell-compete", 20)
    # faster competitor (id 1) ends with materially more biomass AND volume
    assert obs["biomass"]["1"] > 1.5 * obs["biomass"]["2"]
    assert obs["volume"]["1"] > obs["volume"]["2"]

def test_crossfeeding_keeps_the_consumer_viable():
    obs = _run("cellcell-crossfeed", 20)
    # consumer (id 2) has ~no local glucose yet grows — it must be living on acetate
    assert obs["local_glucose"]["2"] < 0.5
    assert obs["biomass"]["2"] > obs_initial_biomass()  # grew despite no glucose
    assert obs["local_acetate"]["2"] > 0.0              # acetate plume reached it

def obs_initial_biomass():
    return 0.05  # matches CpmColonyField init biomass; adjust to the value chosen in Task 2
```

- [ ] **Step 2: Run → TUNE.** Adjust seed positions, `glucose_vmax` gap, `grow_per_biomass`, acetate diffusion coeff, and secretor→consumer spacing in the composites until both tests pass. Budget iteration here (API-map risk #3). Record the final tuned constants in the ledger.
- [ ] **Step 3: Commit** (composites + test together).

---

## Task 5: Multi-cell visualization

**Goal:** a GIF of both cells over the field(s) + a synced per-cell metrics panel, for each regime.

**Files:** Modify `meta_modelers_guide/cpm/viz.py`; Create `tests/test_cpm_colony_viz.py`.

Add `run_colony_frames(state, core, steps, cadence) -> (frames, metrics)` mirroring the flagship's `run_flagship_frames`, but reaching the live world via the colony process instance and rendering per-cell: color the lattice by cell id (distinct colors), overlay the glucose field, and (crossfeed) an acetate panel. `metrics` holds per-cell arrays (`biomass[cid]`, `volume[cid]`, `local_glucose[cid]`, `local_acetate[cid]`) sharing one `time` axis. Reuse `frames_to_gif` and `metrics_panel` (extend the panel to plot per-cell traces; keep `include_plotlyjs` param).

- [ ] **Step 1: RED** — `tests/test_cpm_colony_viz.py`: run ≥16 steps on `cellcell-crossfeed`, assert ≥6 frames, per-cell metric arrays present and equal length, GIF file written non-empty, metrics HTML written and contains a Plotly div.
- [ ] **Step 2: Implement → GREEN.**
- [ ] **Step 3: Bake** the GIF + metrics into `workspace/studies/cell-cell-coupling-spatial/viz/` for both regimes (or the more illustrative one + a competition GIF). Commit code; viz artifacts committed with the study in Task 6.

---

## Task 6: Study + investigation + report

**Goal:** author the study, wire it into the investigation, render the report with the baked loom Model figure(s) and viz.

**Files:** Create `workspace/studies/cell-cell-coupling-spatial/study.yaml` (+ `viz/`); Modify `workspace/investigations/the-cellular-interface-multicellular/investigation.yaml`.

Model the study.yaml on the flagship's `cell-environment-coupling-spatial/study.yaml` (schema_version 4): baseline references the two composite ids (`meta_modelers_guide.composites.cellcell-compete`, `...cellcell-crossfeed`); cite the tests; honest caveats (toy-real dFBA; two-writer additivity now runtime-verified in Task 1; exclusion/handoff are tuned demonstrations not fitted; per-cell cobra copies); cross-link to the `draft-to-living-cell` analogue `cell-cell-coupling`; viz refs to the GIF(s) (`image:`) + metrics (`html:`).

- [ ] **Step 1:** author `study.yaml`; add `cell-cell-coupling-spatial` to the investigation's `studies:` list.
- [ ] **Step 2:** `lint-workspace.py` clean (only the pre-existing dash-in-name warning is acceptable).
- [ ] **Step 3:** bake the loom Model figure(s): `render-loom --study cell-cell-coupling-spatial --max-width 1600 --colors 128` (composites are in the discovered dir, so both build).
- [ ] **Step 4:** render the investigation report (`scripts/render_report.py` / workbench) and verify the study section shows the loom Model figure (not the schematic) + the GIF + interactive metrics. Do NOT commit a generated `reports/*.html` (gitignored).
- [ ] **Step 5:** run the FULL suite (`PYTHONPATH=$PWD ... -m pytest -q`) — expect all green, new colony tests included; confirm the CI-condition skip still holds (deps-blocked run exits 0).
- [ ] **Step 6: Commit** the study + investigation + viz artifacts.

---

## Self-Review notes

- **Spec coverage:** study 3 row (competition + cross-feeding, dFBA each, shared field) → Tasks 2–4 + 6. ✓
- **Risk #1 (two-writer additivity):** retired first, Task 1. ✓
- **Risk #2 (bound leakage):** per-cell cobra copies, Global Constraints + Task 2. ✓
- **Risk #3 (legibility):** explicit tuning budget, Task 4. ✓
- **Type consistency:** per-cell observables are id-string-keyed `map[...]` with `overwrite` on absolutes throughout (Tasks 2, 4, 5). The Task 3 build-guard string (`CpmColonyField`) is reconciled with `test_composites_build.py` in Task 3 Step 2.
- **CI:** every new test carries the `importorskip("cobra"/"cpm"/"spatio_flux")` guard so the base CI image skips (matches merged flagship). ✓
