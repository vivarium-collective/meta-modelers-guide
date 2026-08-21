# Study 4: `disintegration` (spatial) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build study 4 of `the-cellular-interface-multicellular` — a coherent CPM cell that holds while a stressor field is low, then **disintegrates into scattering physical particles** when the stressor crosses its viability bound (paper Fig 6, "level shift"). A new CPM→particle bridge sheds the resorbing cell's vacated pixels as debris that spatio-flux `BrownianMovement` scatters — watchable in the loom viewer / a GIF — with a synced metrics panel and a study + report.

**Architecture:** ONE CPM-world-owning process `CpmDisintegration` (modeled on the merged `CpmCellField`, **minus cobra**) reads a shared spatio-flux stressor field at the cell footprint each tick; once `mean(stressor[footprint]) >= viability_threshold` it **latches** a `released` flag and ramps `set_target_volume(cid) → 0` (resorption — the only reliable runtime lever; see API map). Each tick after release it diffs the vacated footprint pixels and emits (capped) new particles into a shared `particles: map[particle]` store via the map `_add` sentinel; a second process, stock `BrownianMovement`, scatters them. Composed over shared `fields` + `particles` stores by full import-path address.

**Tech Stack:** Python, `process_bigraph`, `cpm` (viva-cpm; Rust `cpm_core`), `spatio_flux` (`DiffusionAdvection`, `particles.BrownianMovement`), `scipy.ndimage` (connected-component metrics), matplotlib + imageio/Pillow (GIF), Plotly (metrics). **No cobra** (this study is about the viability level-shift, not metabolism).

**Spec:** `docs/superpowers/specs/2026-08-21-cellular-interface-multicellular-design.md` (study 4 row: "a CPM cell whose structural-integrity constraint releases when a stressor field crosses its viability bound → coherent cell domain dissolves into dispersed pixels/particles"). User chose the **particles** realization.
**API map:** `docs/superpowers/api-maps/2026-08-21-disintegration-api-map.md` — §1–4 (CPM/stressor/resorption) and §5 (particle bridge). Every API claim below is verified there with a run snippet.

## Global Constraints

- **Worktree discipline:** all work in `~/code/meta-modelers-guide--cpm-multicellular` on branch `study4-disintegration`. Never commit in the canonical checkout. Verify `git branch --show-current` before each commit. Tests run with `PYTHONPATH=~/code/meta-modelers-guide--cpm-multicellular` prepended; interpreter `~/code/meta-modelers-guide/.venv/bin/python`.
- **NO cobra in this study.** New tests carry `pytest.importorskip("cpm")` and `pytest.importorskip("spatio_flux")` — NOT cobra. `CpmDisintegration.__init__` must not import cobra.
- **The disintegration trigger is RESORPTION, not shatter.** Connectivity (E1) is a verified no-op in this cpm build; `lambda_volume`/`temperature` are init-only (no runtime setters). The ONLY runtime levers are `set_target_volume` and `set_contact`. Trigger = `mean(stressor[fp]) >= threshold → ramp set_target_volume(cid)→0`. The *drama* comes from converting the shed pixels to scattering particles, not from lattice fragmentation.
- **Particle emit contract** (verified §5.3): output port `particles: 'map[particle]'`; emit `{'particles': {'_add': {new_id: {'id': new_id, 'position': (x, y), 'mass': 1.0}}}}`. Ids from a **monotonic counter** on the instance (`self._pid`), never random/uuid/time. **Only include the `_add` key on ticks that actually shed pixels** — an empty `_add: {}` forces a full structural realize every tick. Emit `mass` ONCE in the `_add` payload (mass is an accumulator); never re-emit it.
- **Coordinate mapping** (verified §5.4, no axis flip): shed pixel `lat[row=j, col=i]` → `x=(i+0.5)*bounds_x/nx, y=(j+0.5)*bounds_y/ny`. **Particle/BrownianMovement `bounds` and `n_bins` MUST equal the field's `bounds`/`n_bins` and the CPM `(nx,ny)`; square cells** — do not leave `bounds` at the spatio-flux `_constants` default (50,50).
- **Latch `released`.** After resorption the footprint empties and `mean(stressor[fp])` reads 0.0 — never recompute the trigger from an empty footprint; once true, stays true. Re-derive live ids from `np.unique(snapshot())`; guard `area = max(fp.sum(), 1)`.
- **Init temperature 10–12** for a clean coherent baseline (temperature ≥25 self-fragments even a cohesive cell; it's init-only so cannot be lowered later).
- **Full import-path process addresses:** `local:!spatio_flux.processes.diffusion_advection.DiffusionAdvection`, and for the mover `local:!spatio_flux.processes.particles.BrownianMovement` (verify at build; fall back to bare `local:BrownianMovement` only if the full address fails to resolve). In-repo `CpmDisintegration` registers via `build_core()` (auto-scan, `core.register_link`), addressed `local:CpmDisintegration`.
- **Shared-grid contract:** all arrays `(ny,nx)`=(rows,cols); x=cols, y=rows; `snapshot()` flat `x+y*nx` → reshape `(ny,nx)`; `DiffusionAdvection.update()` returns DELTAS.
- **`overwrite[...]` on absolute observables:** `volume`, `area`, `position`, `mean_stressor`, `n_components`, `largest_fragment_fraction`, `released`, `released_tick` are per-tick absolute readings → `overwrite[...]`. `particles` is a `map[particle]` (`_add`-merged), not overwrite.
- **Toy-real:** plausible constants, not fitted; keep the honest-framing conventions of `draft-to-living-cell`. Honest caveats REQUIRED (resorption+particle-emit mechanism, connectivity E1 no-op, BrownianMovement not pymunk).

---

## File Structure

- Create: `meta_modelers_guide/cpm/disintegration.py` — `CpmDisintegration(Process)` (owns one CPM world; stressor read, resorption trigger, particle emission).
- Create: `meta_modelers_guide/composites/disintegration-spatial.composite.json` — the composite (CPM cell + stressor field + BrownianMovement over shared `particles`).
- Modify: `meta_modelers_guide/cpm/viz.py` — add `run_disintegration_frames()` + particle-overlay frame rendering (reuse `frames_to_gif`/`metrics_panel`).
- Create: `tests/test_particle_bridge_spike.py` — emit-via-`_add` + BrownianMovement scatter in a real Composite (retires the §5.6 "not-yet-in-one-composite" gap).
- Create: `tests/test_cpm_disintegration.py` — the process: coherent-then-resorb + particle emission.
- Create: `tests/test_disintegration_regime.py` — the demonstrating metrics (held → released → dissolved + debris scatter).
- Create: `tests/test_disintegration_viz.py` — GIF + metrics panel.
- Modify: `tests/test_composites_build.py` — extend the process-name guard to also `importorskip("cpm")` for `CpmDisintegration` (this composite needs cpm + spatio_flux, NOT cobra).
- Create: `workspace/studies/disintegration-spatial/study.yaml` (+ `viz/`).
- Modify: `workspace/investigations/the-cellular-interface-multicellular/investigation.yaml` — add `disintegration-spatial` to `studies`.

Every new test guards optional frameworks so base CI skips cleanly:
```python
import pytest
pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")
```

---

## Task 1: Particle-bridge spike (retire the one-composite gap)

**Goal:** prove in a REAL `process_bigraph.Composite` that a process emitting particles via the `_add` sentinel into a shared `map[particle]` store, with a stock `BrownianMovement` on the same store, produces particles that appear then scatter — the whole bridge in one committed run. (API map §5.3 proved it with a stand-in emitter; this locks it as a test.)

**Files:** Create `tests/test_particle_bridge_spike.py`.

- [ ] **Step 1: Write the failing test (RED)**

```python
# tests/test_particle_bridge_spike.py
"""The CPM->particle bridge primitive: a process emitting particles via the map
`_add` sentinel into a shared map[particle] store, moved by a stock BrownianMovement,
makes particles appear then scatter — verified in one real Composite."""
from __future__ import annotations
import numpy as np
import pytest
from process_bigraph import Composite, Process
from meta_modelers_guide.core import build_core

pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")

NX = NY = 20
BOUNDS = (20.0, 20.0)

class _DebrisEmitter(Process):
    """Emits 3 particles on the first update tick, then nothing."""
    config_schema = {}
    def __init__(self, config, core):
        super().__init__(config, core)
        self._done = False
    def inputs(self):  return {}
    def outputs(self): return {"particles": "map[particle]"}
    def update(self, state, interval):
        if self._done:
            return {}                                  # never emit empty _add
        self._done = True
        add = {f"debris_{i}": {"id": f"debris_{i}",
                               "position": (5.0 + i, 5.0), "mass": 1.0} for i in range(3)}
        return {"particles": {"_add": add}}

def test_emit_then_scatter():
    core = build_core()
    core.register_link("_DebrisEmitter", _DebrisEmitter)
    state = {
        "particles": {},
        "emit": {"_type": "process", "address": "local:_DebrisEmitter", "config": {},
                 "outputs": {"particles": ["particles"]}},
        "move": {"_type": "process",
                 "address": "local:!spatio_flux.processes.particles.BrownianMovement",
                 "config": {"bounds": BOUNDS, "n_bins": (NX, NY), "diffusion_rate": 2.0},
                 "inputs": {"particles": ["particles"]}, "outputs": {"particles": ["particles"]}},
    }
    comp = Composite({"state": state}, core=core)
    comp.run(1)
    p1 = {k: tuple(v["position"]) for k, v in comp.state["particles"].items()}
    assert len(p1) == 3                                # emitted
    comp.run(3)
    p2 = {k: tuple(v["position"]) for k, v in comp.state["particles"].items()}
    assert len(p2) == 3                                # still 3
    moved = sum(1 for k in p1 if p2[k] != p1[k])
    assert moved >= 2                                  # scattered
```

- [ ] **Step 2: Run it** — `PYTHONPATH=$PWD ~/code/meta-modelers-guide/.venv/bin/python -m pytest tests/test_particle_bridge_spike.py -v`. If the `BrownianMovement` full address does not resolve, read `spatio_flux/processes/particles.py` for the class location and try bare `local:BrownianMovement`; record which works. If `register_link` / the `_add` merge behaves differently than the API map states, STOP and ledger — the whole study rests on this. Expected: GREEN.
- [ ] **Step 3: Commit.**

---

## Task 2: `CpmDisintegration` process

**Goal:** the CPM-world-owning process: hold coherent, trigger resorption on stressor threshold, shed vacated pixels as capped particle emissions.

**Files:** Create `meta_modelers_guide/cpm/disintegration.py`; Create `tests/test_cpm_disintegration.py`.

**Interfaces:**
- Consumes (config): `grid {nx, ny}`; `bounds {x, y}` (== grid, square cells); `cell {seed_block, target_volume, lambda_volume, temperature (10–12)}`; `viability_threshold` (stressor level that releases); `resorb_per_tick` (target-volume decrement, tuned for ~15–20-tick dissolution); `max_particles_per_tick` (cap); `contact` list.
- Consumes (ports): `inputs {fields: map[array]}` (needs `stressor`).
- Produces (ports): `outputs` = `particles: map[particle]` (via `_add`) + `volume: overwrite[float]`, `area: overwrite[float]`, `position: overwrite[list]`, `mean_stressor: overwrite[float]`, `n_components: overwrite[float]`, `largest_fragment_fraction: overwrite[float]`, `released: overwrite[boolean]`, `released_tick: overwrite[float]`.

Read `meta_modelers_guide/cpm/cell_field.py` (world construction, `_footprint`, `set_target_volume` growth) and `colony_field.py` (live-id handling) first; strip the cobra/dFBA path. Logic per tick (all verified in the API map):
1. `lat = np.array(self.world.snapshot()).reshape(ny, nx)`; `cid` = the single live id (`sorted(set(np.unique(lat)) - {0})[0]`, guard empty).
2. `fp = (lat == cid)`; `area = int(fp.sum())`; `mean_stressor = float(stressor[fp].mean()) if fp.any() else 0.0`.
3. `self._released = self._released or (mean_stressor >= viability_threshold)`; record `released_tick` on the transition.
4. If released and area > 0: `new_target = max(self._target - resorb_per_tick, 0.0)`; `self._target = new_target`; `world.set_target_volume(cid, new_target)`.
5. After `world.step(mcs)` (do the step BEFORE recomputing the diff, or hold prev/curr masks consistently — pick one order and document): `vacated = self._prev_fp & ~curr_fp`; take up to `max_particles_per_tick` vacated pixels; emit them as particles at mapped centers (`x=(i+0.5)*bx/nx, y=(j+0.5)*by/ny`) via `_add` with `self._pid` monotonic ids; `self._prev_fp = curr_fp`. Only include `_add` when ≥1 pixel shed.
6. Metrics: `n_components`, `largest_fragment_fraction` via `scipy.ndimage.label(fp)`.

- [ ] **Step 1: Write the failing test (RED)**

```python
# tests/test_cpm_disintegration.py
"""CpmDisintegration: a coherent CPM cell holds while the stressor is low, then on
threshold-cross latches `released`, resorbs (area -> 0), and sheds its vacated pixels
as particles into the shared store."""
from __future__ import annotations
import numpy as np
import pytest
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

pytest.importorskip("cpm"); pytest.importorskip("spatio_flux")

NX = NY = 40

def _state(core, stressor_level):
    stressor = np.full((NY, NX), stressor_level)
    return {
        "fields": {"stressor": stressor},
        "particles": {},
        "cell": {"_type": "process", "address": "local:CpmDisintegration",
            "config": {"grid": {"nx": NX, "ny": NY}, "bounds": {"x": NX, "y": NY},
                       "cell": {"seed_block": [16, 16, 0, 24, 24, 1], "target_volume": 64.0,
                                "lambda_volume": 2.0, "temperature": 11.0},
                       "viability_threshold": 0.5, "resorb_per_tick": 6.0,
                       "max_particles_per_tick": 8, "mcs": 3,
                       "contact": [{"a": 0, "b": 1, "j": 14.0}]},
            "inputs": {"fields": ["fields"]},
            "outputs": {"fields": ["fields"], "particles": ["particles"],
                        "area": ["obs", "area"], "released": ["obs", "released"]},
        },
    }

def test_holds_below_threshold():
    core = build_core()
    comp = Composite({"state": _state(core, 0.1)}, core=core)   # stressor below 0.5
    comp.run(12)
    assert comp.state["obs"]["released"] in (False, 0, 0.0)
    assert comp.state["obs"]["area"] > 20                        # cell intact
    assert len(comp.state["particles"]) == 0                     # no debris

def test_releases_and_disintegrates_into_particles():
    core = build_core()
    comp = Composite({"state": _state(core, 0.9)}, core=core)   # stressor above 0.5
    comp.run(20)
    assert comp.state["obs"]["released"] in (True, 1, 1.0)      # latched
    assert comp.state["obs"]["area"] < 10                        # cell dissolved
    assert len(comp.state["particles"]) > 0                      # debris created
```

- [ ] **Step 2: Run → iterate to GREEN.** Fix real API mismatches against the flagship + cpm source; do not fabricate. Expected: PASS.
- [ ] **Step 3: Commit.**

---

## Task 3: The disintegration composite

**Goal:** author `disintegration-spatial.composite.json` in the discovered `composites/` dir (so the loom Model figure bakes automatically), wiring CpmDisintegration + a rising stressor field + BrownianMovement over the shared `particles` store.

**Files:** Create `meta_modelers_guide/composites/disintegration-spatial.composite.json`; Modify `tests/test_composites_build.py`.

Composite `state`: `fields` (a `stressor` array, initialized as a gradient or with a source that `DiffusionAdvection` spreads so the footprint-local stressor RISES across the run to cross the threshold mid-run); `particles` (starts `{}`); the `CpmDisintegration` process (`local:CpmDisintegration`); the `DiffusionAdvection` stressor process (full address); `BrownianMovement` (`local:!spatio_flux.processes.particles.BrownianMovement`, `bounds`/`n_bins` == field); a `RAMEmitter`. Grid 60×60, `bounds` 60×60.

- [ ] **Step 1:** author the JSON. To make the stressor cross the viability threshold at the cell mid-run, either pre-load a rising field or add a stressor source term (a boundary/point source that diffuses inward). Verify the composite builds:
  `PYTHONPATH=$PWD ... -m pytest "tests/test_composites_build.py::test_composite_builds[disintegration-spatial]" -v`
- [ ] **Step 2:** extend the build guard so the new process is covered without demanding cobra (it doesn't use cobra):
  ```python
  if "CpmCellField" in raw or "CpmColonyField" in raw:
      pytest.importorskip("cpm")
      pytest.importorskip("cobra")
  if "CpmDisintegration" in raw:
      pytest.importorskip("cpm")           # no cobra — this study is metabolism-free
  ```
- [ ] **Step 3:** run the parametrized build case + full `-m pytest -q` (no regressions). Expected: GREEN.
- [ ] **Step 4: Commit.**

---

## Task 4: Tune + assert the disintegration regime

**Goal:** the run must READ as: cell coherent and stable while stressor is low → stressor crosses threshold mid-run → `released` latches → area collapses to ~0 over ~15–20 ticks → a debris cloud of particles appears and scatters (spread grows).

**Files:** Create `tests/test_disintegration_regime.py`.

- [ ] **Step 1: Write the failing test (RED)**

```python
# tests/test_disintegration_regime.py
"""The disintegration regime is legible over a bounded run: the cell holds, then a
rising stressor crosses its viability bound, the domain resorbs to ~0, and its shed
pixels become a scattering particle-debris cloud."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pytest
from process_bigraph import Composite
from meta_modelers_guide.core import build_core

pytest.importorskip("cpm"); pytest.importorskip("spatio_flux")
COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"

def _spread(particles):
    if len(particles) < 2:
        return 0.0
    pos = np.array([p["position"] for p in particles.values()])
    return float(np.sqrt(((pos - pos.mean(0)) ** 2).sum(1).mean()))  # RMS radius

def test_cell_holds_then_disintegrates_into_scattering_debris():
    core = build_core()
    state = json.loads((COMPOSITES / "disintegration-spatial.composite.json").read_text())["state"]
    comp = Composite({"state": state}, core=core)
    # early: coherent
    comp.run(6)
    assert comp.state["obs"]["area"] > 30
    assert comp.state["obs"]["released"] in (False, 0, 0.0)
    # late: released, dissolved, debris present and spreading
    comp.run(18)
    assert comp.state["obs"]["released"] in (True, 1, 1.0)
    assert comp.state["obs"]["area"] < 10
    parts = comp.state["particles"]
    assert len(parts) >= 20                              # substantial debris
    spread_now = _spread(parts)
    comp.run(6)
    assert _spread(comp.state["particles"]) > spread_now  # debris keeps scattering
```

- [ ] **Step 2: Run → TUNE** the composite: stressor source/gradient + `diffusion_coeffs` so the crossing lands ~tick 6–10; `resorb_per_tick` so dissolution spans ~15–20 ticks; `max_particles_per_tick` so debris count is substantial but bounded; `BrownianMovement.diffusion_rate` so the cloud visibly spreads without instantly hitting walls. Record final constants in the ledger.
- [ ] **Step 3: Commit** (composite + test together).

---

## Task 5: Disintegration visualization (the payoff)

**Goal:** a GIF showing the coherent cell, the crossing, and the dissolution into a scattering debris cloud over the stressor field; plus a synced metrics panel.

**Files:** Modify `meta_modelers_guide/cpm/viz.py`; Create `tests/test_disintegration_viz.py`.

Add `run_disintegration_frames(state, core, steps, cadence) -> (frames, metrics)` mirroring `run_flagship_frames`: reach the live world + the shared `particles` store via the composite; render each frame as the stressor field heatmap with the CPM cell pixels drawn in one color AND the particle positions overplotted as scattering points (size/alpha for debris). `metrics` holds `time`, `area`, `mean_stressor`, `n_particles`, `n_components` (+ `released_tick`). Reuse `frames_to_gif`; extend `metrics_panel` to plot area + mean_stressor (twin axis) + n_particles with a dashed `released_tick` marker (keep `include_plotlyjs`). Do not break the flagship/colony viz paths (branch on metrics shape or add a sibling function; confirm `test_cpm_viz.py` + `test_cpm_colony_viz.py` still pass).

- [ ] **Step 1: RED** — `tests/test_disintegration_viz.py`: run ≥18 steps on `disintegration-spatial`, assert ≥6 frames, metric arrays present + equal length, `n_particles` ends > 0, GIF written non-empty, metrics HTML written with a Plotly div.
- [ ] **Step 2: Implement → GREEN.**
- [ ] **Step 3: Bake** `viz/disintegration-spatial.gif` + `viz/disintegration-metrics.html` into `workspace/studies/disintegration-spatial/viz/`. Commit code now; artifacts land with the study in Task 6.

---

## Task 6: Study + investigation + report

**Goal:** author the study, wire it into the investigation, bake the loom Model figure, render the report.

**Files:** Create `workspace/studies/disintegration-spatial/study.yaml` (+ `viz/`); Modify `workspace/investigations/the-cellular-interface-multicellular/investigation.yaml`.

Model on `workspace/studies/cell-cell-coupling-spatial/study.yaml` (schema_version 4). Content:
- Name `disintegration-spatial`, investigation `the-cellular-interface-multicellular`, title "Disintegration, Spatial".
- Question: does Fig 6's level-shift hold spatially — a coherent CPM cell that loses structural viability when a diffusing stressor field crosses its bound, its domain resorbing while its shed material becomes scattering physical particles — composed from independent frameworks (viva-cpm + spatio-flux particles) through one coupling process?
- Measured outcomes (from Task 4's tuned run): held area, `released_tick`, final area ≈ 0, final debris particle count, debris spread growth.
- Cite tests: `test_particle_bridge_spike`, `test_cpm_disintegration`, `test_disintegration_regime`, `test_disintegration_viz`.
- HONEST caveats (required): the disintegration mechanism is **resorption + particle-shedding**, not lattice fragmentation (the cpm connectivity/E1 constraint is a verified no-op and `lambda_volume`/`temperature` are init-only, so a settled domain cannot be shattered in-lattice — documented in the API map); debris uses `BrownianMovement` (NumPy diffusion), not rigid-body pymunk; toy-real constants; no metabolism (unlike studies 2–3). Cross-link to the `draft-to-living-cell` analogue study `disintegration`.
- Viz refs: `image:` → `viz/disintegration-spatial.gif`; `html:` → `viz/disintegration-metrics.html`.

- [ ] **Step 1:** author `study.yaml`; add `disintegration-spatial` to the investigation's `studies:`.
- [ ] **Step 2:** `python scripts/lint-workspace.py` → `workspace lint: OK` (only the pre-existing dash-in-name WARN class).
- [ ] **Step 3:** bake the loom Model figure: `vivarium-workbench render-loom --study disintegration-spatial --max-width 1600 --colors 128` (composite is in the discovered dir).
- [ ] **Step 4:** render the investigation report; confirm the study section shows the loom Model figure (not the schematic) + the GIF + interactive metrics. Do NOT commit any generated `reports/*.html` (gitignored).
- [ ] **Step 5:** run the FULL suite `-m pytest -q` (all green) and confirm the deps-absent CI condition still skips cleanly (new tests carry the importorskip guards).
- [ ] **Step 6: Commit** study + investigation + viz artifacts (GIF, metrics HTML, model-loom PNG).

---

## Self-Review notes

- **Spec coverage:** study 4 row (structural-integrity release on stressor crossing → dissolution into particles) → Tasks 2–4 + 6; the user-selected particles path → the bridge in Tasks 1–2 + BrownianMovement in Task 3. ✓
- **Bridge assumption retired first:** Task 1 spike (emit-`_add` + scatter in one Composite). ✓
- **No cobra:** enforced in Global Constraints + the build-guard (Task 3 Step 2 keeps `CpmDisintegration` on a cpm-only guard). ✓
- **Honesty:** resorption-not-shatter + connectivity-E1-no-op + Brownian-not-pymunk are mandated caveats (Task 6). ✓
- **Type consistency:** `particles: map[particle]` (`_add`-merged, monotonic ids, mass-once) everywhere; absolute observables `overwrite[...]`; coordinate mapping `x=(i+0.5)*bx/nx, y=(j+0.5)*by/ny` with `bounds==field==CPM` used identically in the process (Task 2) and viz (Task 5). ✓
- **CI:** every new test carries `importorskip("cpm"/"spatio_flux")`; no local absolute home-dir paths in committed docs (use `~` or `<worktree>`). ✓
