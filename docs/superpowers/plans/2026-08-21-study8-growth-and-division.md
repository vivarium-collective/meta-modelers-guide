# Study 8: `growth-and-division` (spatial) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build study 8 of `the-cellular-interface-multicellular` — a CPM cell that **grows** (volume target driven by metabolism at its footprint) and **divides** at a volume threshold into two daughters, compounding 1→2→4 (paper Fig 10a,b) — composed from independent frameworks, with a lineage GIF + synced metrics (n_cells staircase, per-cell-volume sawtooth) and a study + report.

**Architecture:** A new world-owning process `CpmGrowthDivision` (modeled on the merged `CpmColonyField`) runs the flagship dFBA→biomass→`set_target_volume` growth body over every live cell id each tick, `world.step()`s, then calls the NATIVE `world.divide_cells(vol_threshold, reset_target)` — which splits every cell over the threshold along its long axis (mass-conserved; parent keeps id, one new id per split) and resets daughters' targets. The process folds new daughter ids into per-cell biomass bookkeeping so growth resumes from each daughter. Composed over the shared `fields` grid with spatio-flux `DiffusionAdvection` as the flagship does.

**Tech Stack:** Python, `process_bigraph`, `cpm` (viva-cpm; Rust `cpm_core`, native `divide_cells`), `spatio_flux` (`DiffusionAdvection`), `cobra` (`e_coli_core` — metabolism-driven growth), `scipy`/matplotlib + imageio/Pillow (GIF), Plotly (metrics).

**Spec:** `docs/superpowers/specs/2026-08-21-cellular-interface-multicellular-design.md` (study 8 row: "CPM cell grows (volume target driven by metabolism) and divides at threshold").
**API map:** `docs/superpowers/api-maps/2026-08-21-growth-and-division-api-map.md` — every API claim below is verified there with a run snippet.

## Global Constraints

- **Worktree discipline:** all work in `~/code/meta-modelers-guide--cpm-multicellular` on branch `study8-growth-division`. Never commit in the canonical checkout. Verify `git branch --show-current` before each commit. Tests run with `PYTHONPATH=~/code/meta-modelers-guide--cpm-multicellular` prepended; interpreter `~/code/meta-modelers-guide/.venv/bin/python`.
- **Native division:** `world.divide_cells(threshold, reset_target)` divides ALL cells with `volume >= threshold` in one call (NOT per-id): split ⟂ the longest bbox axis, mass-conserved, **parent keeps its id + one NEW id per split**, engine sets both daughters' `target_volume = reset_target`, returns the list of new ids. The native threshold check IS the trigger — call it once per tick after `step()`; below-threshold cells no-op.
- **Growth is metabolism-driven (reuse the colony dFBA path):** each tick, per live cell id, read footprint-local glucose, run `e_coli_core` dFBA (MM-limited uptake, `EX_o2_e` cap), accumulate `self.biomass[cid]`, `set_target_volume(cid, grow_per_biomass * biomass[cid])`. Mass-conservative field writeback, cobra `sol.status == "optimal"` guard, per-cell cobra model copies — all exactly as `colony_field.py`.
- **Daughter bookkeeping (avoid infinite re-division):** capture `vols_before = cell_volumes()` before `divide_cells`; after it, for every cid that is newly present (in the returned new ids) OR whose volume dropped (divided, `vols_after[cid] < vols_before[cid]`), set `self.biomass[cid] = reset_target / grow_per_biomass` so its biomass-driven target equals `reset_target` (no instantaneous jump back over the threshold). Undivided cells keep their accumulated biomass. Re-derive live ids from `np.unique(snapshot()) - {0}` every tick.
- **Phantom-daughter guard:** dividing a cell too small to split cleanly creates a zero-volume phantom that inflates `n_cells()`. Floor `vol_threshold` well above ~8 px, and always drive per-cell logic off `live_ids` derived from `snapshot()` (a zero-area id is skipped); guard `area = max(fp.sum(), 1)`.
- **Field depletion:** metabolism-driven growth plateaus as the shared glucose field depletes. The composite must supply enough glucose (large initial concentration and/or a replenishment source) that the cell reaches the division threshold for at least 2 generations (1→2→4). Tuned in Task 4.
- **Full import-path process addresses:** `local:!spatio_flux.processes.diffusion_advection.DiffusionAdvection`. In-repo `CpmGrowthDivision` registers via `build_core()` (auto-scan, `core.register_link`), addressed `local:CpmGrowthDivision`.
- **Shared-grid contract:** arrays `(ny,nx)`=(rows,cols); x=cols,y=rows; CPM dims == spatio-flux `n_bins`; `snapshot()` flat `x+y*nx` → reshape `(ny,nx)`; `DiffusionAdvection.update()` returns DELTAS; spatio-flux needs square cells (`bounds == n_bins`).
- **`cell_volumes()`/`cell_coms()` are LISTS indexed by id, element `[0]` = medium** — iterate ids `1..n`, never `.get()`.
- **`overwrite[...]` on absolute observables:** per-cell `volume`, `position`, `biomass`, `local_glucose`, and scalar `n_cells`, `total_volume`, `generation_max` are per-tick absolute readings → `overwrite[...]`. `acetate_secreted`/field deltas stay additive.
- **Init temperature 10–12** for clean cell shapes; seed one cell centered with room to grow 2 generations without crowding the grid.
- **Toy-real:** plausible constants, not fitted; honest framing conventions of `draft-to-living-cell`. Tests carry `pytest.importorskip("cpm")`, `("spatio_flux")`, `("cobra")`.

---

## File Structure

- Create: `meta_modelers_guide/cpm/growth_division.py` — `CpmGrowthDivision(Process)` (colony dFBA growth + native `divide_cells` + daughter bookkeeping).
- Create: `meta_modelers_guide/composites/growth-division-spatial.composite.json` — the composite.
- Modify: `meta_modelers_guide/cpm/viz.py` — add `run_growth_division_frames()` + lineage-colored frame rendering (reuse `frames_to_gif`/`metrics_panel`).
- Create: `tests/test_cpm_divide_spike.py` — native `divide_cells` in a real world (1→2, mass conserved, ids stable, phantom-daughter floor).
- Create: `tests/test_cpm_growth_division.py` — the process: grow → divide → daughters resume growth, no infinite re-division.
- Create: `tests/test_growth_division_regime.py` — the demonstrating metric (n_cells staircase 1→2→4, per-cell-volume sawtooth).
- Create: `tests/test_growth_division_viz.py` — GIF + metrics panel.
- Modify: `tests/test_composites_build.py` — add `CpmGrowthDivision` → `importorskip("cpm")` + `importorskip("cobra")` (this study uses dFBA).
- Create: `workspace/studies/growth-and-division-spatial/study.yaml` (+ `viz/`).
- Modify: `workspace/investigations/the-cellular-interface-multicellular/investigation.yaml` — add `growth-and-division-spatial` to `studies`.

Every new test guards optional frameworks so base CI skips cleanly:
```python
import pytest
pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")
pytest.importorskip("cobra")
```

---

## Task 1: Native `divide_cells` spike

**Goal:** prove in a REAL cpm world that `divide_cells(threshold, reset_target)` splits a grown cell 1→2 with mass conserved, the parent keeping its id and one new id appearing, ids stable across further steps — and that a too-small cell does not spawn a live phantom. (API map Q1 proved it in scratch; this locks it as a committed test.)

**Files:** Create `tests/test_cpm_divide_spike.py`.

- [ ] **Step 1: Write the failing test (RED)**

```python
# tests/test_cpm_divide_spike.py
"""Native CPM division: divide_cells splits a grown cell into two mass-conserved
daughters (parent keeps id, one new id), ids stable, no phantom from a tiny split."""
from __future__ import annotations
import numpy as np
import pytest

pytest.importorskip("cpm"); pytest.importorskip("spatio_flux")
from cpm.schema import load_world

NX = NY = 40

def _one_cell(target=150.0):
    return load_world({
        "potts": {"dims": [NX, NY, 1], "boundary": "noflux", "neighbor_order": 2,
                  "temperature": 11.0, "seed": 1},
        "cells": [{"type": 1, "target_volume": target, "lambda_volume": 2.0,
                   "target_surface": 0.0, "lambda_surface": 0.0,
                   "seed_block": [15, 15, 0, 25, 25, 1]}],
        "contact": [{"a": 0, "b": 1, "j": 14.0}, {"a": 1, "b": 1, "j": 14.0}],
    })

def test_divide_splits_one_into_two_mass_conserved():
    w = _one_cell(150.0)
    w.step(40)                                   # grow toward 150
    vol_before = w.cell_volumes()[1]
    new_ids = w.divide_cells(80.0, 40.0)         # threshold 80, daughters reset to 40
    assert len(new_ids) == 1                      # one new daughter id
    ids = sorted(set(int(x) for x in np.unique(w.snapshot())) - {0})
    assert ids == [1, new_ids[0]]                 # parent id 1 kept + the new id
    vols = w.cell_volumes()
    assert abs((vols[1] + vols[new_ids[0]]) - vol_before) <= 2   # mass conserved (±rounding)
    w.step(10)
    ids2 = sorted(set(int(x) for x in np.unique(w.snapshot())) - {0})
    assert ids2 == ids                            # ids stable across further steps

def test_below_threshold_is_noop():
    w = _one_cell(60.0)
    w.step(20)
    assert w.divide_cells(500.0, 40.0) == []      # nothing over threshold -> no split
```

- [ ] **Step 2: Run it** — `PYTHONPATH=$PWD ~/code/meta-modelers-guide/.venv/bin/python -m pytest tests/test_cpm_divide_spike.py -v`. If `divide_cells`'s return type or arg order differs, read `~/code/viva-cpm/crates/cpm-py/src/lib.rs` and the API map Q1 and correct. Expected: GREEN.
- [ ] **Step 3: Commit.**

---

## Task 2: `CpmGrowthDivision` process

**Goal:** the world-owning process: metabolism-driven growth per cell + native division at threshold + daughter bookkeeping that resumes growth without infinite re-division.

**Files:** Create `meta_modelers_guide/cpm/growth_division.py`; Create `tests/test_cpm_growth_division.py`.

**Interfaces:**
- Consumes (config): `grid {nx,ny}`; `cell {seed_block, target_volume, lambda_volume, temperature}`; `box_volume_L`, `grow_per_biomass`, `glucose_vmax`, `oxygen_vmax`, `mcs`; `vol_threshold`, `reset_target` (division); `contact` (include `{a:1,b:1,j:...}`).
- Consumes (ports): `inputs {fields: map[array]}` (needs `glucose`).
- Produces (ports): `outputs` = `fields: map[array]` (summed delta) + per-cell `volume/position/biomass/local_glucose` as `overwrite[map[float]]`/`overwrite[map[list]]`, and scalars `n_cells: overwrite[float]`, `total_volume: overwrite[float]`.

Read `meta_modelers_guide/cpm/colony_field.py` in full and REUSE its per-cell dFBA growth body (footprint read, MM-limited dFBA, mass-conservative writeback, `sol.status` guard, per-cell cobra copies, `set_target_volume(cid, grow_per_biomass*biomass[cid])`). Then add division:

- After `world.step(mcs)` each tick: `vols_before = list(self.world.cell_volumes())`; `new_ids = self.world.divide_cells(vol_threshold, reset_target)`; if `new_ids`: `vols_after = self.world.cell_volumes()`; for every live id that is in `new_ids` OR whose `vols_after[cid] < vols_before[cid]` (divided), set `self.biomass[cid] = reset_target / grow_per_biomass`. Initialize `self.biomass[new_id]` for any daughter not yet tracked. (This keeps each daughter's biomass-driven target at `reset_target`, so it grows again from there rather than snapping back over the threshold.)
- New per-cell cobra model: give each new daughter id its own `load_model("textbook")` copy with the same role bounds (mirror how colony builds `self._models`; add a lazily-created model for ids that appear at runtime).
- `n_cells` = number of live ids (excluding medium); `total_volume` = sum of live cell volumes.

- [ ] **Step 1: Write the failing test (RED)**

```python
# tests/test_cpm_growth_division.py
"""CpmGrowthDivision: a single CPM cell grows on the shared glucose field and divides
at threshold; daughters resume growth; the population increases without runaway."""
from __future__ import annotations
import numpy as np
import pytest
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

pytest.importorskip("cpm"); pytest.importorskip("spatio_flux"); pytest.importorskip("cobra")

NX = NY = 60

def _state(core):
    glucose = np.full((NY, NX), 12.0)                 # abundant, supports a few generations
    return {
        "fields": {"glucose": glucose, "acetate": np.zeros((NY, NX))},
        "cell": {"_type": "process", "address": "local:CpmGrowthDivision",
            "config": {"grid": {"nx": NX, "ny": NY},
                       "cell": {"seed_block": [27, 27, 0, 33, 33, 1], "target_volume": 40.0,
                                "lambda_volume": 2.0, "temperature": 11.0},
                       "box_volume_L": 0.3, "grow_per_biomass": 40.0,
                       "glucose_vmax": 10.0, "oxygen_vmax": 15.0, "mcs": 3,
                       "vol_threshold": 80.0, "reset_target": 40.0,
                       "contact": [{"a": 0, "b": 1, "j": 14.0}, {"a": 1, "b": 1, "j": 14.0}]},
            "inputs": {"fields": ["fields"]},
            "outputs": {"fields": ["fields"], "n_cells": ["obs", "n_cells"],
                        "total_volume": ["obs", "total_volume"], "volume": ["obs", "volume"]},
        },
    }

def test_cell_grows_and_divides_into_a_population():
    core = build_core()
    comp = Composite({"state": _state(core)}, core=core)
    n0 = comp.state["obs"]["n_cells"]
    comp.run(30)
    assert comp.state["obs"]["n_cells"] > n0            # population grew by division
    assert comp.state["obs"]["n_cells"] >= 3            # at least 1 -> 2 -> ~4
    vols = comp.state["obs"]["volume"]
    assert all(v < 200 for v in vols.values())          # no runaway single cell (division caps size)
    assert all(v > 5 for v in vols.values())            # no zero-volume phantom daughters
```

- [ ] **Step 2: Run → iterate to GREEN.** Watch for phantom daughters (floor `vol_threshold`), infinite re-division (biomass reset), and glucose depletion (raise the field or shorten to 2 generations). Tune the test's config minimally if needed and note changes. Expected: PASS.
- [ ] **Step 3: Commit.**

---

## Task 3: The growth-division composite

**Goal:** author `growth-division-spatial.composite.json` in the discovered `composites/` dir, wiring the glucose field + DiffusionAdvection + CpmGrowthDivision.

**Files:** Create `meta_modelers_guide/composites/growth-division-spatial.composite.json`; Modify `tests/test_composites_build.py`.

Mirror `single-cell-in-a-field.composite.json` structure. `state`: `fields` (`glucose` abundant — a high uniform level and/or a replenishing source so ≥2 generations are reached; `acetate` zeros), one `CpmGrowthDivision` (`local:CpmGrowthDivision`, cell seeded centered), `DiffusionAdvection` (full address, glucose diffusion), `RAMEmitter`. Grid 60×60 (room for 4+ cells).

- [ ] **Step 1:** author the JSON; verify it builds — `... -m pytest "tests/test_composites_build.py::test_composite_builds[growth-division-spatial]" -v`.
- [ ] **Step 2:** extend the build guard:
  ```python
  if "CpmGrowthDivision" in raw:
      pytest.importorskip("cpm")
      pytest.importorskip("cobra")   # dFBA-driven growth
  ```
- [ ] **Step 3:** run the parametrized build case + full `-m pytest -q` (no regressions). Expected: GREEN.
- [ ] **Step 4: Commit.**

---

## Task 4: Tune + assert the growth-and-division regime

**Goal:** the run must READ as Fig 10b: a cell grows, divides at threshold (n_cells steps 1→2→4), per-cell volume sawtooths (grow to threshold, halve on division, regrow), over a bounded run.

**Files:** Create `tests/test_growth_division_regime.py`.

- [ ] **Step 1: Write the failing test (RED)**

```python
# tests/test_growth_division_regime.py
"""The growth-and-division regime is legible: the population steps up (n_cells 1->2->4)
as cells grow past the volume threshold and divide, per-cell volume sawtoothing."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pytest
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

pytest.importorskip("cpm"); pytest.importorskip("spatio_flux"); pytest.importorskip("cobra")
COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"

def test_population_steps_up_by_division():
    core = build_core()
    state = json.loads((COMPOSITES / "growth-division-spatial.composite.json").read_text())["state"]
    comp = Composite({"state": state}, core=core)
    ns = []
    for _ in range(12):
        comp.run(3)
        ns.append(comp.state["obs"]["n_cells"])
    assert ns[0] <= 2                                   # starts as ~1 cell
    assert max(ns) >= 4                                 # reaches at least 2 generations (4 cells)
    assert ns == sorted(ns)                             # monotonic non-decreasing staircase
    vols = comp.state["obs"]["volume"]
    assert all(8 < v < 200 for v in vols.values())      # bounded cell sizes, no phantoms
```

- [ ] **Step 2: Run → TUNE** the composite: glucose level/replenishment (reach ≥2 generations), `vol_threshold`/`reset_target` (`vol_threshold ≈ 2·reset_target`), `grow_per_biomass` (slow enough to see the sawtooth), grid size (fit 4 cells). Record final constants + observed n_cells trajectory in the ledger.
- [ ] **Step 3: Commit** (composite + test together).

---

## Task 5: Growth-and-division visualization

**Goal:** a GIF of the lineage — one cell growing, dividing into two, then four — colored by cell id over the glucose field; plus a synced metrics panel.

**Files:** Modify `meta_modelers_guide/cpm/viz.py`; Create `tests/test_growth_division_viz.py`.

Add `run_growth_division_frames(state, core, steps, cadence) -> (frames, metrics)` mirroring `run_colony_frames`: reach the live world; color each cell id a distinct lineage color over the glucose heatmap. `metrics` holds `time`, `n_cells`, `total_volume`, and per-cell `volume` arrays (cells appear over time). Reuse `frames_to_gif`; extend `metrics_panel` to plot the `n_cells` staircase + total_volume (and, if practical, per-cell volume sawtooth) with `include_plotlyjs` kept. Do not break flagship/colony/disintegration viz paths (branch on metrics shape; confirm their viz tests still pass).

- [ ] **Step 1: RED** — `tests/test_growth_division_viz.py`: run enough steps for ≥2 divisions, assert ≥6 frames, `n_cells` array present and ends ≥ its start, GIF written non-empty, metrics HTML written with a Plotly div.
- [ ] **Step 2: Implement → GREEN.**
- [ ] **Step 3: Bake** `viz/growth-division-spatial.gif` + `viz/growth-division-metrics.html` into `workspace/studies/growth-and-division-spatial/viz/`. Commit code now; artifacts land with the study in Task 6.

---

## Task 6: Study + investigation + report

**Goal:** author the study, wire it into the investigation, bake the loom Model figure, render the report.

**Files:** Create `workspace/studies/growth-and-division-spatial/study.yaml` (+ `viz/`); Modify `workspace/investigations/the-cellular-interface-multicellular/investigation.yaml`.

Mirror `workspace/studies/cell-cell-coupling-spatial/study.yaml` (schema_version 4). Content:
- Name `growth-and-division-spatial`, investigation `the-cellular-interface-multicellular`, title "Growth and Division, Spatial".
- Question: does Fig 10a,b hold spatially — a CPM cell whose metabolism (dFBA at its footprint) grows its volume until it crosses a threshold and divides (native `divide_cells`, mass-conserved), compounding into a lineage — composed from independent frameworks through one coupling process?
- Measured outcomes from Task 4's tuned run: the n_cells staircase (1→2→4), per-cell-volume sawtooth, division threshold/reset, generations reached.
- Cite tests: `test_cpm_divide_spike`, `test_cpm_growth_division`, `test_growth_division_regime`, `test_growth_division_viz`.
- HONEST caveats: growth is metabolism-driven (real dFBA) but constants are toy-real not fitted; division is the native CPM `divide_cells` (a modeling operation triggered by the volume threshold, not emergent membrane mechanics); the run spans ~2 generations bounded by the shared glucose supply (note the field-depletion limit); per-cell cobra copies. Cross-link to the `draft-to-living-cell` analogue study `growth-and-division` (whose division is a place-graph rewrite — contrast the spatial native-CPM division here).
- Viz refs: `image:` → `viz/growth-division-spatial.gif`; `html:` → `viz/growth-division-metrics.html`.

- [ ] **Step 1:** author `study.yaml`; add `growth-and-division-spatial` to the investigation's `studies:`.
- [ ] **Step 2:** `python scripts/lint-workspace.py` → `workspace lint: OK` (only the pre-existing dash-in-name warning class).
- [ ] **Step 3:** bake the loom Model figure: `vivarium-workbench render-loom --study growth-and-division-spatial --max-width 1600 --colors 128`.
- [ ] **Step 4:** render the investigation report; confirm the study section shows the loom Model figure (not the schematic) + the GIF + interactive metrics. Do NOT commit any generated `reports/*.html` (gitignored).
- [ ] **Step 5:** run the FULL suite `-m pytest -q` (all green) + confirm the deps-absent CI condition still skips cleanly. Also `bash scripts/check-no-local-paths.sh` → OK.
- [ ] **Step 6: Commit** study + investigation + viz artifacts (GIF, metrics HTML, model-loom PNG).

---

## Self-Review notes

- **Spec coverage:** study 8 row (grow by metabolism → divide at threshold) → Tasks 2–4 + 6; native `divide_cells` retired first in Task 1. ✓
- **Risks addressed:** field depletion (abundant glucose/replenish, Task 3/4), phantom daughters (threshold floor + snapshot-derived live ids, Global Constraints + Task 2), infinite re-division (biomass reset on division, Task 2). ✓
- **cobra IS used** (dFBA growth): tests importorskip cpm+spatio_flux+cobra; build guard keys `CpmGrowthDivision` on cpm+cobra (Task 3). ✓
- **Type consistency:** per-cell observables id-keyed `map[...]` with `overwrite` on absolutes; `divide_cells(threshold, reset_target)` two-arg, parent-keeps-id + one-new-id semantics used identically in Task 1 test and Task 2 process. ✓
- **CI:** every new test carries the three importorskip guards; no local absolute home-dir paths in committed docs. ✓
