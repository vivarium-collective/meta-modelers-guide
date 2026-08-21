# Code-verified API map — STUDY 4 `disintegration` (spatial)

**Date:** 2026-08-21
**Investigation:** `the-cellular-interface-multicellular`
**Analogue:** Fig 6 "level shift" (disintegration) → spatial: a coherent CPM cell domain dissolves when a stressor field crosses its viability bound.
**Verified against installed code:** `cpm` (`~/code/viva-cpm/cpm/`, Rust `cpm_core`), the merged flagship `meta_modelers_guide/cpm/cell_field.py`, study-3 `colony_field.py`, and `spatio_flux` (`~/code/spatio-flux/`).
**Interpreter:** `~/code/meta-modelers-guide/.venv/bin/python`, `PYTHONPATH=<worktree>`. All snippets below were RUN; scratch scripts (`verify_disint.py`, `verify2..7.py`) live in the session scratchpad.

---

## 1. Summary + recommended process shape + confirmed trigger

Study 4 is the **spatial analogue of the non-spatial `draft-to-living-cell` disintegration study** (`workspace/studies/disintegration/study.yaml`): there, a scripted thermal shock pushes `viability` past its bound and `biomass → debris`. Here the "viability bound" is a **stressor field** read at the cell's footprint, and "disintegration" is the **coherent cell domain visibly coming apart in `snapshot()`** over ticks.

**Recommended process shape (one line):** ONE CPM-world-owning process (`CpmDisintegration`, modeled on `CpmCellField` **minus cobra**) that each tick reads a shared spatio-flux stressor field at the cell footprint (`snapshot()==cid`), and once `mean(stressor[fp]) >= viability_threshold` **latches** a `released` flag and ramps `set_target_volume(cid) → 0` (optionally also `set_contact(0,1, negative)` to scatter the final pixels), dissolving the domain gradually over ~15–20 ticks.

**Confirmed disintegration trigger — the CRUX resolved:**
- **Connectivity is NOT usable as the structural-integrity lock.** `world.set_connectivity(type, True)` does **not** keep a cell coherent under fragmenting energetics in this build, and turning it OFF makes no difference (ON == OFF, sometimes ON gives *more* components — see Q1). It **can** be called at runtime without error, but has **no observable effect**. So the process cannot "flip connectivity" to disintegrate.
- **The true fragmentation drivers — `lambda_volume` and `temperature` — are INIT-ONLY** (no runtime setters exist; verified in Q3). The only runtime levers are `set_target_volume` and `set_contact`.
- **A settled coherent blob CANNOT be shattered into scattered pixels mid-run** by those levers (verified across temp/J/lambda sweeps in Q1–Q2: negative contact J does not overcome a settled blob's volume-constraint cohesion barrier).
- **Therefore the confirmed, reliable, gradual trigger is:** `mean(stressor[footprint]) >= threshold → ramp set_target_volume(cid) → 0` (**resorption**). The cell shrinks coherently and is reclaimed by medium (id → 0), staging a brief pixel-scatter only in its final few pixels. This is verified end-to-end (Q4/Q5).

---

## 2. Verified API

### Q1 — Connectivity constraint is NOT structural integrity (the crux)

`cpm/schema.py:73-78` wires `connectivity: {types:[...], medium:bool}` to `world.set_connectivity(int(t), True)` / `world.set_connectivity_medium(True)`. The schema docstring calls this "anti-fragmentation (E1)". **Empirically it does not anti-fragment.**

Under fragmenting energetics (negative contact J, which favors cell–medium interface), connectivity ON and OFF give statistically indistinguishable fragmentation (`scipy.ndimage.label` component count on `snapshot()==1`, 40×40, seed square, 30 mcs):

```
j=-5.0 lam_vol=2.0 conn=True : comp=67 area=111 largest=7  lff=0.06
j=-5.0 lam_vol=2.0 conn=False: comp=72 area=105 largest=5  lff=0.05
j=-2.0 lam_vol=2.0 conn=True : comp=57 area=107 largest=9  lff=0.08
j=-2.0 lam_vol=2.0 conn=False: comp=32 area=102 largest=25 lff=0.25   # OFF less fragmented!
```

Under a strong volume constraint the cell stays coherent **regardless** of connectivity (high temp/high J, 60 mcs): `conn=True` and `conn=False` produced byte-identical trajectories (`comp=1` throughout). So coherence here is supplied by the **volume constraint (`lambda_volume`) + positive contact J + moderate temperature**, not by the connectivity term.

**Runtime toggle:** `world.set_connectivity(1, False)` called after `finalize()` and mid-run returns cleanly (no exception) — but changes nothing (component count unmoved over 50 further mcs). So it is *callable* at runtime but *ineffective*.

**Conclusion:** do not build the trigger on connectivity. (Flag for the plan / possibly a `viva-cpm` E1 bug — see Risks.)

### Q2 — What "dissolve" looks like in `snapshot()`: resorption, not shatter

For a **settled** coherent cell (the study's premise — a coherent domain that then dissolves), no runtime lever fragments it into many same-id blobs. Sweeps at temp∈{15,20}, flipping contact J to −8/−16 and/or dropping/raising `target_volume`, all kept `comp=1` while area changed. Example (settle at j=14, then flip j=−16 AND `set_target_volume(1,30)`, 60 mcs):

```
temp=20 flip j->-16 & tv->30: base=(comp1 area117) -> after=(comp1 area27 lff1.0)   # shrank, stayed coherent
```

The realistic dissolution signature is therefore **coherent resorption**: the id region shrinks (stays 1 connected component, `lff≈1.0`) and is **reclaimed by medium** (id → 0), reaching area 0. Verified gradual ramp `set_target_volume 120→0` over ticks:

```
area: 117 -> 101 -> 85 -> 69 -> 52 -> 38 -> 23 -> 1 -> 0   (comp stays 1; only the last 1–4 pixels scatter to comp≈4 before vanishing)
```

(True `comp≈67` fragmentation IS reachable, but only from a **fresh seed** at negative J that *never coheres* — not from a settled cell; see Q1's `j=-5` fresh-seed rows.)

### Q3 — Runtime mutation surface (what the trigger can actually change)

`dir(cpm_core.World)` runtime setters and their verified behavior after `finalize()`:

| Method | Signature | Runtime? | Effect |
|---|---|---|---|
| `set_target_volume` | `(cid:int, v:float)` | **YES** (flagship uses it every tick) | shrink/grow; `→0` resorbs the cell cleanly |
| `set_contact` | `(a:int, b:int, j:float)` | **YES** (verified `set_contact(0,1,-16.0)` applied) | changes adhesion; does NOT shatter a settled blob |
| `set_cell_type` | `(cid:int, type:int)` | exists | (untested for this study) |
| `set_length_constraint` | `(type:int, target_len:float, lam:float)` | exists | elongation term |
| `set_external_potential` | `(type:int, fx,fy,fz:float)` | exists | constant force |
| `remove_cells` | `([cid])` | exists | quirky (study-3 Q8: `n_cells()` doesn't decrement) |
| `set_connectivity` | `(type:int, bool)` | callable | **INEFFECTIVE** (Q1) |

**No `set_lambda_volume`, no `set_lambda_surface`, no `set_temperature`** — verified absent from `dir(World)` (`'lambda'/'volume'` members are only `cell_volumes`, `set_junction_lambda`, `set_target_volume`). **`lambda_volume`, `lambda_surface`, and `temperature` are fixed at `load_world` and cannot be changed at runtime.** This is why the disintegration trigger must run through `set_target_volume` (and optionally `set_contact`).

### Q4 — Stressor field coupling (no cobra needed)

Mirror the flagship's footprint read (`cell_field.py:99-101`): reshape the flat `snapshot()` to `(ny,nx)`, mask by id, mean the shared spatio-flux `fields` array over the mask:

```python
lat = np.array(self.world.snapshot()).reshape(self._ny, self._nx)
fp  = (lat == cid)
mean_stressor = float(stressor[fp].mean()) if fp.any() else 0.0
released = released or (mean_stressor >= threshold)   # LATCH — see Q6
```

End-to-end run (synthetic ramp standing in for a `DiffusionAdvection` plume; temp=12, threshold=0.5), **no cobra imported** — the process runs `cpm + spatio-flux only`:

```
tick  mean_stressor  released  comp area  volume
  7    0.480          False      1  116  116     # coherent while stressor < 0.5
  8    0.540          True       1  101  101     # crosses threshold -> released, resorption starts
 10    0.660          True       1   69   69
 12    0.780          True       1   38   38
 14    0.900          True       1    1    1
 15    0.960          True       0    0    0     # domain fully dissolved (id -> medium)
released_tick: 8
```

**Recommendation: drop cobra for this study** (it is about the level-shift/viability release, not metabolism — the non-spatial disintegration study keeps metabolism as a separate grain-swap concern). The stressor is an ordinary spatio-flux `DiffusionAdvection` species. (`world.field_mean_at_cell` exists as a Rust-native footprint-mean, but only for a **CPM-registered** field; the stressor must live in the **writable spatio-flux `fields` store** because the CPM-internal field is write-protected — carried constraint — so read it in Python as above.)

### Q4b — "→ particles" handoff (optional)

A particle path exists in `spatio_flux/processes/`: `particles.py` (`BrownianMovement`, `ManageBoundaries`, `ParticleExchange`) and `pymunk_particles.py`. But it is a **separate state model** (a list of particles with continuous `position`/pymunk bodies), and there is **no CPM-lattice → particle adapter**. A clean handoff would require converting each shed pixel/fragment into a particle body — a nontrivial bridge. **Recommendation: keep the toy version as dispersed/resorbed CPM pixels; note "→ particles" as future work.**

### Q5 — Observables + the demonstrating metric

Emit each tick (all cheap, from `snapshot()` + one `scipy.ndimage.label`):

- `n_components` — `ndimage.label(lat==cid)[1]`
- `largest_fragment_fraction` — largest component size / total area (`lff`)
- `area` / `volume` — `int((lat==cid).sum())` == `world.cell_volumes()[cid]`
- `mean_stressor` — `stressor[fp].mean()` (guard empty fp → 0)
- `released` (bool) + `released_tick` (int)
- `position` — `world.cell_coms()[cid][:2]`

**Demonstrating signal (verified in Q4):** while `mean_stressor < threshold`, `area`/`volume` hold flat and `lff≈1.0` (integrity intact); the tick `mean_stressor` crosses → `released` flips → `area`/`volume` collapse monotonically to 0 (`lff` holds 1.0 through resorption, briefly dipping as the last few pixels scatter). Chart `area` (and `mean_stressor` on a second axis) vs tick, with a dashed line at `released_tick` — directly mirrors the non-spatial study's viability-collapse chart.

### Q6 — Gotchas for this study

- **Latch `released`.** Once `area→0` the footprint mask is empty and `mean(stressor[fp])` reads **0.0** (verified: tick 16+ show `mean_stressor 0.000`), which would *un-cross* the threshold. Latch the flag and never recompute the trigger from an empty footprint.
- **Id persists as a zeroed slot.** After resorption the cell id lingers in `cell_volumes()`/`cell_coms()` (verified: `cell_volumes()=[..., 52]` then 0, `n_cells()` stayed 1). Re-derive live ids from `np.unique(snapshot())` and guard growth math with `area = max(fp.sum(), 1)` (flagship already does this).
- **Temperature is init-only and drives fragmentation.** At `temperature=25`, even a cohesive `j=14` cell begins to fragment on its own (`comp=2` at 60 mcs) — so pick a **moderate temperature (10–12)** at init for a clean coherent baseline; you cannot lower it later.
- **`seed_block` half-open, `z1=1` for 2D** (carried constraint); overlapping blocks not relevant (single cell).
- **Gradual over ~15–20 ticks:** a `target_volume` decrement of ~16/tick dissolves ~120 px in ~7 ticks; use a gentler decrement (or a stressor-proportional rate) to stretch to 15–20 for a watchable GIF.
- **Connectivity interaction:** none usable (Q1) — do not add it expecting an integrity lock.

---

## 3. Carried-over constraints (still binding)

From the flagship and study-3 API maps / plans:

- **Worktree discipline:** all work in `<worktree>` (`~/code/meta-modelers-guide--cpm-multicellular`); `PYTHONPATH` prepended; venv interpreter above. Read-only except the one output file.
- **Full import-path process addresses:** `local:!spatio_flux.processes.diffusion_advection.DiffusionAdvection` (bare `local:DiffusionAdvection` collides with `viva_munk`); in-repo processes register via `build_core()`.
- **Shared-grid contract:** all arrays `(ny,nx)` = (rows, cols); x=cols, y=rows; CPM dims == spatio-flux `n_bins`; `snapshot()`/`field_conc()` are flat `x + y*nx` → reshape `(ny,nx)`; spatio-flux needs square cells.
- **`DiffusionAdvection.update()` returns DELTAS** the engine applies; the stressor lives in the writable spatio-flux `fields` store (CPM-internal field is write-protected).
- **`overwrite[...]` on absolute observables:** `volume`, `position`, `area`, `mean_stressor`, `n_components`, `largest_fragment_fraction` are per-tick absolute readings → declare `overwrite[...]` (plain `float`/`list` apply is additive/concatenating, per flagship `outputs()` docstring). A boolean `released`/`released_tick` likewise `overwrite`.
- **`cell_coms()`/`cell_volumes()`/`cell_types()` are LISTS indexed by id, element `[0]` = medium** (study-3 Q1). Use `[cid]`, never `.get()`.
- **Toy-real:** plausible constants, not a fitted organism; honest framing (the non-spatial study's `wholecell.py`-style honesty note applies).

---

## 4. Open risks / decisions for the plan

1. **"Dispersed pixels" is not literally achievable from a settled cell in this engine.** The honest, verified mechanism is **coherent resorption** (shrink-to-medium), not shatter-into-N-fragments — the fragmentation drivers (`lambda_volume`, `temperature`) are init-only and negative contact J does not break a settled blob's cohesion barrier (Q1/Q2). **Decision:** frame the study as *dissolution by resorption* (area collapse to medium, with a brief terminal pixel-scatter) — which faithfully renders "coherent domain dissolves." If the reviewer insists on visible N-way fragmentation, the only routes are (a) seed the cell in a barely-cohered high-temperature/low-`lambda_volume` regime so release genuinely scatters it (fragile tuning; even then a settled blob barely fragments), or (b) the heavy CPM→particles bridge (Q4b). Recommend (resorption) unless told otherwise.
2. **The connectivity constraint (`E1`) appears to be a no-op in this `viva-cpm` build.** The schema advertises it as anti-fragmentation but it neither prevents fragmentation nor keeps a cell coherent, ON or OFF (Q1). Do not rely on it; flag it upstream as a probable bug so the plan doesn't design around a lever that doesn't work.
3. **Empty-footprint / vanished-cell bookkeeping.** After the domain dissolves, `mean(stressor[fp])` reads 0 (must latch `released`), the id lingers as a zeroed slot in `cell_volumes()`/`cell_coms()` (re-derive live ids from `snapshot()`), and growth math must guard `area = max(fp.sum(),1)` (Q6). Cheap to handle but each is a real footgun if missed.

Lesser: choosing a moderate init temperature (10–12) so the coherent baseline is clean (Q6); stretching the resorption ramp to 15–20 ticks for a watchable GIF; the `remove_cells` id-slot quirk if removal is ever used (prefer `target_volume→0`).

---

## 5. Particle-bridge addendum (CPM→particles, user-selected path)

The user chose the **dramatic path**: when a CPM cell crosses its viability bound, its shed pixels are **converted into physical particles that scatter**, rather than being silently resorbed into medium. This addendum verifies the particle-side API by reading and RUNNING the real code (`~/code/spatio-flux/spatio_flux/processes/particles.py`, `pymunk_particles.py`, `~/code/spatio-flux/spatio_flux/__init__.py` type specs, `spatio_flux/composites/particles.py`). All snippets were RUN with `PYTHONPATH=<worktree>` and `~/code/meta-modelers-guide/.venv/bin/python`; scratch scripts (`vp1.py`, `vp2.py`) live in the session scratchpad. **spatio_flux resolves to the editable checkout at `~/code/spatio-flux/` and `import pymunk` succeeds (7.3.0).**

**Recommended bridge composition (one paragraph).** Use **two processes over one shared `particles` store** (typed `map[particle]`). The existing `CpmDisintegration` process (§1) gains a second output port `particles: map[particle]`; each tick, after `released`, it diffs the previous vs current footprint mask, and for every just-vacated pixel emits a NEW particle into the shared store via the map **`_add` sentinel** (`{'particles': {'_add': {new_id: {...}}}}`), using a **monotonic counter** for ids (no random/Date). A second process, stock **`BrownianMovement`** (from `spatio_flux.processes.particles`), is wired to the same `['particles']` store and scatters every particle each tick by emitting absolute replacement positions. This is the classic "one process emits into a store moved by a second process" shape and it is **verified working end-to-end** (Q3 below) — no need for the disintegration process to own/move the particle list itself. `ManageBoundaries` (a `Step`) is optional and only needed if you want particles absorbed/reflected at the domain edge; `BrownianMovement` already clamps to `bounds`.

### Q5.1 — Particle state schema (RUN)

The collection is a **`map[particle]`** — a plain dict keyed by particle id; the engine merges it by key, so emitting `{new_id: {...}}` (under `_add`) adds one particle. The `particle` type is `SIMPLE_PARTICLE_TYPE` (`~/code/spatio-flux/spatio_flux/__init__.py:32-39`): fields `id: string`, `position: position` (a `tuple[set_float, set_float]` = replace-on-update x,y), `mass: mass{1.0}` (non-negative accumulator), plus optional `local: map[concentration]`, `exchange: map[count]`, `sub_masses: map[mass]`. Coordinates are **continuous within `bounds`** (`env_size = ((0, bounds[0]), (0, bounds[1]))`), and the field contract is `arr[y, x]` = `arr[row, col]` (`get_local_field_values`, `particles.py:43-67`) — the same `(ny,nx)` grid the CPM side uses.

```
=== Q1 particle collection (map keyed by id) ===
'p_0' {'id': 'p_0', 'position': (27.44.., 35.75..), 'mass': 0.603..}
'p_1' {'id': 'p_1', 'position': (27.24.., 21.18..), 'mass': 0.646..}
particle type schema: id:String position:Position[SetFloat,SetFloat] mass:Mass(_default=1.0)
  local:Map[String->Concentration] exchange:Map[String->Count] sub_masses:Map[String->Mass]
```

A particle needs only `{id, position, mass}` to be valid; `local`/`exchange`/`sub_masses` are only touched by `ParticleExchange`/`ParticleDivision` and can be omitted for pure scatter debris.

### Q5.2 — Which mover: BrownianMovement (recommended) vs pymunk

**Recommend `BrownianMovement`** for "cell explodes into scattering debris." It is pure NumPy (`particles.py:148-200`): each tick it displaces every particle by a diffusion-scaled Gaussian step plus optional advection and clamps to `bounds` — exactly the drifting-debris visual, with two knobs (`diffusion_rate`, `advection_rate`) and no native deps. It **verifiably moves particles** (Q5.1 run: three particles seeded at (25,25),(10,40),(40,10) drift each tick):

```
=== Q2 BrownianMovement before/after ===
t0: {'p_0': (25.0, 25.0),   'p_1': (10.0, 40.0),  'p_2': (40.0, 10.0)}
t1: {'p_0': (25.685, 25.819),'p_1': (9.743, 41.994),'p_2': (39.47, 10.389)}
t2: {'p_0': (24.326, 26.352),'p_1': (9.79, 42.957), 'p_2': (37.259, 9.588)}
```

`PymunkParticleMovement` (`pymunk_particles.py`) is a rigid-body integrator with gravity (default −9.81), walls, collisions, friction, damping and substeps (default 100) — heavier to configure (particles fall and pile unless gravity is zeroed) and pulls the native `pymunk`/chipmunk lib. `import pymunk` **does** succeed in this env (7.3.0), but tests that import `pymunk_particles` should still carry a `pytest.importorskip("pymunk")` guard for portability (and note `pymunk_particles.py` also imports `spatio_flux.plots.multibody_plots`, which pulls plotting deps at import time). For pure scatter, Brownian is lighter and more reliable.

### Q5.3 — Emitting NEW particles from a separate process (the crux) — VERIFIED YES

**Yes.** A separate process can add particles to the shared `map[particle]` store each tick by returning the map **`_add` sentinel**; the reconciler merges the new keys in. Proof (`vp2.py`): a tiny `Emitter` process (empty inputs) emits 3 new particles on one tick via `{'particles': {'_add': {pid: {'id':pid,'position':(x,y),'mass':1.0}}}}` into a store that **starts empty**, and a stock `BrownianMovement` wired to the same `['particles']` store then scatters them:

```
=== Q3/Q4 emit NEW particles from a separate process, then scatter ===
t0 (empty):        {}
t1 (after emit):   {'debris_0001': (10.5, 10.5), 'debris_0002': (11.5, 10.5), 'debris_0003': (10.5, 11.5)}
t2 (scattered):    {'debris_0001': (13.749, 9.276), 'debris_0002': (10.444, 8.354), 'debris_0003': (12.231, 6.897)}
t3 (scattered):    {'debris_0001': (17.238, 7.754), 'debris_0002': (11.082, 7.855), 'debris_0003': (15.155, 2.777)}
count: 3
```

The particles appear at their mapped pixel centers on the emit tick and scatter thereafter — the whole bridge in one run. Port shape to append is **`{'particles': {'_add': {new_id: {'id':…, 'position':(x,y), 'mass':…}}}}`** with `outputs()` returning `{'particles': 'map[particle]'}`. (To remove particles later, the symmetric `{'particles': {'_remove': [id,…]}}` sentinel exists — used by `ManageBoundaries`/`ParticleDivision`.) A whole-list overwrite is **not** required. Registration note: in-repo processes register via `core.register_link('Emitter', Emitter)` (not `register_process`); the composite then addresses it `local:Emitter`.

### Q5.4 — Coordinate mapping CPM pixel → particle position (VERIFIED round-trip)

A shed footprint pixel at lattice array index `[row=j, col=i]` (from `lat = snapshot().reshape(ny, nx)`, §Q4) maps to the **pixel-center** continuous position

```
x = (i + 0.5) * bounds_x / nx        # col → x
y = (j + 0.5) * bounds_y / ny        # row → y
```

where `bounds` is the **shared field's physical bounds** and `(nx, ny)` its bin count (must equal the CPM `(nx, ny)`; square cells). With `nx=ny=40, bounds=(40,40)` each pixel is 1 unit and the center offset is +0.5. Verified this round-trips exactly through spatio-flux's own `get_bin_position` (a particle placed at the mapped position lands back in the originating bin):

```
pixel(col=10,row=10) -> pos(10.5,10.5) -> bin(xbin=10,ybin=10)  match=True
pixel(col=0, row=0)  -> pos(0.5, 0.5)  -> bin(0,0)              match=True
pixel(col=39,row=39) -> pos(39.5,39.5) -> bin(39,39)            match=True
pixel(col=25,row=7)  -> pos(25.5,7.5)  -> bin(25,7)             match=True
```

Because both the CPM footprint read and the particle field-sampling use `arr[row, col]` = `arr[y, x]`, **no axis flip is needed** — x follows columns, y follows rows on both sides. (Only requirement: the particle `bounds` must be set equal to the field/lattice physical size, not left at the `_constants.SQUARE_BOUNDS=(50,50)` default while the CPM is 40×40.)

### Q5.5 — Recommended bridge handoff (the design)

Each tick after `released`: compute `vacated = prev_mask & ~curr_mask` (pixels the resorption ramp `set_target_volume→0` just freed), and for each vacated pixel `(i,j)` emit one particle at its mapped center (Q5.4) into the shared store via `_add` (Q5.3), incrementing a monotonic `self._pid_counter`. `BrownianMovement` on the same store scatters them. So it is **ONE process (`CpmDisintegration`) emitting into a `particles: map[particle]` store that a SECOND process (`BrownianMovement`) moves** — the disintegration process does *not* own particle motion. Composite wiring:

```
state:
  fields:      map[array]          # shared grid: stressor (+ any diffusands)
  particles:   map[particle]       # shared debris store, starts {}
  cpm_disint:  process  address local:CpmDisintegration
               inputs  {fields: [fields]}
               outputs {fields: [fields], particles: [particles], volume/area/... : [...]}
  stressor:    process  address local:!spatio_flux.processes.diffusion_advection.DiffusionAdvection
               inputs/outputs {fields: [fields]}
  brownian:    process  address local:BrownianMovement
               config  {bounds: <field bounds>, n_bins: <field n_bins>, diffusion_rate: ~2.0}
               inputs/outputs {particles: [particles]}
  # optional: enforce_boundaries (ManageBoundaries Step) if edge absorption/reflection wanted
```

`CpmDisintegration` keeps its existing `overwrite[...]` observable ports; add `particles: 'map[particle]'` to its `outputs()`.

### Q5.6 — Bridge-specific risks / gotchas

- **Particle-count blow-up.** A ~120-pixel cell converting over ~7–15 ticks yields ~120 particles; converting the whole footprint on ONE tick spikes the store and forces a full structural realize. **Cap particles/tick** (emit at most k of the vacated pixels per tick, or 1 particle per N vacated pixels) — this also stretches the scatter into a watchable GIF. Matches the resorption ramp already recommended in §Q6.
- **Deterministic ids, no `_add: {}` churn.** Generate ids from a **monotonic counter** on the process instance (`self._pid_counter`), never `random`/`short_id`/Date, so runs are reproducible. And only include the `_add` key on ticks where something was actually shed — emitting an empty `_add: {}` every tick flips `has_structural` in the reconciler and forces a full realize (the stock steps guard this explicitly, `particles.py:363-371`).
- **Bounds must equal the field's physical size** (Q5.4). Leaving `BrownianMovement`/emitter `bounds` at the `_constants` default (50,50) while the CPM lattice is 40×40 puts debris in the wrong place and mis-clamps at the edge. Set `bounds = field bounds`, `n_bins = field n_bins = CPM (nx,ny)`.
- **Boundary handling.** `BrownianMovement` **clamps** positions to `[0,bounds]` (`np.clip`, `particles.py:192-193`) — debris piles on the wall, never leaves or wraps. `ManageBoundaries` (a `Step`) instead **reflects** all sides by default and only **removes** particles on sides listed in `boundary_to_remove` (absorbing); it can also *add* inflow particles (`add_rate`) which you do NOT want here (leave `add_rate=0`). For a contained "debris settles in the dish" look, Brownian's clamp is fine; add `ManageBoundaries` only if you want debris to leave the frame.
- **`position` replaces, `mass` accumulates.** `position` is `tuple[set_float,set_float]` (replace-on-apply — correct for absolute moves), but `mass` is a `Mass` (non-negative *accumulator*): if any process emits a `mass` delta each tick it will sum. Debris that only scatters should emit `mass` **once, in the `_add` payload**, and never again.
- **Native/plot deps in the pymunk path.** If pymunk is ever chosen, `import spatio_flux.processes.pymunk_particles` pulls `pymunk` (native chipmunk) *and* `spatio_flux.plots.multibody_plots` at module top — guard tests with `pytest.importorskip("pymunk")`. Brownian has neither dependency.
- **Could-not-verify.** Not verified in a single composite that also runs the real `CpmDisintegration` + `DiffusionAdvection` together with the emitter (the emitter here was a stand-in to isolate the `_add`→move mechanism). The three mechanisms are each proven; wiring them in one Composite is a mechanical next step, not a new API risk.
