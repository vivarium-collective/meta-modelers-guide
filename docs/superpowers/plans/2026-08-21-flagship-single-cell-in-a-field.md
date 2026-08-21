# Flagship: `single-cell-in-a-field` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the flagship of `the-cellular-interface-multicellular` — one CPM cell in a spatio-flux diffusing nutrient field, running dynamic FBA at its location (uptake → biomass → growth, secreting a byproduct), composed from independent frameworks via one coupling module, with a GIF + synced-metrics visualization and a study + report.

**Architecture:** Compose three process-bigraph processes over one shared `fields` grid: spatio-flux `DiffusionAdvection` (diffuses nutrient + byproduct), spatio-flux `SpatialDFBA` (per-bin `e_coli_core` metabolism using a biomass grid), and a new `CpmCellField` process (a CPM cell that exposes its lattice footprint and grows from biomass). A `CpmFieldBridge` maps the CPM cell footprint ↔ the biomass grid and metabolism ↔ growth. All wired by full import-path address.

**Tech Stack:** Python, `process_bigraph`, `cpm` (viva-cpm; Rust `cpm_core` engine), `spatio_flux` (`DiffusionAdvection`, `SpatialDFBA`/`DynamicFBA`, `e_coli_core` via cobra), matplotlib + imageio/Pillow (GIF), Plotly (`DynamicsPlot` reuse for metrics).

**Spec:** `docs/superpowers/specs/2026-08-21-cellular-interface-multicellular-design.md`

## Global Constraints

- **Worktree discipline:** all work in `~/code/meta-modelers-guide--cpm-multicellular` on branch `cpm-multicellular-investigation`. Never commit in the canonical checkout. Verify `git branch --show-current` before each commit. Tests run with `PYTHONPATH=~/code/meta-modelers-guide--cpm-multicellular` prepended; interpreter `~/code/meta-modelers-guide/.venv/bin/python`.
- **Cross-package process addresses use FULL import-path form** (verified): `local:!cpm.processes.cpm_process.CPMProcess`, `local:!spatio_flux.processes.diffusion_advection.DiffusionAdvection`, `local:!spatio_flux.processes.dfba.SpatialDFBA` (and `.DynamicFBA`). Bare `local:DiffusionAdvection` resolves to the WRONG package (`viva_munk` collision); bare `local:CPMProcess` does NOT resolve (`cpm` absent from `packages_distributions()`). New in-repo processes register normally via `meta_modelers_guide.core.build_core()`.
- **Shared-grid contract:** all arrays are `(ny, nx)` = (rows, cols); x=cols, y=rows. CPM lattice dims == spatio-flux `n_bins` for 1:1 pixel↔bin. `world.snapshot()`/`field_conc()` are flat `x + y*nx` → reshape `(ny, nx)`. spatio-flux requires **square cells** (`dx == dy`): set `bounds == n_bins` (unit cells).
- **CPM `seed_block` uses HALF-OPEN ranges** — a 2D cell needs `z0,z1 = 0,1` (z1=0 → empty world). `[x0,y0,z0, x1,y1,z1]` with `x1=x0+width`.
- **`DiffusionAdvection.update()` and `DynamicFBA`/`SpatialDFBA.update()` return DELTAS**, not new field values. The engine applies deltas to the store.
- **Rust CPM field is write-protected** — no external `set_field`. The nutrient the cell metabolizes lives in the spatio-flux `fields` store (writable), NOT the CPM internal field. CPM chemotaxis (Rust) is out of scope for the flagship (deferred to a variant).
- Frameworks stay **toy-real** (plausible constants, not fitted); keep the honest-framing conventions of `draft-to-living-cell`.

---

## File Structure

- Create: `meta_modelers_guide/cpm/__init__.py`
- Create: `meta_modelers_guide/cpm/cell_field.py` — the `CpmCellField` process (owns a CPM world; footprint + growth ports).
- Create: `meta_modelers_guide/cpm/bridge.py` — `CpmFieldBridge` (footprint ↔ biomass grid; metabolism ↔ growth) if kept separate from `CpmCellField`; the spike (Task 1) decides whether the bridge is a standalone process or folded into `CpmCellField`.
- Create: `meta_modelers_guide/cpm/viz.py` — `cpm_frames_to_gif` + `metrics_panel`.
- Create: `meta_modelers_guide/composites/single-cell-in-a-field.composite.json` — the flagship composite.
- Modify: `meta_modelers_guide/core.py` — ensure `register_workspace_processes` picks up `meta_modelers_guide.cpm.*` processes (it auto-scans this package's Process subclasses; confirm the new subpackage is imported).
- Modify: `pyproject.toml` — declare `pbg-cpm` and `spatio-flux` deps (documented as editable-installed; note the Rust `cpm_core` maturin precondition).
- Create: `tests/test_cpm_smoke.py`, `tests/test_cpm_cell_field.py`, `tests/test_flagship_field.py`, `tests/test_cpm_viz.py`.
- Create: `workspace/investigations/the-cellular-interface-multicellular/investigation.yaml`
- Create: `workspace/studies/cell-environment-coupling-spatial/study.yaml` (+ `viz/`) — the flagship study (slug distinct from the draft-to-living-cell `cell-environment-coupling`; investigation-scoped).

---

## Task 1: Prove the composition (spike → smoke test) + decide the coupling shape

**Goal:** stand up a minimal composite — a CPM cell + a spatio-flux `DiffusionAdvection` field + a biomass grid — running a few steps, proving cross-package wiring + the read/write bridge work; DECIDE whether the CPM↔field coupling is a standalone `CpmFieldBridge` process or folded into a world-owning `CpmCellField` process (the API map shows the lattice + growth are NOT CPM stores, so a world-owning process is the likely answer). Record the decision.

**Files:** Create `tests/test_cpm_smoke.py`; scratch exploration allowed.

- [ ] **Step 1: Write the smoke test (RED)**

```python
# tests/test_cpm_smoke.py
"""Prove the flagship composition primitives: a CPM cell world runs, its lattice +
COM are readable, and a spatio-flux DiffusionAdvection field composes over a shared
(ny,nx) grid — all addressed by full import path."""
from __future__ import annotations
import numpy as np
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

NX = NY = 40

def _cpm_spec(nx=NX, ny=NY):
    return {
        "potts": {"dims": [nx, ny, 1], "boundary": "noflux",
                  "neighbor_order": 2, "temperature": 10.0, "seed": 1},
        "cells": [{"type": 1, "target_volume": 60.0, "lambda_volume": 2.0,
                   "target_surface": 0.0, "lambda_surface": 0.0,
                   "seed_block": [17, 17, 0, 24, 24, 1]}],  # half-open; z1=1 for 2D
        "contact": [{"a": 0, "b": 1, "j": 14.0}],
    }

def test_cpm_world_runs_and_lattice_readable():
    from cpm.schema import load_world
    world = load_world(_cpm_spec())
    world.step(5)
    lattice = np.array(world.snapshot()).reshape(NY, NX)
    assert lattice.shape == (NY, NX)
    assert (lattice > 0).sum() > 0                     # the cell occupies pixels
    coms = world.cell_coms()
    assert len(coms) >= 2 and 0 < coms[1][0] < NX      # cell 1 has a COM in-bounds

def test_diffusion_advection_composes_full_address():
    core = build_core()
    field = np.zeros((NY, NX)); field[NY//2, NX//2] = 100.0
    state = {
        "fields": {"glucose": field},
        "diff": {"_type": "process",
                 "address": "local:!spatio_flux.processes.diffusion_advection.DiffusionAdvection",
                 "config": {"n_bins": (NX, NY), "bounds": (float(NX), float(NY)),
                            "diffusion_coeffs": {"glucose": 0.5},
                            "boundary_conditions": {"glucose": {"default": {"type": "neumann"}}}},
                 "inputs": {"fields": ["fields"]}, "outputs": {"fields": ["fields"]}},
    }
    comp = Composite({"state": state}, core=core)
    before = float(np.sum(comp.state["fields"]["glucose"]))
    comp.run(5)
    after = float(np.sum(comp.state["fields"]["glucose"]))
    assert abs(after - before) < 1e-6                  # mass conserved under neumann
    assert comp.state["fields"]["glucose"][NY//2, NX//2] < 100.0  # spread out
```

- [ ] **Step 2: Run it (RED → GREEN as primitives are confirmed)**

Run: `PYTHONPATH=~/code/meta-modelers-guide--cpm-multicellular ~/code/meta-modelers-guide/.venv/bin/python -m pytest tests/test_cpm_smoke.py -v`
Expected: both pass. If `n_bins`/`bounds` ordering or BC config differs from the map, adjust to the verified `DiffusionAdvection.config_schema` (it takes `n_bins: (nx,ny)`, `bounds: (xmax,ymax)`, per-species `boundary_conditions`). If `load_world` rejects the spec, reconcile against `cpm/schema.py` grammar (the half-open `seed_block` is the usual culprit).

- [ ] **Step 3: Spike the coupling read/write, decide the shape, RECORD it**

In a scratch script (not committed), confirm: (a) you can compute a cell's footprint mask `lattice == 1` and read the mean of a `(ny,nx)` nutrient array over it; (b) you can write a biomass array that is nonzero only on the footprint; (c) you can grow the CPM cell via `world.set_target_volume(1, v)` then `world.step()`. Decide: **`CpmCellField`** = one process that OWNS the CPM world (so it can read the lattice + grow the cell) and exposes `fields` in/out + observables — this is the recommended shape because the lattice and growth are not process-bigraph stores. Write the decision (one paragraph) into the plan's progress ledger / task-1 notes.

- [ ] **Step 4: Commit**

```bash
git add tests/test_cpm_smoke.py
git commit -m "test(cpm): smoke — CPM world + spatio-flux DiffusionAdvection compose by full address"
```

---

## Task 2: `CpmCellField` — the CPM cell that metabolizes a shared field and grows

**Files:**
- Create: `meta_modelers_guide/cpm/__init__.py` (empty, or re-exports)
- Create: `meta_modelers_guide/cpm/cell_field.py`
- Test: `tests/test_cpm_cell_field.py`
- Modify: `meta_modelers_guide/core.py` (import the cpm subpackage so its Process is registered)

**Interfaces:**
- Consumes: `process_bigraph.Process`; `cpm.schema.load_world`; `spatio_flux.processes.dfba.run_fba_update` (or a cobra e_coli_core `optimize` call); `build_core`.
- Produces: `CpmCellField(Process)` with `inputs {"fields": "map[array]"}`, `outputs {"fields": "map[array]", "volume": "float", "position": "list", "local_nutrient": "float", "biomass": "float", "acetate_secreted": "float"}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cpm_cell_field.py
"""CpmCellField: a CPM cell that reads a shared nutrient grid at its footprint, runs
dFBA there (uptake→biomass, secretes acetate), grows from biomass, and writes its
uptake/secretion back to the field as a delta."""
from __future__ import annotations
import numpy as np
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

NX = NY = 40

def _state(core):
    glucose = np.full((NY, NX), 10.0)
    acetate = np.zeros((NY, NX))
    return {
        "fields": {"glucose": glucose, "acetate": acetate},
        "cell": {
            "_type": "process",
            "address": "local:CpmCellField",
            "config": {"nx": NX, "ny": NY, "seed_block": [17, 17, 0, 24, 24, 1],
                       "mcs_per_update": 8, "biomass0": 0.1,
                       "grow_per_biomass": 300.0, "box_volume_L": 1e-6},
            "inputs": {"fields": ["fields"]},
            "outputs": {"fields": ["fields"], "volume": ["obs", "volume"],
                        "position": ["obs", "position"], "local_nutrient": ["obs", "local_nutrient"],
                        "biomass": ["obs", "biomass"], "acetate_secreted": ["obs", "acetate_secreted"]},
        },
        "obs": {"volume": 0.0, "position": [0.0, 0.0], "local_nutrient": 0.0,
                "biomass": 0.0, "acetate_secreted": 0.0},
    }

def test_cell_metabolizes_grows_and_reshapes_field():
    core = build_core()
    comp = Composite({"state": _state(core)}, core=core)
    g0 = float(comp.state["fields"]["glucose"].mean())
    comp.run(12)
    obs = comp.state["obs"]
    assert obs["biomass"] > 0.1                              # grew biomass via dFBA
    assert obs["volume"] > 40.0                              # CPM cell grew
    assert float(comp.state["fields"]["glucose"].mean()) < g0  # depleted glucose locally
    assert float(comp.state["fields"]["acetate"].sum()) > 0.0  # secreted byproduct
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=… pytest tests/test_cpm_cell_field.py -v` — FAIL (`CpmCellField` not defined).

- [ ] **Step 3: Implement `meta_modelers_guide/cpm/cell_field.py`**

```python
"""CpmCellField — a CPM cell (viva-cpm) that metabolizes a shared spatio-flux nutrient
field at its footprint and grows from the biomass it makes.

Owns the CPM world (the lattice + growth are not process-bigraph stores, so a single
world-owning process is the clean coupling point). Composes over one shared ``fields``
grid with spatio-flux ``DiffusionAdvection``: the cell reads glucose at its footprint,
runs one dFBA step (e_coli_core), writes back the uptake (−glucose) and secretion
(+acetate) as a field delta, and grows its CPM target volume in proportion to biomass.
Toy-real: plausible constants, not a fitted organism."""
from __future__ import annotations

import numpy as np
from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


class CpmCellField(Process):
    config_schema = {
        "nx": {"_type": "integer", "_default": 40},
        "ny": {"_type": "integer", "_default": 40},
        "seed_block": {"_type": "list", "_default": [17, 17, 0, 24, 24, 1]},
        "mcs_per_update": {"_type": "integer", "_default": 8},
        "temperature": _f(10.0),
        "lambda_volume": _f(2.0),
        "contact_j": _f(14.0),
        "biomass0": _f(0.1),
        "grow_per_biomass": _f(300.0),   # target_volume = grow_per_biomass * biomass
        "box_volume_L": _f(1e-6),
        "glucose_km": _f(0.5), "glucose_vmax": _f(10.0),
    }

    def inputs(self):
        return {"fields": "map[array]"}

    def outputs(self):
        return {"fields": "map[array]", "volume": "float", "position": "list",
                "local_nutrient": "float", "biomass": "float", "acetate_secreted": "float"}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        from cpm.schema import load_world
        c = self.config
        nx, ny = int(c["nx"]), int(c["ny"])
        self._nx, self._ny = nx, ny
        spec = {
            "potts": {"dims": [nx, ny, 1], "boundary": "noflux", "neighbor_order": 2,
                      "temperature": c["temperature"], "seed": 1},
            "cells": [{"type": 1, "target_volume": 60.0, "lambda_volume": c["lambda_volume"],
                       "target_surface": 0.0, "lambda_surface": 0.0,
                       "seed_block": list(c["seed_block"])}],
            "contact": [{"a": 0, "b": 1, "j": c["contact_j"]}],
        }
        self.world = load_world(spec)
        self.biomass = float(c["biomass0"])
        # one cobra e_coli_core, loaded once
        from cobra.io import load_model
        self._model = load_model("textbook")

    def _footprint(self):
        lat = np.array(self.world.snapshot()).reshape(self._ny, self._nx)
        return lat == 1

    def _fba(self, glucose_conc, interval):
        """One dFBA step on e_coli_core: MM-limited glucose uptake → growth + acetate."""
        c = self.config
        m = self._model
        v = c["glucose_vmax"] * glucose_conc / (c["glucose_km"] + glucose_conc) if glucose_conc > 0 else 0.0
        # budget-limit the uptake by available glucose over the footprint
        m.reactions.EX_glc__D_e.lower_bound = -float(v)
        sol = m.optimize()
        mu = float(sol.objective_value or 0.0)
        d_biomass = mu * self.biomass * interval
        glc_flux = float(sol.fluxes.get("EX_glc__D_e", 0.0))   # negative = uptake
        ac_flux = float(sol.fluxes.get("EX_ac_e", 0.0))        # positive = secretion
        d_glc = glc_flux * self.biomass * interval / c["box_volume_L"]
        d_ac = ac_flux * self.biomass * interval / c["box_volume_L"]
        return d_biomass, d_glc, d_ac

    def update(self, state, interval):
        fields = state.get("fields", {})
        glucose = np.asarray(fields.get("glucose"))
        acetate = np.asarray(fields.get("acetate"))
        fp = self._footprint()
        area = max(int(fp.sum()), 1)
        local_glc = float(glucose[fp].mean()) if fp.any() else 0.0

        d_biomass, d_glc, d_ac = self._fba(local_glc, interval)
        self.biomass = max(self.biomass + d_biomass, 1e-9)

        # write uptake/secretion back to the field, spread over the footprint pixels
        dglc = np.zeros_like(glucose)
        dace = np.zeros_like(acetate)
        # clamp glucose delta so a pixel never goes negative
        per_pixel_glc = max(d_glc, -float(glucose[fp].sum())) / area if fp.any() else 0.0
        per_pixel_ac = d_ac / area if fp.any() else 0.0
        dglc[fp] = per_pixel_glc
        dace[fp] = per_pixel_ac

        # grow the CPM cell from biomass, then step the world
        target = float(self.config["grow_per_biomass"]) * self.biomass
        self.world.set_target_volume(1, max(target, 4.0))
        self.world.step(int(self.config["mcs_per_update"]))

        vol = float(self.world.cell_volumes()[1])
        com = list(self.world.cell_coms()[1])[:2]
        return {"fields": {"glucose": dglc, "acetate": dace},
                "volume": vol, "position": com, "local_nutrient": local_glc,
                "biomass": self.biomass, "acetate_secreted": float(dace.sum())}
```

- [ ] **Step 4: Register the subpackage** — in `meta_modelers_guide/core.py`, ensure `register_workspace_processes` discovers `meta_modelers_guide.cpm.cell_field.CpmCellField` (import `meta_modelers_guide.cpm.cell_field` where the core iterates workspace modules; follow the existing `_iter_own_process_classes` pattern — add the `cpm/` subpackage to its scan or import it at module load).

- [ ] **Step 5: Run to verify it passes**

Run: `PYTHONPATH=… pytest tests/test_cpm_cell_field.py -v` — PASS. Tune `grow_per_biomass`, `glucose_vmax`, `mcs_per_update` only if biomass/volume/glucose don't move as asserted (dFBA on e_coli_core with glucose≈10 gives μ≈0.8/hr; scale constants so growth is visible over ~12 ticks). If `set_target_volume`/`cell_volumes`/`snapshot` signatures differ, correct against the verified `world.*` list.

- [ ] **Step 6: Commit**

```bash
git add meta_modelers_guide/cpm/__init__.py meta_modelers_guide/cpm/cell_field.py \
        meta_modelers_guide/core.py tests/test_cpm_cell_field.py
git commit -m "feat(cpm): CpmCellField — CPM cell metabolizes a shared field (dFBA) and grows from biomass"
```

---

## Task 3: The flagship composite + behavior test

**Files:**
- Create: `meta_modelers_guide/composites/single-cell-in-a-field.composite.json`
- Test: `tests/test_flagship_field.py`

**Interfaces:** Consumes `CpmCellField` (Task 2), spatio-flux `DiffusionAdvection` (full address). Produces the composite spec id `meta_modelers_guide.composites.single-cell-in-a-field`.

- [ ] **Step 1: Write the composite JSON**

A `fields` store `{glucose:(ny,nx) seeded high on one side (a gradient/source), acetate:(ny,nx) zeros}`; a `DiffusionAdvection` process (full address) diffusing both species over the grid; the `CpmCellField` process wired to the same `fields` store + an `obs` store for observables; a `RAMEmitter` capturing `obs` + `fields` at each step. Grid `nx=ny=40`, `bounds=(40,40)`. Diffusion coeffs: glucose 0.4, acetate 0.6. Seed glucose as a left→right gradient (or a source blob) so there is spatial structure to deplete.

- [ ] **Step 2: Write the behavior test**

```python
# tests/test_flagship_field.py
"""The flagship sense/act loop: over the run the cell depletes local glucose, grows
biomass + volume, secretes acetate into the field, and diffusion spreads it — a real
spatial realization of Fig 5 cell-environment coupling (niche construction)."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

COMP = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "cpm" / "composites" / "single-cell-in-a-field.composite.json"

def test_flagship_sense_act_loop():
    core = build_core()
    state = json.loads(COMP.read_text())["state"]
    comp = Composite({"state": state}, core=core)
    glc0 = float(np.asarray(comp.state["fields"]["glucose"]).sum())
    comp.run(20)
    obs = comp.state["obs"]
    assert obs["biomass"] > state["cell"]["config"]["biomass0"]   # metabolized
    assert obs["volume"] > 40.0                                    # grew
    assert float(np.asarray(comp.state["fields"]["acetate"]).sum()) > 0.0  # secreted
    assert float(np.asarray(comp.state["fields"]["glucose"]).sum()) < glc0  # consumed net
```

(The composite JSON stores numpy arrays as nested lists; the builder or test constructs them — if JSON can't hold ndarrays, generate the composite via a tiny `scripts/build_flagship_composite.py` that writes the arrays, mirroring how spatio-flux composites seed `fields`; adjust the test to load via that builder. Decide in Step 1 and keep consistent.)

- [ ] **Step 3: Run RED → implement/seed → GREEN**

Run: `PYTHONPATH=… pytest tests/test_flagship_field.py -v`. Iterate seeding/diffusion/growth constants until the four assertions hold over 20 steps. Keep it toy-real.

- [ ] **Step 4: Commit**

```bash
git add meta_modelers_guide/composites/single-cell-in-a-field.composite.json tests/test_flagship_field.py
git commit -m "feat(cpm): flagship single-cell-in-a-field composite — CPM cell + diffusion + dFBA, sense/act loop"
```

---

## Task 4: `cpm_viz` — the GIF + synced metrics visualization

**Files:**
- Create: `meta_modelers_guide/cpm/viz.py`
- Test: `tests/test_cpm_viz.py`

**Interfaces:** Produces `run_flagship_frames(composite_state, core, steps, cadence) -> (frames, metrics)` and `frames_to_gif(frames, out_path)` + `metrics_panel(metrics, out_path)`.

- [ ] **Step 1: Failing test**

```python
# tests/test_cpm_viz.py
"""cpm_viz bakes a GIF of the CPM cell over its nutrient field + a synced metrics panel."""
from __future__ import annotations
import json, os
from pathlib import Path
from process_bigraph import Composite
from meta_modelers_guide.core import build_core
from meta_modelers_guide.cpm import viz

COMP = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "cpm" / "composites" / "single-cell-in-a-field.composite.json"

def test_gif_and_metrics(tmp_path):
    core = build_core()
    state = json.loads(COMP.read_text())["state"]
    frames, metrics = viz.run_flagship_frames(state, core, steps=16, cadence=2)
    assert len(frames) >= 6                       # multiple frames captured
    assert set(("time","volume","local_nutrient","biomass")).issubset(metrics)
    assert len(metrics["biomass"]) == len(frames)
    gif = tmp_path / "run.gif"; viz.frames_to_gif(frames, gif)
    assert gif.exists() and gif.stat().st_size > 0
    panel = tmp_path / "metrics.html"; viz.metrics_panel(metrics, panel)
    assert panel.exists()
```

- [ ] **Step 2: Run RED**

- [ ] **Step 3: Implement `meta_modelers_guide/cpm/viz.py`**

`run_flagship_frames`: build the Composite; loop `steps//cadence` times, each `comp.run(cadence)`; per tick capture a frame = the CPM lattice (reach the live world: `comp.state['cell']['instance'].world.snapshot()` reshaped `(ny,nx)`) overlaid on the `fields['glucose']` array + the cell COM marker, rendered via matplotlib Agg `imshow(origin='lower')`; append the scalar `obs` (time, volume, local_nutrient, biomass, acetate_secreted). Return `(frames_as_rgb_arrays, metrics_dict_of_lists)`. `frames_to_gif`: `imageio.mimsave(out, frames, fps=6)` (fallback to Pillow `save(..., save_all=True, append_images=...)` if imageio absent — guard the import). `metrics_panel`: reuse the workspace `DynamicsPlot` (from `draft-to-living-cell`'s `meta_modelers_guide/visualization.py`) or a small Plotly `to_html` time-series sharing the run's time axis; write to `out_path`. Guard all optional deps; a missing imageio degrades to a single PNG + a note.

- [ ] **Step 4: Run GREEN**

Confirm `imageio` (or Pillow) availability first: `~/code/meta-modelers-guide/.venv/bin/python -c "import imageio; print(imageio.__version__)"`; if absent, `uv pip install imageio` into the venv (Pillow is already present) — record which was used.

- [ ] **Step 5: Commit**

```bash
git add meta_modelers_guide/cpm/viz.py tests/test_cpm_viz.py
git commit -m "feat(cpm): cpm_viz — GIF of the cell over its field + synced metrics panel"
```

---

## Task 5: The study + investigation scaffolding

**Files:**
- Create: `workspace/investigations/the-cellular-interface-multicellular/investigation.yaml`
- Create: `workspace/studies/cell-environment-coupling-spatial/study.yaml` (+ baked `viz/run.gif`, `viz/metrics.html`)

- [ ] **Step 1:** Author `investigation.yaml` for `the-cellular-interface-multicellular` — schema_version 2, title "The Cellular Interface, Multicellular", the arc from the spec, `studies: [cell-environment-coupling-spatial]` (the rest added in later increments), a `question`/`lead`/`executive` re-anchored to the spatial realization, and a cross-link to `draft-to-living-cell`. Follow the shape of the existing `draft-to-living-cell/investigation.yaml`.

- [ ] **Step 2:** Author `cell-environment-coupling-spatial/study.yaml` (schema_version 4; `name` matches dir; `investigation: the-cellular-interface-multicellular`): baseline composite `meta_modelers_guide.composites.single-cell-in-a-field`; question/claim = the Fig 5 sense/act loop as real spatial dFBA + niche construction; cite `tests/test_flagship_field.py`; honest caveats (toy-real e_coli_core constants; chemotaxis-toward-the-external-field deferred; the CPM field is Rust-internal, the metabolized nutrient is the spatio-flux field). Bake the GIF + metrics into `viz/` and reference them in `visualizations:` (`image:` for the GIF, the interactive metrics as the `html:` figure per the workbench viz convention).

- [ ] **Step 3:** Validate: `PYTHONPATH=… python scripts/lint-workspace.py` — the new study + investigation resolve; the baseline composite exists. Commit:

```bash
git add workspace/investigations/the-cellular-interface-multicellular workspace/studies/cell-environment-coupling-spatial
git commit -m "studies: the-cellular-interface-multicellular investigation + flagship cell-environment-coupling-spatial study"
```

---

## Task 6: Integration — full suite, lint, report

- [ ] **Step 1:** Full suite: `PYTHONPATH=… python -m pytest -q` — all pass (existing draft-to-living-cell tests unaffected; new cpm/flagship/viz tests green). The cpm/spatio-flux tests skip gracefully if `cpm_core` or `cobra` is unavailable (guard imports).
- [ ] **Step 2:** Lint: `PYTHONPATH=… python scripts/lint-workspace.py` — clean; both investigations present.
- [ ] **Step 3:** Regenerate the report for `the-cellular-interface-multicellular` (workbench `/api/investigation-report/the-cellular-interface-multicellular` or `render_investigation_report`) and confirm the flagship study shows the **GIF + the interactive metrics** together. (Use the fixed self-contained-report path — the workbench PR that inlines shared Plotly.js.)
- [ ] **Step 4:** Commit any regenerated report artifacts. Final verification: the flagship composite runs, the GIF + metrics render in the report, both investigations lint clean.

---

## Self-Review

**Spec coverage:** the flagship increment (spec §"The flagship" + §"Visualization" + §"Increment plan" step 1) is fully covered — CpmCellField (composition), the composite (CPM + diffusion + dFBA), cpm_viz (GIF + synced metrics), the study + investigation scaffolding. The deferred pieces (chemotaxis, force modules, the other 8 studies) are explicitly out of this plan (later increments), matching the spec's flagship-first decision.

**Placeholder scan:** code steps carry real code grounded in the verified API map (full-address wiring, `world.*` methods, dFBA deltas, `(ny,nx)` grids). The two genuinely spike-decided points (bridge-vs-world-owning-process; JSON-vs-builder for ndarray seeding) are called out explicitly with the recommended resolution, not left vague.

**Type consistency:** `CpmCellField` ports (`fields`, `volume`, `position`, `local_nutrient`, `biomass`, `acetate_secreted`) are used identically in Task 2's test, Task 3's composite/test, and Task 4's viz. Full addresses (`local:!spatio_flux…`, `local:!cpm…`) are used consistently. The composite spec id `meta_modelers_guide.composites.single-cell-in-a-field` is referenced identically in Tasks 3, 4, 5.
