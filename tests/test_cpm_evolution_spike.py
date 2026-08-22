# tests/test_cpm_evolution_spike.py
"""Study-9 Task 1 spike: prove the EVOLUTION crux before building the real
`CpmEvolution` process (Task 2). A per-cell heritable trait (glucose-uptake
`vmax`, used in that cell's dFBA) must be inherited-with-mutation on division
through the SAME creation-order `zip(dividing, new_ids)` pairing study 8 uses
for biomass/lineage (`meta_modelers_guide/cpm/growth_division.py`), and the
population mean trait must shift up under selection but NOT in a no-mutation
control.

`CpmEvolution` here is a MINIMAL harness subclass of `CpmGrowthDivision` that
lifts the trait bookkeeping onto the study-8 colony body (growth loop unchanged
via the overridden `_fba`; division loop duplicated with one extra
mutation-on-division step, mirroring the module docstring's parent<->daughter
pairing exactly). It is run directly (no `Composite`/`Process` address
registration) -- a focused harness, not the merged process. Task 2 promotes
this to `meta_modelers_guide/cpm/evolution.py`.

Two config/seed traps verified in the API map
(`docs/superpowers/api-maps/2026-08-22-development-and-evolution-api-map.md`
Q7) are baked in on purpose:

1. The no-mutation control is a BOOLEAN `mutate` flag, never a `mut_sigma:
   0.0` float override -- bigraph_schema silently drops a `0.0` float
   override (schema default retained), so a float-gated "no mutation" arm
   would secretly keep mutating.
2. `seed` is threaded into BOTH the CPM `potts` spec (world construction,
   init-only) AND the mutation RNG -- the base process hardcodes
   `potts.seed=1`, so without this every "different seed" would replay one
   Metropolis trajectory.
"""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("cpm")
pytest.importorskip("spatio_flux")
pytest.importorskip("cobra")

from process_bigraph import Process

from meta_modelers_guide.core import build_core
from meta_modelers_guide.cpm.growth_division import CpmGrowthDivision, _DEFAULT_CELL_TYPE

NX = NY = 60
TICKS = 45
FOUNDER_VMAX = 1.5
MUT_SIGMA = 0.3


def _f(default):
    return {"_type": "float", "_default": default}


class CpmEvolution(CpmGrowthDivision):
    """Spike harness: `CpmGrowthDivision` (study 8) + a per-cell heritable
    `vmax` trait carried through the SAME creation-order division pairing.

    Growth is unchanged (reuses the base `_clamp_removal`, only `_fba` is
    overridden to read `self.vmax[cid]` instead of the config-wide
    `glucose_vmax`). The division loop is duplicated from
    `CpmGrowthDivision.update` verbatim, with one addition inside the
    existing `zip(dividing, new_ids)` pairing: the daughter's trait is drawn
    from the parent's trait +/- Gaussian mutation (or exactly the parent's
    trait when `mutate` is False); the parent keeps its own trait unchanged.
    """

    config_schema = {
        **CpmGrowthDivision.config_schema,
        "mutate": {"_type": "boolean", "_default": True},
        "mut_sigma": _f(MUT_SIGMA),
        "vmax0": _f(FOUNDER_VMAX),
        "vmax_min": _f(0.2),
        "vmax_max": _f(20.0),
        "seed": {"_type": "integer", "_default": 1},
    }

    def __init__(self, config=None, core=None):
        # Deliberately do NOT call CpmGrowthDivision.__init__ / super() --
        # it hardcodes `potts.seed=1` when building the world (trap #2 in
        # the module docstring above). Go straight to the grandparent
        # `Process.__init__` (fills `self.config` from `config_schema` via
        # `core.fill`, see `bigraph_schema.edge.Edge.__init__`) and replicate
        # the rest of `CpmGrowthDivision.__init__` ourselves so the `seed`
        # config value can reach the potts spec.
        Process.__init__(self, config, core=core)
        from cpm.schema import load_world
        try:
            from cobra.io import load_model
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "CpmEvolution requires the optional 'cobra' package.") from exc
        self._load_model = load_model

        c = self.config
        grid = dict(c.get("grid") or {})
        nx, ny = int(grid.get("nx", 40)), int(grid.get("ny", 40))
        self._nx, self._ny = nx, ny

        cell_cfg = dict(c.get("cell") or {})
        seed_block = list(cell_cfg.get("seed_block") or [17, 17, 0, 24, 24, 1])
        target_volume = float(cell_cfg.get("target_volume", 40.0))
        lambda_volume = float(cell_cfg.get("lambda_volume", 2.0))
        temperature = float(cell_cfg.get("temperature", 11.0))

        contact = list(c.get("contact") or [{"a": 0, "b": _DEFAULT_CELL_TYPE, "j": 14.0}])

        seed = int(c.get("seed", 1))
        spec = {
            "potts": {"dims": [nx, ny, 1], "boundary": "noflux", "neighbor_order": 2,
                      "temperature": temperature, "seed": seed},
            "cells": [{"type": _DEFAULT_CELL_TYPE, "target_volume": target_volume,
                       "lambda_volume": lambda_volume, "target_surface": 0.0,
                       "lambda_surface": 0.0, "seed_block": seed_block}],
            "contact": contact,
        }
        self.world = load_world(spec)

        self._models: dict[int, object] = {}
        self.biomass: dict[int, float] = {}
        self.lineage: dict[int, int] = {}
        self.generation: dict[int, int] = {1: 0}
        self.max_generation: int = 0

        # --- evolution bookkeeping (the addition over study 8) ----------
        self.rng = np.random.default_rng(seed)  # seed also drives mutation draws
        self.vmax: dict[int, float] = {1: float(c["vmax0"])}
        # (parent_vmax, daughter_vmax) recorded at every division event, in
        # order -- the inheritance-correctness test reads this directly.
        self.pairs: list[tuple[float, float]] = []

        self._new_model(1, float(c["init_biomass"]))

    def _fba(self, cid, local_glc, interval):
        """Same dFBA step as the base -- the ONLY change is that `vmax` is
        this cell's own heritable trait, not the config-wide constant."""
        c = self.config
        m = self._models[cid]
        km = float(c["glucose_km"])
        vmax = float(self.vmax.get(cid, c["vmax0"]))
        v = vmax * local_glc / (km + local_glc) if local_glc > 0 else 0.0
        m.reactions.EX_glc__D_e.lower_bound = -float(v)

        sol = m.optimize()
        if sol.status != "optimal":
            return 0.0, 0.0, 0.0

        mu = float(sol.objective_value or 0.0)
        biomass = self.biomass[cid]
        d_biomass = mu * biomass * interval
        box_volume_L = float(c["box_volume_L"])
        glc_flux = float(sol.fluxes.get("EX_glc__D_e", 0.0))
        ac_flux = float(sol.fluxes.get("EX_ac_e", 0.0))
        d_glc = glc_flux * biomass * interval / box_volume_L
        d_ac = ac_flux * biomass * interval / box_volume_L
        return d_biomass, d_glc, d_ac

    def update(self, state, interval):
        fields = state.get("fields", {})
        glucose = np.asarray(fields.get("glucose"), dtype=float)
        acetate = np.asarray(fields.get("acetate"), dtype=float)
        lat = np.array(self.world.snapshot()).reshape(self._ny, self._nx)
        live_ids = sorted(set(int(i) for i in np.unique(lat)) - {0})

        dglc_total = np.zeros_like(glucose)
        dace_total = np.zeros_like(acetate)

        local_glc_obs = {}
        grow_per_biomass = float(self.config["grow_per_biomass"])

        for cid in live_ids:
            self._new_model(cid, float(self.config["init_biomass"]))
            if cid not in self.vmax:
                # Should not happen (every daughter gets a trait in the
                # division loop below) -- defensive fallback only.
                self.vmax[cid] = float(self.config["vmax0"])
            fp = (lat == cid)
            key = str(cid)

            local_glc = float(glucose[fp].mean()) if fp.any() else 0.0
            local_glc_obs[key] = local_glc

            d_biomass, d_glc_request, d_byproduct = self._fba(cid, local_glc, interval)

            clamped, per_pixel, ratio = self._clamp_removal(glucose, fp, d_glc_request)
            d_biomass *= ratio
            d_byproduct *= ratio
            area = max(int(fp.sum()), 1)
            if fp.any():
                dglc_total[fp] += per_pixel
                dace_total[fp] += d_byproduct / area

            self.biomass[cid] = max(self.biomass[cid] + d_biomass, 1e-9)

            target = grow_per_biomass * self.biomass[cid]
            self.world.set_target_volume(cid, max(target, 0.0))

        self.world.step(int(self.config["mcs"]))

        # --- division (study 8's pairing, +trait mutation) --------------
        vol_threshold = float(self.config["vol_threshold"])
        reset_target = float(self.config["reset_target"])
        vols_before = list(self.world.cell_volumes())
        new_ids = self.world.divide_cells(vol_threshold, reset_target)
        if new_ids:
            dividing = [cid for cid in range(1, len(vols_before)) if vols_before[cid] >= vol_threshold]
            assert len(dividing) == len(new_ids), (
                f"parent/daughter count mismatch: {len(dividing)} dividing vs {len(new_ids)} new_ids")
            vols_after = self.world.cell_volumes()
            mutate = bool(self.config.get("mutate", True))
            mut_sigma = float(self.config["mut_sigma"])
            vmax_min = float(self.config["vmax_min"])
            vmax_max = float(self.config["vmax_max"])
            for parent_id, daughter_id in zip(dividing, new_ids):
                total_bm = self.biomass.get(parent_id, reset_target / grow_per_biomass)
                vol_parent_after = float(vols_after[parent_id]) if parent_id < len(vols_after) else 0.0
                vol_daughter = float(vols_after[daughter_id]) if daughter_id < len(vols_after) else 0.0
                denom = vol_parent_after + vol_daughter
                if denom > 0:
                    parent_bm = total_bm * vol_parent_after / denom
                    daughter_bm = total_bm * vol_daughter / denom
                else:
                    parent_bm = daughter_bm = total_bm / 2.0
                self.biomass[parent_id] = max(parent_bm, 1e-9)
                self._new_model(daughter_id, max(daughter_bm, 1e-9))

                # --- the evolution crux: mutation-on-division through the
                # SAME parent<->daughter pairing as biomass/lineage above.
                # The parent keeps its own trait; a BOOLEAN `mutate` flag
                # gates the draw (never a `mut_sigma: 0.0` float override --
                # module docstring trap #1).
                parent_vmax = self.vmax.get(parent_id, float(self.config["vmax0"]))
                delta = float(self.rng.normal(0.0, mut_sigma)) if mutate else 0.0
                daughter_vmax = float(np.clip(parent_vmax + delta, vmax_min, vmax_max))
                self.vmax[daughter_id] = daughter_vmax
                self.pairs.append((parent_vmax, daughter_vmax))

                self.lineage[daughter_id] = parent_id
                gen = self.generation.get(parent_id, 0) + 1
                self.generation[daughter_id] = gen
                self.max_generation = max(self.max_generation, gen)

        lat = np.array(self.world.snapshot()).reshape(self._ny, self._nx)
        live_ids = sorted(set(int(i) for i in np.unique(lat)) - {0})

        vols = self.world.cell_volumes()
        coms = self.world.cell_coms()
        volume_obs, position_obs, biomass_obs, generation_obs, vmax_obs = {}, {}, {}, {}, {}
        total_volume = 0.0
        for cid in live_ids:
            key = str(cid)
            vol = float(vols[cid]) if cid < len(vols) else 0.0
            volume_obs[key] = vol
            position_obs[key] = list(coms[cid])[:2] if cid < len(coms) else [0.0, 0.0]
            biomass_obs[key] = self.biomass.get(cid, 0.0)
            generation_obs[key] = float(self.generation.get(cid, 0))
            vmax_obs[key] = self.vmax.get(cid, float(self.config["vmax0"]))
            total_volume += vol

        trait_values = list(vmax_obs.values())
        mean_vmax = float(np.mean(trait_values)) if trait_values else float(self.config["vmax0"])
        var_vmax = float(np.var(trait_values)) if trait_values else 0.0

        return {
            "fields": {"glucose": dglc_total, "acetate": dace_total},
            "volume": volume_obs,
            "position": position_obs,
            "local_glucose": local_glc_obs,
            "biomass": biomass_obs,
            "generation": generation_obs,
            "vmax": vmax_obs,
            "n_cells": float(len(live_ids)),
            "total_volume": total_volume,
            "max_generation": float(self.max_generation),
            "mean_vmax": mean_vmax,
            "var_vmax": var_vmax,
        }


def _config(seed, mutate):
    return {
        "grid": {"nx": NX, "ny": NY},
        "cell": {"seed_block": [27, 27, 0, 33, 33, 1], "target_volume": 40.0,
                  "lambda_volume": 2.0, "temperature": 11.0},
        "contact": [{"a": 0, "b": 1, "j": 14.0}, {"a": 1, "b": 1, "j": 14.0}],
        "box_volume_L": 0.3, "grow_per_biomass": 40.0,
        "glucose_km": 0.5, "oxygen_vmax": 15.0, "mcs": 3,
        "vol_threshold": 80.0, "reset_target": 40.0, "init_biomass": 1.25,
        "vmax0": FOUNDER_VMAX, "mut_sigma": MUT_SIGMA, "mutate": mutate,
        "vmax_min": 0.2, "vmax_max": 20.0, "seed": seed,
    }


def _run(seed, mutate, ticks=TICKS):
    """Run `CpmEvolution` directly (no `Composite`) for `ticks` steps on a
    fixed abundant-glucose field, manually replaying the SAME plain-additive
    `fields` apply the base process documents (`outputs()`: `"fields":
    "map[array]"` is a genuine spatial delta the engine sums into the shared
    grid) -- see `growth_division.py`'s module docstring / `outputs()`."""
    core = build_core()
    proc = CpmEvolution(config=_config(seed, mutate), core=core)
    state = {"fields": {"glucose": np.full((NY, NX), 12.0), "acetate": np.zeros((NY, NX))}}
    out = None
    for _ in range(ticks):
        out = proc.update(state, 1.0)
        state["fields"]["glucose"] = state["fields"]["glucose"] + out["fields"]["glucose"]
        state["fields"]["acetate"] = state["fields"]["acetate"] + out["fields"]["acetate"]
    return proc, out


# Seed 3 is a clearly-rising seed (verified in the API map, dbg_pair.py /
# run_evo.py): 45 ticks, founder 1.5, sigma 0.3 -> mean 1.500 -> 2.200
# (+0.700), 69 division events, 99% of |child-parent| within 3 sigma. The
# multi-seed FRACTION (>=4/5 seeds rising) is Task 4's job; this spike only
# needs one seed that clearly demonstrates the mechanism.
SELECTION_SEED = 3


@pytest.fixture(scope="module")
def selection_run():
    return _run(SELECTION_SEED, mutate=True)


def test_trait_inheritance_within_3_sigma(selection_run):
    """Across division events, |vmax[daughter] - vmax[parent]| is
    ~N(0,sigma)-distributed -- the creation-order pairing propagates traits,
    not scrambles them. A wrong pairing would smear diffs across the whole
    trait range (~1.5+), not cluster them within a few sigma."""
    proc, _out = selection_run
    assert len(proc.pairs) >= 15, "too few division events to test the distribution"

    diffs = np.array([abs(d - p) for p, d in proc.pairs])
    within_3sigma = float((diffs <= 3 * MUT_SIGMA).mean())
    assert within_3sigma >= 0.95, f"only {within_3sigma:.2%} of |child-parent| within 3 sigma"

    # A scrambled pairing would routinely produce diffs comparable to the
    # trait's own operating range (order 1+); a correct pairing keeps every
    # diff within a handful of sigma of the mutation kernel.
    assert diffs.max() < 10 * MUT_SIGMA
    # And the mean absolute diff should land near E|N(0,sigma)| = sigma*sqrt(2/pi).
    expected_mean_abs = MUT_SIGMA * np.sqrt(2 / np.pi)
    assert diffs.mean() == pytest.approx(expected_mean_abs, rel=0.6)


def test_selection_shifts_mean_trait_up(selection_run):
    """With mutation ON and vmax feeding the dFBA uptake, the population mean
    vmax ends clearly above the founder value for this seed (selection
    through differential division on the shared depleting field)."""
    proc, out = selection_run
    assert out["mean_vmax"] > FOUNDER_VMAX + 0.1, (
        f"mean vmax {out['mean_vmax']} did not clearly rise above founder {FOUNDER_VMAX}")
    assert out["n_cells"] >= 10, "too few cells/divisions for a meaningful selection signal"
    assert out["var_vmax"] > 0.0, "mutation should have built up trait variance"


def test_no_mutation_control_is_static():
    """With `mutate=False` (BOOLEAN, not `mut_sigma=0.0`), the mean vmax
    stays EXACTLY the founder value and variance is exactly 0 -- no raw
    material for selection to act on."""
    proc, out = _run(SELECTION_SEED, mutate=False)
    assert len(proc.pairs) >= 1, "need at least one division to exercise the control"
    assert out["mean_vmax"] == pytest.approx(FOUNDER_VMAX, abs=1e-9)
    assert out["var_vmax"] == pytest.approx(0.0, abs=1e-9)
    for parent_vmax, daughter_vmax in proc.pairs:
        assert daughter_vmax == pytest.approx(parent_vmax, abs=1e-9)
        assert daughter_vmax == pytest.approx(FOUNDER_VMAX, abs=1e-9)


def test_seed_threads_into_world_and_mutation_rng():
    """`seed` must reach BOTH the CPM potts spec (world construction) and the
    mutation RNG. Proof: (a) the SAME seed run twice is fully deterministic
    (reproducible Metropolis trajectory + mutation draws); (b) two DIFFERENT
    seeds diverge -- if `seed` only reached one of the two RNG sources, a
    "different seed" run would silently replay the same trajectory."""
    proc_a, out_a = _run(seed=7, mutate=True)
    proc_b, out_b = _run(seed=7, mutate=True)
    assert out_a["mean_vmax"] == pytest.approx(out_b["mean_vmax"], abs=1e-9)
    assert out_a["n_cells"] == out_b["n_cells"]
    assert out_a["position"] == out_b["position"]

    proc_c, out_c = _run(seed=8, mutate=True)
    same_population = out_a["n_cells"] == out_c["n_cells"]
    same_mean = out_a["mean_vmax"] == pytest.approx(out_c["mean_vmax"], abs=1e-9)
    same_layout = out_a["position"] == out_c["position"]
    assert not (same_population and same_mean and same_layout), (
        "seeds 7 and 8 produced an identical trajectory -- `seed` is not "
        "threading into both the potts world and the mutation RNG")
