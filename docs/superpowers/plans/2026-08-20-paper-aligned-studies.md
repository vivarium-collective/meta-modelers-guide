# Paper-Aligned Studies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the `draft-to-living-cell` investigation into 9 studies, one per composition-pattern section of the paper, each authored as a typed contract compiled to an executable, with the 5-laws apparatus re-homed to where the paper actually argues each law.

**Architecture:** The composite/handler/env/test code is already figure-numbered correctly, so the work is (A) build the one genuinely-missing pattern — cell–cell coupling — as a new draft + handlers + env + composite + BUILD entry + law test; (B) re-author the study layer 6→9 via the `/viva-study` skill, re-homing the three metabolisms into `disintegration`/`autopoiesis` and the impostor into `cellular-interface`; (C) re-anchor `investigation.yaml`, `README.md`, and regenerate reports. The paper's Fig 6 is Disintegration (not a fabricated "metabolism" figure) and the existing `fig06-disintegration` composite already models the cell↔molecular-network grain-swap — the fix is narrative + study placement, not new metabolism code.

**Tech Stack:** Python, `process_bigraph`, `viva_compiler` (the compiler + laws), pytest, the `/viva-*` workbench skills, COBRApy (optional, guarded).

**Spec:** `docs/superpowers/specs/2026-08-20-paper-aligned-studies-design.md`

## Global Constraints

- **Worktree discipline:** all work happens in the worktree `~/code/meta-modelers-guide--paper-aligned` on branch `paper-aligned-studies`. Never `git checkout`/commit in the canonical `~/code/meta-modelers-guide`. Verify `git branch --show-current` before each commit.
- **Editable install points at the canonical checkout.** Run every test/script with the worktree prepended: `PYTHONPATH=~/code/meta-modelers-guide--paper-aligned pytest …`. Verify once with `PYTHONPATH=~/code/meta-modelers-guide--paper-aligned python -c "import meta_modelers_guide, os; print(meta_modelers_guide.__file__)"` — the path must contain `--paper-aligned`.
- **Study writes go through `/viva-study`** (canonicalization + provenance), not hand-edited YAML. Requires the workbench running (`/viva-workbench start`; `workspace.yaml` has `server.enabled: false`).
- **Composites the compiler owns are generated,** not hand-edited: after touching handlers/envs/semantic drafts, regenerate with `PYTHONPATH=… python scripts/build_executables.py`.
- **COBRApy-dependent tests stay guarded** (`pytest.importorskip("cobra")` / graceful skip), as in commit #32.
- **Study naming:** kebab-case slug matching the study dir; `schema_version: 4`; `required: [name, baseline]`; baseline is a non-empty list of `{name, composite, params}` with package-qualified composite ids (`meta_modelers_guide.composites.<stem>`).
- **The 9 studies, in paper order:** `cellular-interface`, `cell-environment-coupling`, `cell-cell-coupling`, `disintegration`, `molecular-interfaces`, `biomolecular-complementarity`, `autopoiesis`, `growth-and-division`, `development-and-evolution`.
- **Law homes:** Law 1 (conformance/impostor) → `cellular-interface`; Law 2/3 → every study; Law 4 (handler independence / grain-swap) → `disintegration` + `autopoiesis`; Law 2′ (rewrite) → `growth-and-division` + `development-and-evolution`.

---

## File Structure

**New files:**
- `meta_modelers_guide/handlers_cellcell.py` — competition + cross-feeding handlers over one cell–cell coupling interface, plus its `ENV` maps.
- `meta_modelers_guide/composites/cellcell-coupling.composite.json` — the draft (contract) composite: two cell agents wired to a shared environmental nutrient store.
- `tests/test_cellcell.py` — the cell–cell law test (competition drives one cell's viability below the other's; interface preserved; handler independence competition vs cross-feed).
- `meta_modelers_guide/composites/fig06-disintegration-dynamics.composite.json` — a **playable** level-shift composite (thermal shock → viability collapse → biomass → molecular debris) with a RAM emitter, so stepping through it in the Composite Explorer/loom visibly shows disintegration.
- `scripts/build_disintegration.py` — serializes `build_disintegration()` to that composite JSON (mirrors `scripts/build_executables.py`'s write pattern).
- `tests/test_disintegration_dynamics.py` — asserts that over the play viability collapses below the floor and molecular debris accumulates while biomass falls.
- 3 new study dirs under `workspace/studies/`: `cell-cell-coupling/`, plus renamed dirs (see tasks).

**Modified files:**
- `meta_modelers_guide/interfaces.py` — add the `CellAgent` + `SharedNutrientEnv` draft processes (Fig-less cell–cell section).
- `meta_modelers_guide/handler_envs.py` — register `cellcell-compete` and `cellcell-crossfeed` envs.
- `scripts/build_executables.py` — add the two cell–cell BUILD rows.
- `workspace/investigations/draft-to-living-cell/investigation.yaml` — full re-author (order, at_a_glance, executive, scientific_argument, capstone, caveats).
- `README.md` — remove the "Fig 6 = metabolism" flagship; re-anchor to the paper's arc; fix the composite table.
- `workspace/studies/*` — 6 studies re-authored into 9 (via `/viva-study`).

---

## Phase A — Build the missing pattern (cell–cell coupling)

### Task 1: Cell–cell coupling — draft, handlers, env, composite, BUILD, test

**Files:**
- Modify: `meta_modelers_guide/interfaces.py` (append two `@draft_process` classes)
- Create: `meta_modelers_guide/handlers_cellcell.py`
- Modify: `meta_modelers_guide/handler_envs.py:23` (register two envs)
- Modify: `scripts/build_executables.py:22` (BUILD rows)
- Create: `meta_modelers_guide/composites/cellcell-coupling.composite.json`
- Test: `tests/test_cellcell.py`

**Interfaces:**
- Consumes: `process_bigraph.Process`, `DraftProcess`, `draft_process`; `meta_modelers_guide.core.build_core`; `meta_modelers_guide.compile.{compile_composite, interface_of, check_conformance}`; `meta_modelers_guide.handler_envs.ENVS`.
- Produces: draft classes `CellAgent`, `SharedNutrientEnv`; handlers `CompetingCell`, `CrossFeedingCell`, `NutrientPool`; envs `ENVS["cellcell-compete"]`, `ENVS["cellcell-crossfeed"]`; composite stem `cellcell-coupling`; executables `cellcell-executable-compete`, `cellcell-executable-crossfeed`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cellcell.py`:

```python
"""Cell–cell coupling: two cell interfaces coupled through one shared nutrient
store negotiate viability. Competition drives the weaker cell out of its viable
band while the stronger persists; a cross-feeding handler over the SAME coupling
interface stabilizes both (law 4). Interface preserved under compilation (law 2)."""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite

from meta_modelers_guide.core import build_core
from meta_modelers_guide.compile import compile_composite, interface_of
from meta_modelers_guide.handler_envs import ENVS

COMPOSITES = Path(__file__).resolve().parent.parent / "meta_modelers_guide" / "composites"


def _sem():
    return json.loads((COMPOSITES / "cellcell-coupling.composite.json").read_text())["state"]


def _run(env_name):
    core = build_core()
    ex = compile_composite(_sem(), ENVS[env_name], core)
    assert interface_of(ex) == interface_of(_sem())  # law 2
    comp = Composite({"state": ex}, core=core)
    comp.run(20)
    return comp.state


def test_competition_pushes_weaker_cell_out_of_viable_bounds():
    st = _run("cellcell-compete")
    va = st["cell_a"]["viability"]
    vb = st["cell_b"]["viability"]
    # cell_a has the higher uptake capacity → it stays viable and cell_b starves.
    assert va > 0.5 and vb < 0.5, f"expected a>0.5>b, got a={va} b={vb}"
    # shared resource actually depleted (coupling is real, not two isolated cells)
    assert st["env"]["nutrient"] < 1.0


def test_crossfeeding_keeps_both_cells_viable():
    st = _run("cellcell-crossfeed")
    va = st["cell_a"]["viability"]
    vb = st["cell_b"]["viability"]
    assert va > 0.5 and vb > 0.5, f"cross-feeding should sustain both, got a={va} b={vb}"


def test_handler_independence_same_interface():
    # law 4: competition and cross-feeding are two handler envs over ONE interface.
    core = build_core()
    compete = compile_composite(_sem(), ENVS["cellcell-compete"], core)
    crossfeed = compile_composite(_sem(), ENVS["cellcell-crossfeed"], core)
    assert interface_of(compete) == interface_of(crossfeed) == interface_of(_sem())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=~/code/meta-modelers-guide--paper-aligned pytest tests/test_cellcell.py -v`
Expected: FAIL — `cellcell-coupling.composite.json` missing / envs not defined.

- [ ] **Step 3: Add the draft processes to `interfaces.py`**

Append to `meta_modelers_guide/interfaces.py`:

```python
# ─────────────────────────────────────────────────────────────────────────────
# Cell–cell coupling (paper §"Cell–cell coupling"; no dedicated figure).
# Two cell agents share one environmental nutrient store; what is coupled is not
# only state but CONSTRAINT — each cell's uptake reshapes the other's viability.
# ─────────────────────────────────────────────────────────────────────────────
@draft_process(
    name="CellAgent",
    inputs={"nutrient": "concentration"},
    outputs={"nutrient": "concentration", "biomass": "mass", "viability": "viability"},
    contract={
        "summary": "A cell agent coupled to shared environmental nutrient.",
        "behavior": "Takes up nutrient from a shared pool, grows biomass, and "
                    "maintains viability only while uptake meets its maintenance "
                    "demand; its uptake depletes the pool other cells depend on.",
        "senses": "the shared environmental nutrient concentration.",
        "affects": "the shared nutrient pool (depletion) and its own biomass and "
                   "viability.",
        "constraints": "nutrient mass is conserved across the shared pool; "
                       "viability stays in [0,1] and falls when uptake < maintenance.",
        "ports": {
            "nutrient": "shared environmental nutrient concentration (mol·L⁻¹)",
            "biomass": "cell biomass (kg)",
            "viability": "in-bounds fraction; 1 = viable, 0 = starved (0–1)",
        },
    },
)
class CellAgent(DraftProcess):
    pass


@draft_process(
    name="SharedNutrientEnv",
    inputs={"nutrient": "concentration"},
    outputs={"nutrient": "concentration"},
    contract={
        "summary": "The shared environmental store the cells compete over.",
        "behavior": "Holds and slowly replenishes the nutrient pool both cells "
                    "read and deplete — the medium through which their interfaces "
                    "are indirectly coupled.",
        "senses": "the nutrient pool.",
        "affects": "the nutrient pool via a bounded replenishment source.",
        "constraints": "concentration stays non-negative.",
        "ports": {"nutrient": "environmental nutrient concentration (mol·L⁻¹)"},
    },
)
class SharedNutrientEnv(DraftProcess):
    pass
```

- [ ] **Step 4: Create the handlers `meta_modelers_guide/handlers_cellcell.py`**

```python
"""Cell–cell coupling handlers — two cells over ONE shared nutrient store.

Competition and cross-feeding are two handler environments over the same coupling
interface (law 4). Both deplete the shared pool; the cross-feeding cell also
returns a usable byproduct, so the pair persists where competition starves one.
Handlers auto-registered at ``local:<ClassName>`` by build_core."""
from __future__ import annotations

from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


class NutrientPool(Process):
    """Shared environmental pool: bounded first-order replenishment toward capacity."""
    config_schema = {"supply": _f(0.02), "capacity": _f(1.0)}

    def inputs(self):
        return {"nutrient": "concentration"}

    def outputs(self):
        return {"nutrient": "concentration"}

    def update(self, state, interval):
        n = float(state.get("nutrient", 0.0))
        c = self.config
        return {"nutrient": c["supply"] * (c["capacity"] - n) * interval}


class CompetingCell(Process):
    """Saturating uptake from the shared pool; viability falls when uptake drops
    below maintenance. Depletes the shared nutrient (negative delta) — the coupling.
    ``vmax`` sets competitive strength (cell_a > cell_b in the compete env)."""
    config_schema = {"vmax": _f(0.6), "km": _f(0.3), "yield_": _f(0.5),
                     "maintenance": _f(0.15), "via_gain": _f(0.4)}

    def inputs(self):
        return {"nutrient": "concentration", "viability": "viability"}

    def outputs(self):
        return {"nutrient": "concentration", "biomass": "mass", "viability": "viability"}

    def update(self, state, interval):
        n = float(state.get("nutrient", 0.0))
        v = float(state.get("viability", 1.0))
        c = self.config
        uptake = c["vmax"] * n / (c["km"] + n) if (c["km"] + n) else 0.0
        # viability climbs toward 1 when uptake beats maintenance, falls otherwise.
        surplus = uptake - c["maintenance"]
        target = 1.0 if surplus >= 0 else 0.0
        dv = c["via_gain"] * (target - v) * interval
        return {"nutrient": -uptake * interval,
                "biomass": c["yield_"] * uptake * v * interval,
                "viability": dv}


class CrossFeedingCell(Process):
    """Same coupling interface as CompetingCell, but returns a usable byproduct to
    the shared pool (partial return), so the pair does not exhaust the resource and
    both stay above maintenance — cooperation stabilizes viability (law 4 contrast)."""
    config_schema = {"vmax": _f(0.6), "km": _f(0.3), "yield_": _f(0.5),
                     "maintenance": _f(0.15), "via_gain": _f(0.4), "return_frac": _f(0.7)}

    def inputs(self):
        return {"nutrient": "concentration", "viability": "viability"}

    def outputs(self):
        return {"nutrient": "concentration", "biomass": "mass", "viability": "viability"}

    def update(self, state, interval):
        n = float(state.get("nutrient", 0.0))
        v = float(state.get("viability", 1.0))
        c = self.config
        uptake = c["vmax"] * n / (c["km"] + n) if (c["km"] + n) else 0.0
        surplus = uptake - c["maintenance"]
        target = 1.0 if surplus >= 0 else 0.0
        dv = c["via_gain"] * (target - v) * interval
        net = uptake * (1.0 - c["return_frac"])  # byproduct returned to the pool
        return {"nutrient": -net * interval,
                "biomass": c["yield_"] * uptake * v * interval,
                "viability": dv}
```

- [ ] **Step 5: Register the envs in `handler_envs.py`**

After the `ENVS["fig06-fba"] = …` line, append:

```python
# Cell–cell coupling: two cells over ONE shared-nutrient interface (law 4).
# cell_a is the stronger competitor (higher vmax); cell_b starves under compete.
from .handlers_cellcell import NutrientPool  # noqa: F401  (registration side-effect)

ENVS["cellcell-compete"] = {
    "SharedNutrientEnv": {"handler": "NutrientPool",
                          "config": {"supply": 0.02, "capacity": 1.0},
                          "init": {"env.nutrient": 1.0}},
    "CellAgent#a": {"handler": "CompetingCell",
                    "config": {"vmax": 0.8, "km": 0.3, "yield_": 0.5,
                               "maintenance": 0.15, "via_gain": 0.4},
                    "init": {"cell_a.viability": 1.0}},
    "CellAgent#b": {"handler": "CompetingCell",
                    "config": {"vmax": 0.35, "km": 0.3, "yield_": 0.5,
                               "maintenance": 0.15, "via_gain": 0.4},
                    "init": {"cell_b.viability": 1.0}},
}

ENVS["cellcell-crossfeed"] = {
    "SharedNutrientEnv": {"handler": "NutrientPool",
                          "config": {"supply": 0.02, "capacity": 1.0},
                          "init": {"env.nutrient": 1.0}},
    "CellAgent#a": {"handler": "CrossFeedingCell",
                    "config": {"vmax": 0.6, "km": 0.3, "yield_": 0.5,
                               "maintenance": 0.15, "via_gain": 0.4, "return_frac": 0.7},
                    "init": {"cell_a.viability": 1.0}},
    "CellAgent#b": {"handler": "CrossFeedingCell",
                    "config": {"vmax": 0.6, "km": 0.3, "yield_": 0.5,
                               "maintenance": 0.15, "via_gain": 0.4, "return_frac": 0.7},
                    "init": {"cell_b.viability": 1.0}},
}
```

> Note: the composite has two distinct process nodes both wired to the `CellAgent`
> draft. If the env key must be unique per node, the composite's two cell nodes use
> node names `cell_a`/`cell_b` and the env maps by draft name; if `compile_composite`
> keys env entries by node rather than draft, replace the `"CellAgent#a"/"#b"` keys
> with the node names the compiler expects (verify against the failing test output in
> Step 8 and align — this is the one place the env↔node keying must match the
> compiler's convention).

- [ ] **Step 6: Create the draft composite `meta_modelers_guide/composites/cellcell-coupling.composite.json`**

```json
{
  "name": "Cell–Cell Coupling",
  "description": "Paper §Cell–cell coupling (no dedicated figure). Two cell agents are wired to ONE shared environmental nutrient store: each senses the pool and depletes it, so their interfaces are coupled not only through shared state but through CONSTRAINT — one cell's uptake reshapes the other's viability. DRAFT: typed ports + contract, no dynamics.",
  "requires": {
    "processes": ["CellAgent", "SharedNutrientEnv"],
    "types": ["concentration", "mass", "viability"]
  },
  "state": {
    "shared_env": {
      "_type": "process",
      "address": "local:SharedNutrientEnv",
      "config": {"interval": 1.0},
      "inputs": {"nutrient": ["env", "nutrient"]},
      "outputs": {"nutrient": ["env", "nutrient"]}
    },
    "cell_a_proc": {
      "_type": "process",
      "address": "local:CellAgent",
      "config": {"interval": 1.0},
      "inputs": {"nutrient": ["env", "nutrient"], "viability": ["cell_a", "viability"]},
      "outputs": {"nutrient": ["env", "nutrient"], "biomass": ["cell_a", "biomass"], "viability": ["cell_a", "viability"]}
    },
    "cell_b_proc": {
      "_type": "process",
      "address": "local:CellAgent",
      "config": {"interval": 1.0},
      "inputs": {"nutrient": ["env", "nutrient"], "viability": ["cell_b", "viability"]},
      "outputs": {"nutrient": ["env", "nutrient"], "biomass": ["cell_b", "biomass"], "viability": ["cell_b", "viability"]}
    },
    "env": {"nutrient": {"_type": "concentration", "_value": 1.0}},
    "cell_a": {"biomass": {"_type": "mass", "_value": 0.0}, "viability": {"_type": "viability", "_value": 1.0}},
    "cell_b": {"biomass": {"_type": "mass", "_value": 0.0}, "viability": {"_type": "viability", "_value": 1.0}}
  }
}
```

- [ ] **Step 7: Add BUILD rows in `scripts/build_executables.py`**

Add to the `BUILD` list (after the fig10 rows):

```python
    ("cellcell-compete",   "cellcell-coupling", "cellcell-executable-compete"),
    ("cellcell-crossfeed", "cellcell-coupling", "cellcell-executable-crossfeed"),
```

- [ ] **Step 8: Run the test; align env↔node keying if needed**

Run: `PYTHONPATH=~/code/meta-modelers-guide--paper-aligned pytest tests/test_cellcell.py -v`
Expected: PASS. If it fails on conformance/keying, the env's per-node key convention is wrong — inspect how `compile_composite` matches env entries to the two `CellAgent` nodes (see `viva_compiler.compiler._iter_processes` / `_draft_name`) and set the env keys accordingly (node names `cell_a_proc`/`cell_b_proc` are the fallback). Re-run until green. Tune `vmax`/`maintenance` only if competition doesn't separate the viabilities (a must stay >0.5, b <0.5).

- [ ] **Step 9: Materialize the executables and run the compilation law-suite**

Run:
```bash
PYTHONPATH=~/code/meta-modelers-guide--paper-aligned python scripts/build_executables.py
PYTHONPATH=~/code/meta-modelers-guide--paper-aligned pytest tests/test_cellcell.py tests/test_compilation.py tests/test_composites_build.py -v
```
Expected: two `cellcell-executable-*.composite.json` written; all listed tests PASS.

- [ ] **Step 10: Commit**

```bash
cd ~/code/meta-modelers-guide--paper-aligned
git add meta_modelers_guide/interfaces.py meta_modelers_guide/handlers_cellcell.py \
        meta_modelers_guide/handler_envs.py scripts/build_executables.py \
        meta_modelers_guide/composites/cellcell-coupling.composite.json \
        meta_modelers_guide/composites/cellcell-executable-compete.composite.json \
        meta_modelers_guide/composites/cellcell-executable-crossfeed.composite.json \
        tests/test_cellcell.py
git commit -m "feat(cellcell): cell–cell coupling pattern — two cells, one shared nutrient, viability negotiation (compete vs cross-feed, law 4)"
```

### Task 1B: Disintegration dynamics — a playable level-shift composite

The disintegration study must *show* disintegration when played in the Composite Explorer/loom: as you step through it, the thermal environment leaves the viable band, viability collapses, cell-level metabolism halts, and biomass turns into molecular debris (the cell→molecular transition, Fig 6a). `wholecell.py` already implements every handler for this (`ThermalEnvironment`, `Uptake`, `ViabilityGatedMetabolism`, `ViabilityMonitor`, `DisintegrationEvent`); this task extracts a **focused** composite (no division/daughters) with a RAM emitter so the trajectory is visible frame-by-frame. Labeled honestly as assembled in the figures' style (like the whole-cell capstone), not compiler-emitted — its role is the *playable dynamics* that complement Task 6's compiled grain-swap.

**Files:**
- Modify: `meta_modelers_guide/wholecell.py` (add `build_disintegration()`)
- Create: `scripts/build_disintegration.py`
- Create: `meta_modelers_guide/composites/fig06-disintegration-dynamics.composite.json` (generated)
- Test: `tests/test_disintegration_dynamics.py`

**Interfaces:**
- Consumes: the existing `wholecell.py` handlers (`ThermalEnvironment`, `Uptake`, `ViabilityGatedMetabolism`, `ViabilityMonitor`, `DisintegrationEvent`), `build_core`.
- Produces: `meta_modelers_guide.wholecell.build_disintegration(emit=True) -> dict`; composite stem `fig06-disintegration-dynamics`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_disintegration_dynamics.py`:

```python
"""The disintegration composite, when played, SHOWS disintegration: the thermal
environment leaves the viable band, viability collapses below the floor, and
biomass turns into molecular debris (the cell→molecular level shift, Fig 6a)."""
from __future__ import annotations

from process_bigraph import Composite

from meta_modelers_guide.core import build_core
from meta_modelers_guide.wholecell import build_disintegration


def test_playing_the_composite_shows_disintegration():
    core = build_core()
    comp = Composite(build_disintegration(emit=False), core=core)
    v0 = comp.state["cell"]["viability"]
    comp.run(20)
    v_end = comp.state["cell"]["viability"]
    debris = comp.state["cell"]["debris"]
    biomass = comp.state["cell"]["biomass"]
    assert v0 > 0.9, "starts viable"
    assert v_end < 0.3, f"viability should collapse past the floor, got {v_end}"
    assert debris > 0.0, f"biomass should disintegrate into molecular debris, got {debris}"
    assert biomass >= 0.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=~/code/meta-modelers-guide--paper-aligned pytest tests/test_disintegration_dynamics.py -v`
Expected: FAIL — `build_disintegration` does not exist.

- [ ] **Step 3: Add `build_disintegration()` to `wholecell.py`**

Append to `meta_modelers_guide/wholecell.py` (reuses the module's `proc` pattern; drops division/daughters; processes use `interval=1.0` and a `shock_time=8.0` so disintegration is clearly visible within a ~20-step play; `viability_floor=0.5`):

```python
def build_disintegration(emit: bool = True) -> dict:
    """A FOCUSED, PLAYABLE disintegration composite (Fig 6a): thermal shock →
    viability collapse → cell-level metabolism halts → biomass decays into molecular
    debris. No division — the trajectory reads as the pure cell→molecular level
    shift. Assembled in the figures' style (like build_whole_cell), not compiler-
    emitted; its RAM emitter makes the collapse visible frame-by-frame in the loom.
    """
    def proc(address, inputs, outputs, config=None):
        return {"_type": "process", "address": f"local:{address}",
                "config": config or {}, "interval": 1.0,
                "inputs": inputs, "outputs": outputs}

    state: dict = {
        "environment": {
            "nutrients": {"_type": "concentration", "_default": 1.0},
            "temperature": {"_type": "temperature", "_default": 37.0},
        },
        "cell": {
            "biomass": {"_type": "mass", "_default": 0.3},
            "energy": {"_type": "energy", "_default": 0.0},
            "viability": {"_type": "viability", "_default": 1.0},
            "nutrients_local": {"_type": "concentration", "_default": 0.0},
            "dividing": {"_type": "fraction", "_default": 0.0},
            "disintegrating": {"_type": "fraction", "_default": 0.0},
            "debris": {"_type": "concentration", "_default": 0.0},
        },
        "thermal": proc("ThermalEnvironment", {},
                        {"temperature": ["environment", "temperature"]},
                        {"temp_normal": 37.0, "temp_shock": 50.0, "shock_time": 8.0}),
        "uptake": proc("Uptake",
                       {"nutrients_ext": ["environment", "nutrients"]},
                       {"nutrients_local": ["cell", "nutrients_local"]},
                       {"uptake_rate": 0.5}),
        "metabolism": proc("ViabilityGatedMetabolism",
                           {"nutrients_local": ["cell", "nutrients_local"],
                            "viability": ["cell", "viability"]},
                           {"biomass": ["cell", "biomass"], "energy": ["cell", "energy"],
                            "nutrients_local": ["cell", "nutrients_local"]},
                           {"mode": "coarse", "k": 0.6, "energy_yield": 0.4}),
        "monitor": proc("ViabilityMonitor",
                        {"temperature": ["environment", "temperature"],
                         "biomass": ["cell", "biomass"], "viability": ["cell", "viability"]},
                        {"viability": ["cell", "viability"],
                         "dividing": ["cell", "dividing"],
                         "disintegrating": ["cell", "disintegrating"]},
                        {"temp_opt": 37.0, "temp_tol": 5.0, "relax": 0.5,
                         "division_threshold": 1e9, "viability_floor": 0.5}),
        "disintegration": proc("DisintegrationEvent",
                               {"biomass": ["cell", "biomass"],
                                "disintegrating": ["cell", "disintegrating"]},
                               {"biomass": ["cell", "biomass"], "debris": ["cell", "debris"]},
                               {"decay_rate": 0.4}),
    }
    if emit:
        state["emitter"] = {
            "_type": "step", "address": "local:RAMEmitter",
            "config": {"emit": {"biomass": "mass", "viability": "viability",
                                "temperature": "temperature", "debris": "concentration",
                                "disintegrating": "fraction", "time": "float"}},
            "inputs": {"biomass": ["cell", "biomass"], "viability": ["cell", "viability"],
                       "temperature": ["environment", "temperature"],
                       "debris": ["cell", "debris"],
                       "disintegrating": ["cell", "disintegrating"],
                       "time": ["global_time"]},
        }
    return {"state": state}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `PYTHONPATH=~/code/meta-modelers-guide--paper-aligned pytest tests/test_disintegration_dynamics.py -v`
Expected: PASS. If viability doesn't collapse in 20 steps, lower `shock_time` or raise `viability_floor`; if the `DisintegrationEvent` never fires, confirm the `disintegrating` flag path (`ViabilityMonitor` sets it when `v_next < viability_floor`).

- [ ] **Step 5: Create `scripts/build_disintegration.py`**

```python
#!/usr/bin/env python
"""Serialize the playable disintegration composite (build_disintegration) to
composites/fig06-disintegration-dynamics.composite.json — discoverable by the
workbench and playable via /viva-explore (the Composite Explorer / loom)."""
from __future__ import annotations

import json
from pathlib import Path

from meta_modelers_guide.wholecell import build_disintegration

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "meta_modelers_guide" / "composites" / "fig06-disintegration-dynamics.composite.json"


def main() -> None:
    doc = {
        "name": "Disintegration (playable)",
        "description": ("Fig 6a — cell disintegration as a PLAYABLE trajectory: a "
                        "thermal shock pushes the cell past its viability bound; "
                        "viability collapses, viability-gated metabolism halts, and "
                        "biomass decays into molecular debris (cell→molecular level "
                        "shift). Assembled in the figures' style (see wholecell.py), "
                        "not compiler-emitted. Play it to watch the collapse."),
        "requires": {"processes": ["ThermalEnvironment", "Uptake",
                                    "ViabilityGatedMetabolism", "ViabilityMonitor",
                                    "DisintegrationEvent"]},
        "state": build_disintegration(emit=True)["state"],
    }
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    print("built", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Generate the composite and confirm it plays**

Run:
```bash
PYTHONPATH=~/code/meta-modelers-guide--paper-aligned python scripts/build_disintegration.py
PYTHONPATH=~/code/meta-modelers-guide--paper-aligned python scripts/viva-run-check.py 2>/dev/null || \
  PYTHONPATH=~/code/meta-modelers-guide--paper-aligned python -c "import json,meta_modelers_guide.core as c; from process_bigraph import Composite; s=json.load(open('meta_modelers_guide/composites/fig06-disintegration-dynamics.composite.json')); Composite(s, core=c.build_core()).run(20); print('plays OK')"
```
Expected: composite written; a 20-step run completes ("plays OK"). Later, in Task 14, verify visually with `/viva-explore fig06-disintegration-dynamics` (Composite Explorer play) — viability curve drops, debris rises.

- [ ] **Step 7: Commit**

```bash
cd ~/code/meta-modelers-guide--paper-aligned
git add meta_modelers_guide/wholecell.py scripts/build_disintegration.py \
        meta_modelers_guide/composites/fig06-disintegration-dynamics.composite.json \
        tests/test_disintegration_dynamics.py
git commit -m "feat(disintegration): playable Fig 6a level-shift composite — thermal shock → viability collapse → biomass to debris (loom-visible)"
```

---

## Phase B — Re-author the study layer 6 → 9 (via `/viva-study`)

**Precondition for all Phase B tasks:** `/viva-workbench start` (workbench up). Each task ends by running `PYTHONPATH=~/code/meta-modelers-guide--paper-aligned python scripts/lint-workspace.py` and confirming no errors for the touched study, then a commit. Use `/viva-study` for the writes (canonicalization + provenance); do not hand-edit `study.yaml`. Content below is the material to author — figure citation, question, claim, baseline composite ids (package-qualified), law home, caveats. Detailed multi-section prose is expanded by `/viva-study` + `/viva-biology-forward` during authoring.

### Task 2: Retire `gallery` and `the-living-atlas` as standalone studies

**Files:**
- Remove: `workspace/studies/gallery/`, `workspace/studies/the-living-atlas/`
- Note for Task 12: capture their salvage — the whole-cell capstone prose (`the-living-atlas`) → investigation capstone; the 12-executable coverage claim (`gallery`) → an investigation-level coverage note.

- [ ] **Step 1:** Copy the `biological_summary`/`conclusion` text from both `study.yaml` files into a scratch note (`/private/tmp/…/scratchpad/salvage.md`) for reuse in Task 12.
- [ ] **Step 2:** Remove the two study dirs: `git rm -r workspace/studies/gallery workspace/studies/the-living-atlas`.
- [ ] **Step 3:** Run `PYTHONPATH=… python scripts/lint-workspace.py`. Expected: no dangling references to the removed studies except in `investigation.yaml` (fixed in Task 12) — note any it reports.
- [ ] **Step 4:** Commit: `git commit -m "refactor(studies): retire gallery + the-living-atlas as standalone studies (become investigation-level capstone + coverage note)"`.

### Task 3: `cellular-interface` (Fig 4) — home of Law 1 + impostor

**Files:** rename `workspace/studies/typed-interface/` → author `workspace/studies/cellular-interface/` (Fig 4 half only).

**Content to author (`/viva-study`):**
- **title:** The Cellular Interface
- **figure:** Fig 4 (`cellular_interface.pdf`)
- **baseline:** `meta_modelers_guide.composites.fig04a-interaction-modalities`, `meta_modelers_guide.composites.fig04b-cellular-interface`, `meta_modelers_guide.composites.fig04b-executable`
- **question:** Can the cellular boundary be specified as nothing but typed, unit-bearing exchange ports (chemical mol·s⁻¹, mechanical N, electrical C·s⁻¹, thermal J·s⁻¹) plus higher-level variables (growth, shape, objective, **viability**) — with no committed mechanism — and compiled, by installing one conforming handler, into a bounded, goal-directed cell whose interface is exactly the one declared?
- **claim:** The cell's interface is authored as an inert typed contract and compiled to a running bounded cell; a non-conforming handler that breaks the port contract is rejected at compile time with a `CompileError` naming the missing ports (**Law 1 conformance**).
- **law home:** Law 1 (conformance) + the impostor `NonConformingMetabolism` → `CompileError`. Reference `tests/test_fba.py::test_impostor_handler_rejected_by_compiler` and note the impostor breaks a *cell interface* contract (renames/drops ports), not a fabricated metabolism figure.
- **caveats:** conformance is STRUCTURAL (port names/types/wiring), not units/dimensions/behavior; ports are unit-labeled but units are name-only.

- [ ] **Step 1:** With the workbench up, author the study via `/viva-study` with the fields above; slug `cellular-interface`.
- [ ] **Step 2:** Remove the old `typed-interface` dir if `/viva-study` created a fresh one (`git rm -r workspace/studies/typed-interface` — its Fig 5 content moves to Task 4).
- [ ] **Step 3:** Run `PYTHONPATH=… python scripts/lint-workspace.py`; confirm `cellular-interface` resolves and its baseline composites exist.
- [ ] **Step 4:** Commit: `git commit -m "studies: cellular-interface (Fig 4) + Law 1/impostor home"`.

### Task 4: `cell-environment-coupling` (Fig 5)

**Content:**
- **title:** Cell–Environment Coupling
- **figure:** Fig 5 (`cell_environment.pdf`)
- **baseline:** `meta_modelers_guide.composites.fig05-cell-environment`, `meta_modelers_guide.composites.fig05-executable`
- **question:** Does the cellular interface become a genuine sense/act loop when the environment is a real diffusing spatial field the cell reads and acts back on?
- **claim:** Compiling the Fig 5 draft installs a real Laplacian-diffusion field + single-cell uptake; the cell depletes nutrient locally, diffusion refills it, and the cell reshapes the very gradient it depends on (niche construction) — interface preserved (**Law 2**).
- **caveats:** toy-real constants; niche construction shown as pattern.

- [ ] **Step 1:** Author via `/viva-study`, slug `cell-environment-coupling`, fields above.
- [ ] **Step 2:** Lint; confirm resolves.
- [ ] **Step 3:** Commit: `git commit -m "studies: cell-environment-coupling (Fig 5)"`.

### Task 5: `cell-cell-coupling` (new composite from Task 1)

**Content:**
- **title:** Cell–Cell Coupling
- **figure:** none (paper §Cell–cell coupling; biofilm/collective nesting is study 9)
- **baseline:** `meta_modelers_guide.composites.cellcell-coupling`, `meta_modelers_guide.composites.cellcell-executable-compete`, `meta_modelers_guide.composites.cellcell-executable-crossfeed`
- **question:** When two cell interfaces are coupled through one shared environmental store, what is coupled is not only state but constraint — does one cell's uptake push the other outside its viable bounds (competition), and can a different handler over the same coupling interface stabilize both (cross-feeding)?
- **claim:** Two cells over one shared-nutrient interface negotiate viability: under competition the weaker cell (lower uptake capacity) starves below its viable band while the stronger persists; under cross-feeding both stay viable — two handler environments over one coupling interface (**Law 4**).
- **caveats:** pairwise, toy-real; population-scale negotiation not modeled.

- [ ] **Step 1:** Author via `/viva-study`, slug `cell-cell-coupling`, fields above; cite `tests/test_cellcell.py`.
- [ ] **Step 2:** Lint; confirm baseline composites (from Task 1) resolve.
- [ ] **Step 3:** Commit: `git commit -m "studies: cell-cell-coupling (viability negotiation, law 4)"`.

### Task 6: `disintegration` (Fig 6) — home of Law 4 (grain-swap) + the three metabolisms

**Content:**
- **title:** Disintegration
- **figure:** Fig 6 (`disintegration.pdf`)
- **baseline (headline first):** `meta_modelers_guide.composites.fig06-disintegration-dynamics` (the **playable** level-shift, Task 1B), then `meta_modelers_guide.composites.fig06-disintegration`, `meta_modelers_guide.composites.fig06-executable-coarse`, `meta_modelers_guide.composites.fig06-executable-kinetic`, `meta_modelers_guide.composites.fig06-executable-fba`
- **question:** When viability bounds are crossed the appropriate level of description shifts from a cellular process to interacting molecular components. (a) Played through, does the disintegration composite actually *show* this shift — viability collapsing and biomass turning into molecular debris? (b) And is one metabolic exchange interface realizable at a coarse cell-level grain, an intermediate kinetic grain, and a resolved molecular-network grain (real COBRApy FBA), with coarse-graining the reverse move?
- **claim:** Disintegration is a change in level of description made executable and **watchable**: playing `fig06-disintegration-dynamics` in the Composite Explorer, a thermal shock pushes the cell past its viability bound, viability collapses, viability-gated metabolism halts, and biomass decays into molecular debris (Fig 6a). The same interface's cell↔molecular-network equivalence carries a coarse lumped yield, a saturating kinetic law, and **real COBRApy flux-balance on `e_coli_core`** (the resolved molecular network, overflowing carbon to acetate) — three grains behind ports that never move (Fig 6b, **Law 4**, `test_fig6_handler_independence`).
- **law home:** Law 4 primary. Home of the three metabolisms (moved from the retired `one-interface-three-mechanisms`).
- **how to view:** note in the study that a reader should run `/viva-explore fig06-disintegration-dynamics` and step through it to watch the viability curve collapse and debris rise.
- **falsifiability:** overturned if, played through, viability never leaves the viable band / never collapses, or biomass never converts to debris (no level shift), or the three grains fail to share one interface.
- **caveats:** the playable dynamics composite is assembled in the figures' style (`wholecell.py`), not compiler-emitted (same honesty as the capstone); its thermal shock is scripted (hard-coded onset), not emergent; FBA requires optional `cobra` (guarded skip); grain equivalence is structural, not a fitted reduction.

- [ ] **Step 1:** Author via `/viva-study`, slug `disintegration`, fields above; cite `tests/test_disintegration_dynamics.py`, `tests/test_compilation.py::test_fig6_handler_independence`, and `tests/test_fba.py`. Record the playable composite as the headline baseline and add a `behavior_tests`/`falsifiability` entry for the viability-collapse trajectory.
- [ ] **Step 2:** Remove the retired `workspace/studies/one-interface-three-mechanisms/` (`git rm -r`).
- [ ] **Step 3:** Lint; confirm resolves and no dangling `one-interface-three-mechanisms` refs remain (outside investigation.yaml).
- [ ] **Step 4:** Commit: `git commit -m "studies: disintegration (Fig 6) — playable level-shift + grain-swap + law 4; retire one-interface-three-mechanisms"`.

### Task 7: `molecular-interfaces` (Fig 7)

**Content:**
- **title:** Molecular Interfaces
- **figure:** Fig 7 (`molecular_interface.pdf`)
- **baseline:** `meta_modelers_guide.composites.fig07-molecular-mechanism`, `meta_modelers_guide.composites.fig07-executable`
- **question:** At the molecular grain, can a single molecular mechanism (F1Fo ATP synthase) be compiled from its draft and run as a PMF-driven rotary catalyst honoring the four physical interface channels (chemical/electrical/mechanical/thermal) and the specialized substrate/cofactor/catalyst/product ports?
- **claim:** The molecular interface's four typed channels + specialized enzymatic ports compile to a running ATP-synthase mechanism — the molecular level the disintegration study drops into, made concrete.
- **caveats:** one mechanism, toy-real kinetics.

- [ ] **Step 1:** Author via `/viva-study`, slug `molecular-interfaces`, fields above.
- [ ] **Step 2:** Lint; confirm resolves.
- [ ] **Step 3:** Commit: `git commit -m "studies: molecular-interfaces (Fig 7)"`.

### Task 8: `biomolecular-complementarity` (Fig 8)

**Content:**
- **title:** Biomolecular Complementarity
- **figure:** Fig 8 (`cell_structure.pdf` / molecular compositions)
- **baseline:** `meta_modelers_guide.composites.fig08-nested-hierarchy`, `meta_modelers_guide.composites.fig08-executable`
- **question:** Do molecular mechanisms compose into nested hierarchical composites (proteins → complexes → organelles → ECM) whose interfaces survive deep nesting, and does a gene-expression cascade wired to the deepest leaves preserve every interface across six levels (**Law 2** at the deepest nesting)?
- **claim:** The six-level nested place graph compiles with a coupled transcription→translation→assembly cascade wired to its deepest stores; the interface is preserved through the deepest nesting.
- **caveats:** complementarity/selectivity (which partners bind) is narrated as the organizing principle but the executable demonstrates hierarchical assembly, not fitted binding selectivity — noted honestly.
- **note:** Task 6 of the old `the-nested-cell` study split: Fig 7 → Task 7, Fig 8 → here. Remove `workspace/studies/the-nested-cell/` after both are authored.

- [ ] **Step 1:** Author via `/viva-study`, slug `biomolecular-complementarity`, fields above.
- [ ] **Step 2:** Remove `workspace/studies/the-nested-cell/` (`git rm -r`) now that Fig 7 + Fig 8 are split out.
- [ ] **Step 3:** Lint; confirm both new studies resolve and no dangling `the-nested-cell` refs (outside investigation.yaml).
- [ ] **Step 4:** Commit: `git commit -m "studies: biomolecular-complementarity (Fig 8); retire the-nested-cell (split into Fig 7 + Fig 8)"`.

### Task 9: `autopoiesis` (Fig 9) — second home of Law 4

**Content:**
- **title:** Autopoiesis — Composition of the Cellular Interface
- **figure:** Fig 9 (`self_organized_process.pdf`)
- **baseline:** `meta_modelers_guide.composites.fig09a-coarse-graining`, `meta_modelers_guide.composites.fig09a-executable`, `meta_modelers_guide.composites.fig09b-minimal-cell`, `meta_modelers_guide.composites.fig09b-executable`
- **question:** How does a maintained cellular interface arise from molecular processes? Do metabolism, containment, and replication, mutually wired so each maintains the others, compile into a self-sustaining minimal cell — and does each self-organized function run at coarse, self-organized, and molecular grains behind one interface (**Law 4**)?
- **claim:** The three closure processes compile into a minimal cell whose interface is produced by the coupling itself; each function is realized at three grains behind a fixed interface — the grain-swap in its second home.
- **caveats (honest):** this illustrates the Maturana–Varela closure *pattern*, not validated autopoiesis; the loop's self-maintenance is demonstrated qualitatively.
- **note:** promoted from the retired `gallery` (fig09a/09b were deflated there).

- [ ] **Step 1:** Author via `/viva-study`, slug `autopoiesis`, fields above.
- [ ] **Step 2:** Lint; confirm resolves.
- [ ] **Step 3:** Commit: `git commit -m "studies: autopoiesis (Fig 9) — closure pattern + grain-swap (law 4, 2nd home)"`.

### Task 10: `growth-and-division` (Fig 10a,b) — Law 2′

**Content:**
- **title:** Growth and Division
- **figure:** Fig 10a,b (`divide_evolve.pdf`)
- **baseline:** `meta_modelers_guide.composites.fig10-1-division`, `meta_modelers_guide.composites.fig10-1-rewrite`, `meta_modelers_guide.composites.fig10-1-executable`
- **question:** Is division a genuine structural rewrite of the place graph — one cell node becoming two daughters at runtime, fired by the cell's own replicated DNA crossing a threshold — that conserves mass (parent partitioned, not duplicated)?
- **claim:** (reuse the existing `divide` study's verified claim) division is a change to the composition itself, DNA-threshold-gated, one node → two, mass conserved (**Law 2′**, rewrite conformance vs wiring).
- **law home:** Law 2′ primary. Reuse `tests/test_compilation.py::test_fig10_division_is_event_driven`, `tests/test_fig10_rewrite.py`.
- **note:** largely a rename + reframe of the existing strong `divide` study to add the *growth* framing (env-coupled uptake grows the stores that cross the threshold).

- [ ] **Step 1:** Author via `/viva-study`, slug `growth-and-division`, reusing `divide`'s content + growth framing.
- [ ] **Step 2:** Remove `workspace/studies/divide/` (`git rm -r`).
- [ ] **Step 3:** Lint; confirm resolves.
- [ ] **Step 4:** Commit: `git commit -m "studies: growth-and-division (Fig 10a,b, law 2′); rename from divide"`.

### Task 11: `development-and-evolution` (Fig 10c–f) — caveated pattern demos

**Content:**
- **title:** Development and Evolution
- **figure:** Fig 10c–f (`divide_evolve.pdf`)
- **baseline:** `meta_modelers_guide.composites.fig10-2-development`, `meta_modelers_guide.composites.fig10-2-rewrite`, `meta_modelers_guide.composites.fig10-2-executable`, `meta_modelers_guide.composites.fig10-3-evolution`, `meta_modelers_guide.composites.fig10-3-rewrite`, `meta_modelers_guide.composites.fig10-3-executable`
- **question:** Can development (cells nesting into a biofilm collective with its own interface) and evolution (a new interface port expanding interaction, selected by viability) be represented as compositional rewrites?
- **claim:** Development nests individual cells into a collective composite with a shared-ECM interface; evolution adds a new chemical port that switches on — both realized as event-driven rewrites (**Law 2′**).
- **caveats (explicit, per paper line 580 "an open and substantial challenge"):** these are pattern demonstrations, not validated results — selection is an ODE, the "new port" is a config-driven ramp; the biofilm nesting is pre-declared post-structure, not runtime node insertion.
- **note:** promoted from the retired `gallery`; biofilm (Fig 10c,d) lives here, not in `cell-cell-coupling`.

- [ ] **Step 1:** Author via `/viva-study`, slug `development-and-evolution`, fields + explicit caveats above.
- [ ] **Step 2:** Lint; confirm resolves.
- [ ] **Step 3:** Commit: `git commit -m "studies: development-and-evolution (Fig 10c–f) — caveated pattern demos (law 2′)"`.

---

## Phase C — Investigation + docs + integration

### Task 12: Re-author `investigation.yaml`

**Files:** Modify `workspace/investigations/draft-to-living-cell/investigation.yaml` (via `/viva-investigation` where it writes; prose fields may be set through the skill).

- [ ] **Step 1:** Set `studies:` to the 9 slugs in paper order: `cellular-interface, cell-environment-coupling, cell-cell-coupling, disintegration, molecular-interfaces, biomolecular-complementarity, autopoiesis, growth-and-division, development-and-evolution`.
- [ ] **Step 2:** Rewrite `at_a_glance:` — one `{study, role}` per new study, role lines matching the table in the spec (each names its figure + what its executable shows + its law home).
- [ ] **Step 3:** Set `executive.key_figures:` to `cellular-interface, disintegration, growth-and-division` (the impostor/Law-1 exhibit, the three-grain metabolism/Law-4 exhibit, the genuine rewrite/Law-2′ exhibit).
- [ ] **Step 4:** Rewrite `executive.what_is_this` / `executive.verdict` / `lead` / `scientific_argument` to the paper's thesis: interfaces as testable biological hypotheses; **viability & minimal agency the throughline**; composition as ongoing practice (connect / cut open at the interface on failure / coarse-grain on emergence). Remove every "Fig 6 = metabolism thesis" framing; Fig 6 is Disintegration and the three metabolisms are its grains.
- [ ] **Step 5:** Add the **capstone** (from `the-living-atlas` salvage in Task 2): a closing investigation-level synthesis composing several patterns into one running whole cell (coarse/kinetic/FBA behind one interface; grows, divides mass-conserved, dies on a scripted thermal shock) — explicitly labeled hand-assembled (`wholecell.py`), not compiler-emitted.
- [ ] **Step 6:** Add the **coverage note** (from `gallery` salvage): every figure draft compiles to a running executable (now incl. the two cell–cell executables) — as an investigation-level appendix line, not a study.
- [ ] **Step 7:** Update `limitations`, `glossary`, `competing_frameworks` for the new structure; keep the honest caveats (toy-real, structural conformance, hand-assembled capstone, caveated dev/evo).
- [ ] **Step 8:** Run `PYTHONPATH=… python scripts/lint-workspace.py`; fix any dangling study references. Confirm all 9 studies referenced, no references to retired studies.
- [ ] **Step 9:** Commit: `git commit -m "investigation: re-anchor to the paper's arc, 9 studies, viability/agency throughline, capstone + coverage note"`.

### Task 13: Rewrite `README.md` (+ NEXT_STEPS pointer)

**Files:** Modify `README.md`.

- [ ] **Step 1:** Replace the flagship section (currently `README.md:23` "The sharpest single view is **Fig 6 — metabolism**") with the paper's real arc and a correct flagship: the exhibit is now the **three-grain Fig 6 Disintegration** (coarse/kinetic/FBA behind one interface) framed as disintegration/coarse-graining, plus the **impostor rejection** framed against the **cellular interface** (Fig 4), plus the **division rewrite** (Fig 10).
- [ ] **Step 2:** Fix the composite table (`README.md:224`) so `fig06-*` rows read as Disintegration grains, not "metabolism", and add the `cellcell-*` composites.
- [ ] **Step 3:** Update the study list / links to the 9 new slugs in paper order.
- [ ] **Step 4:** Confirm no remaining "Fig 6 — metabolism" / "one interface three mechanisms" flagship phrasing: `grep -n "Fig 6 — metabolism\|One Interface, Three" README.md` returns nothing.
- [ ] **Step 5:** Commit: `git commit -m "docs(readme): re-anchor to the paper's arc; Fig 6 is Disintegration; 9-study index"`.

### Task 14: Integration — rebuild, full suite, lint, report

**Files:** none new; regeneration + verification.

- [ ] **Step 1:** Regenerate ONLY the branch's own composites, and protect baked viz. NOTE (discovered in Task 1): `scripts/build_executables.py` recompiles *every* executable from scratch and silently strips the `dynamics_viz` step baked into fig04b/05/06/07/08/09/10 executables by commit `89f2e95`. Do NOT blanket-commit its output. Procedure: run `PYTHONPATH=~/code/meta-modelers-guide--paper-aligned python scripts/build_executables.py`, then `git -C ~/code/meta-modelers-guide--paper-aligned checkout -- meta_modelers_guide/composites/fig0*-executable*.composite.json meta_modelers_guide/composites/fig10-*-executable.composite.json` to restore the baked-viz figures, keeping only the two `cellcell-executable-*` files new. Then `PYTHONPATH=~/code/meta-modelers-guide--paper-aligned python scripts/build_disintegration.py` (writes only `fig06-disintegration-dynamics.composite.json`). Verify with `git status` that no fig0*/fig10 executable shows a viz-stripping diff before committing.
- [ ] **Step 2:** Full test suite: `PYTHONPATH=~/code/meta-modelers-guide--paper-aligned pytest -v`. Expected: all pass (FBA/cobra tests skip gracefully if `cobra` absent). Fix any regressions.
- [ ] **Step 3:** Workspace lint: `PYTHONPATH=~/code/meta-modelers-guide--paper-aligned python scripts/lint-workspace.py`. Expected: clean; no dangling study/composite references.
- [ ] **Step 4:** Visually confirm the playable disintegration: `/viva-explore fig06-disintegration-dynamics`, step through the play, and confirm the viability curve collapses and debris rises (the requirement: disintegration is *visible* when played). Then run `/viva-report` (workbench up) — the reviewer-readiness audit (Pass A) + structural lint (Pass B), then regenerate the dashboard + investigation report. Resolve any verdict↔chart drift or stale-framing flags it raises.
- [ ] **Step 5:** Commit any regenerated report/dashboard artifacts: `git commit -m "report: regenerate dashboard + draft-to-living-cell report for the 9-study realignment"`.
- [ ] **Step 6:** Final verification statement: confirm (a) 9 study dirs exist and lint clean, (b) `pytest` green, (c) no "Fig 6 = metabolism" flagship anywhere (`grep -rn "Fig 6 — metabolism" README.md workspace/`), (d) investigation references exactly the 9 studies.

---

## Self-Review

**Spec coverage:** every spec section maps to a task — 9 studies (Tasks 3–11), framework-as-primer + capstone + coverage (Task 12), 5-laws homes (Tasks 3/6/9/10/11), cell–cell new science (Task 1), the **playable disintegration** requirement (Task 1B → surfaced in Task 6 as the headline baseline and verified in Task 14 via `/viva-explore`), migration/salvage (Tasks 2,6,8,10 retirements + Task 12 salvage), README fix (Task 13), mechanics/report (Task 14). Complementarity-selectivity was deliberately descoped (YAGNI — Fig 8 is nesting, which exists); Task 8 notes it honestly.

**Placeholder scan:** code steps carry real code; study tasks carry exact composite ids + questions + claims (prose expansion is the `/viva-study` skill's job, called out explicitly, not a hidden TODO).

**Type consistency:** draft names `CellAgent`/`SharedNutrientEnv`, handlers `CompetingCell`/`CrossFeedingCell`/`NutrientPool`, envs `cellcell-compete`/`cellcell-crossfeed`, composite stems `cellcell-coupling`/`cellcell-executable-{compete,crossfeed}` are used consistently across Task 1 and referenced identically in Task 5. The one flagged risk (env↔node keying convention) has an explicit alignment step (Task 1 Step 8).
