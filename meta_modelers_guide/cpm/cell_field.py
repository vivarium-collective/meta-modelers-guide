"""CpmCellField — a CPM cell (viva-cpm) that metabolizes a shared spatio-flux nutrient
field at its footprint and grows from the biomass it makes.

Owns the CPM world (the lattice + growth are not process-bigraph stores, so a single
world-owning process is the clean coupling point). Composes over one shared ``fields``
grid with spatio-flux ``DiffusionAdvection``: the cell reads glucose at its footprint,
runs one dFBA step (e_coli_core), writes back the uptake (-glucose) and secretion
(+acetate) as a field delta, and grows its CPM target volume in proportion to biomass.
Toy-real: plausible constants, not a fitted organism.

Oxygen note: unconstrained e_coli_core FBA never secretes acetate — pure aerobic
respiration is the growth-optimal flux distribution whenever O2 uptake is unbounded, so
``EX_ac_e`` sits at 0 for any glucose bound. Real E. coli exhibits acetate overflow once
glycolytic flux outpaces respiratory (TCA/ETC) capacity, which FBA only reproduces if
respiration is capacity-limited. We therefore cap ``EX_o2_e`` uptake at a fixed
microaerobic bound (``oxygen_vmax``, default 15 mmol/gDW/hr — below the ~18-22 the model
wants at glucose saturation) so the optimizer is forced into mixed-acid overflow,
matching the biological mechanism the coupling is meant to demonstrate.
"""
from __future__ import annotations

import numpy as np
from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


class CpmCellField(Process):
    config_schema = {
        "nx": {"_type": "integer", "_default": 40},
        "ny": {"_type": "integer", "_default": 40},
        # NOTE: no `_default` here — bigraph-schema's generic "list" type
        # *concatenates* an incoming config value with a schema-declared
        # `_default` on merge (rather than replacing it), so a caller-supplied
        # 6-int seed_block becomes a spurious 12-int list. Fall back to the
        # sensible default in Python (see `__init__`) instead.
        "seed_block": {"_type": "list"},
        "mcs_per_update": {"_type": "integer", "_default": 8},
        "temperature": _f(10.0),
        "lambda_volume": _f(2.0),
        "contact_j": _f(14.0),
        "biomass0": _f(0.1),
        "grow_per_biomass": _f(300.0),   # target_volume = grow_per_biomass * biomass
        "box_volume_L": _f(1e-6),
        "glucose_km": _f(0.5), "glucose_vmax": _f(10.0),
        "oxygen_vmax": _f(15.0),  # microaerobic cap -> forces acetate overflow
        # --- interface-substitutability: swappable INTERNAL metabolism ---------
        # `mechanism` selects the box behind the fixed cell<->field interface. The
        # PORTS (inputs/outputs) are byte-identical across mechanisms; only the
        # internal organization that realizes uptake/growth/secretion differs.
        #   "dfba" (default, backward-compatible): constraint-based dynamic-FBA on
        #          e_coli_core (requires cobra), the flagship metabolism above.
        #   "mm":   a lumped Michaelis-Menten / Monod metabolism with NO cobra --
        #          uptake v = mm_vmax * glc/(mm_km+glc); biomass gain = mm_yield*v;
        #          acetate overflow = mm_overflow*v (a fixed overflow fraction
        #          standing in for the dFBA's O2-cap-driven mixed-acid overflow).
        # See `_mm` and the substitutability study/test for the tuning that makes
        # the two mechanisms preserve the same coarse-grained interface variables.
        "mechanism": {"_type": "string", "_default": "dfba"},
        "mm_vmax": _f(10.0), "mm_km": _f(0.5),
        "mm_yield": _f(0.09),      # biomass yield mu = mm_yield * v  (growth per uptake)
        "mm_overflow": _f(0.5),    # acetate secreted per unit glucose uptake
        # --- steady-state regime: cell-independent field source/sink + biomass turnover -
        # The flagship is a pure TRANSIENT (no source terms) — it never reaches a
        # source/sink equilibrium. These four terms (all default 0.0 -> OFF, so the
        # flagship is byte-identical) add a standing environmental supply/degradation
        # field plus biomass turnover, turning the composite into a chemostat-like
        # regime with a genuine flux fixed point:
        #   glucose SOURCE (first-order relaxation toward a setpoint, applied
        #     grid-wide): dG = glucose_source_rate * (glucose_source_target - G) * dt
        #   acetate DECAY (first-order sink, grid-wide): dA = -acetate_decay_rate * A * dt
        #   biomass CARRYING CAPACITY (logistic growth saturation): growth is scaled
        #     by max(0, 1 - biomass/biomass_capacity), so biomass approaches a fixed
        #     stationary-phase ceiling instead of compounding without bound (the
        #     flagship's unbounded exponential growth is why the flagship run is capped
        #     at ~20-25 ticks). A dilution term alone gives NO interior biomass fixed
        #     point in this coupling — the cell's per-pixel uptake scales with
        #     biomass/footprint-area (both grow together), so local glucose equilibrates
        #     at a biomass-independent value and mu never falls to a dilution rate. The
        #     logistic cap is what makes biomass, and therefore every metabolic flux,
        #     reach a verifiable d/dt -> 0 steady state.
        "glucose_source_rate": _f(0.0),
        "glucose_source_target": _f(0.0),
        "acetate_decay_rate": _f(0.0),
        "biomass_capacity": _f(0.0),   # 0.0 -> unbounded (flagship); >0 -> logistic cap
        # --- CHEMOTAXIS: directed motion up the sensed glucose gradient ------------
        # The flagship senses -> metabolizes -> grows -> secretes but does NOT act on
        # what it senses (no directed motion). This term closes the sense->act loop by
        # biasing the CPM cell's Metropolis pixel-copy UP the local glucose gradient of
        # the SHARED spatio-flux field (not viva-cpm's separate internal PDE field).
        #
        # Mechanism: each tick we read the shared glucose field the cell already senses,
        # take its spatial gradient grad(glucose) averaged over the cell's footprint, and
        # set viva-cpm's per-type external-potential force f = chemotaxis_strength *
        # grad(glucose). viva-cpm's Hamiltonian then adds U(r) = -f.r per pixel, so
        # dH = (f_old - f_new).r for a copy — a copy that moves the footprint toward
        # higher x (higher glucose) is energetically favoured. This is the linearized
        # (grad-driven) form of CC3D chemotaxis dH = -lambda*dc, driven by the external
        # shared field rather than a viva-cpm-internal one (which has no write path here).
        #
        # DEFAULT 0.0 -> OFF: when strength is 0 we never call set_external_potential, so
        # the world's ext-potential stays all-zero and the base flagship run is
        # byte-identical. >0 turns on directed up-gradient motion (the chemotaxis variant).
        "chemotaxis_strength": _f(0.0),
    }

    def inputs(self):
        return {"fields": "map[array]"}

    def outputs(self):
        # process-bigraph's plain "float"/"list" apply is *additive* (a process's
        # returned value is treated as a delta to accumulate onto prior state) and
        # plain "list" apply *concatenates*. `volume`, `position`, `local_nutrient`,
        # and `biomass` are this process's current absolute readings each tick, not
        # deltas, so they must be declared `overwrite[...]` (replace-on-apply) or a
        # multi-tick run silently sums/concatenates them into nonsense (observed:
        # volume growing far past the lattice's pixel count, position turning into
        # a running concatenation of every tick's [x, y]). `acetate_secreted` is a
        # genuine per-tick delta (this tick's secretion), so plain "float" is
        # correct there — and `fields` is a real spatial delta the engine sums into
        # the shared grid, which is the whole point of the coupling.
        return {"fields": "map[array]", "volume": "overwrite[float]", "position": "overwrite[list]",
                "local_nutrient": "overwrite[float]", "biomass": "overwrite[float]",
                "acetate_secreted": "float"}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        from cpm.schema import load_world
        c = self.config
        nx, ny = int(c["nx"]), int(c["ny"])
        self._nx, self._ny = nx, ny
        seed_block = list(c["seed_block"]) or [17, 17, 0, 24, 24, 1]
        spec = {
            "potts": {"dims": [nx, ny, 1], "boundary": "noflux", "neighbor_order": 2,
                      "temperature": c["temperature"], "seed": 1},
            "cells": [{"type": 1, "target_volume": 60.0, "lambda_volume": c["lambda_volume"],
                       "target_surface": 0.0, "lambda_surface": 0.0,
                       "seed_block": seed_block}],
            "contact": [{"a": 0, "b": 1, "j": c["contact_j"]}],
        }
        self.world = load_world(spec)
        self.biomass = float(c["biomass0"])
        self.mechanism = str(c["mechanism"])
        self._model = None
        if self.mechanism == "dfba":
            # one cobra e_coli_core, loaded once. Only the dFBA mechanism needs
            # cobra; the "mm" (Michaelis-Menten) mechanism runs without it, so the
            # import stays inside this branch and the mm path never touches cobra.
            try:
                from cobra.io import load_model
            except Exception as exc:  # pragma: no cover - exercised only without cobra
                raise RuntimeError(
                    "CpmCellField(mechanism='dfba') requires the optional 'cobra' "
                    "package (pip install -e .[simulators]); use mechanism='mm' for "
                    "the cobra-free Michaelis-Menten metabolism.") from exc
            self._model = load_model("textbook")
            # cap respiratory capacity so glycolytic flux forces mixed-acid (acetate)
            # overflow rather than pure aerobic respiration (see module docstring)
            self._model.reactions.EX_o2_e.lower_bound = -float(c["oxygen_vmax"])
        elif self.mechanism != "mm":
            raise ValueError(
                f"CpmCellField: unknown mechanism {self.mechanism!r} "
                "(expected 'dfba' or 'mm').")

    def _footprint(self):
        lat = np.array(self.world.snapshot()).reshape(self._ny, self._nx)
        return lat == 1

    def _fba(self, glucose_conc, interval):
        """One dFBA step on e_coli_core: MM-limited glucose uptake -> requested growth +
        acetate at the footprint's mean concentration. This is the *idealized* LP
        solution, sized as if the whole footprint held `glucose_conc` everywhere and
        that much glucose were actually available; `update()` clamps the glucose
        removal against what the field's footprint pixels actually hold and scales
        both the growth and the secretion down by the same ratio, so the cell can
        never manufacture biomass/acetate from glucose it didn't actually remove."""
        c = self.config
        m = self._model
        v = c["glucose_vmax"] * glucose_conc / (c["glucose_km"] + glucose_conc) if glucose_conc > 0 else 0.0
        # budget-limit the uptake by available glucose over the footprint
        m.reactions.EX_glc__D_e.lower_bound = -float(v)
        sol = m.optimize()
        if sol.status != "optimal":
            # At v == 0 (no glucose left in the footprint) the LP is infeasible —
            # the fixed non-growth ATP maintenance demand can't be met without any
            # carbon source. `sol.objective_value` correctly comes back 0.0 in that
            # case, but cobra/optlang does NOT zero `sol.fluxes` on an infeasible
            # re-solve of a model that was previously solved to optimality: it
            # returns stale primal values left over from the last feasible solve
            # (confirmed empirically — a feasible solve followed by an infeasible
            # one on the same model object returns nonsense, e.g. a *negative*
            # EX_ac_e "acetate flux"). Never trust `sol.fluxes` unless
            # `sol.status == "optimal"`; growth and secretion both cleanly stop.
            return 0.0, 0.0, 0.0
        mu = float(sol.objective_value or 0.0)
        d_biomass = mu * self.biomass * interval
        glc_flux = float(sol.fluxes.get("EX_glc__D_e", 0.0))   # negative = uptake
        ac_flux = float(sol.fluxes.get("EX_ac_e", 0.0))        # positive = secretion
        d_glc = glc_flux * self.biomass * interval / c["box_volume_L"]
        d_ac = ac_flux * self.biomass * interval / c["box_volume_L"]
        return d_biomass, d_glc, d_ac

    def _mm(self, glucose_conc, interval):
        """One lumped Michaelis-Menten / Monod metabolism step -- a COMPLETELY
        DIFFERENT internal organization from `_fba` (no LP, no stoichiometry, no
        cobra) that returns the SAME `(d_biomass, d_glc, d_ac)` shape and flows
        through the SAME mass-conservative writeback in `update()`. This is the
        interface-substitutability demonstration: swap the box, keep the ports.

        Michaelis-Menten glucose uptake rate (per unit biomass, mmol/gDW/hr):
            v = mm_vmax * glc / (mm_km + glc)
        drives growth by a fixed biomass yield and acetate by a fixed overflow
        fraction (standing in for the dFBA's O2-cap-driven mixed-acid overflow):
            mu (growth rate)   = mm_yield   * v      -> d_biomass = mu * biomass * dt
            acetate flux       = mm_overflow * v     -> secretion, same units as v
        The glucose-uptake flux is -v (negative = uptake), so d_glc mirrors the
        dFBA path's `glc_flux * biomass * dt / box_volume_L` exactly and the
        idealized-then-clamped mass balance in `update()` applies unchanged."""
        c = self.config
        if glucose_conc <= 0:
            return 0.0, 0.0, 0.0
        v = c["mm_vmax"] * glucose_conc / (c["mm_km"] + glucose_conc)
        mu = c["mm_yield"] * v
        d_biomass = mu * self.biomass * interval
        glc_flux = -v                       # negative = uptake, mirrors EX_glc__D_e
        ac_flux = c["mm_overflow"] * v      # positive = secretion, mirrors EX_ac_e
        d_glc = glc_flux * self.biomass * interval / c["box_volume_L"]
        d_ac = ac_flux * self.biomass * interval / c["box_volume_L"]
        return d_biomass, d_glc, d_ac

    def _metabolize(self, glucose_conc, interval):
        """Dispatch to the configured internal mechanism behind the fixed interface."""
        if self.mechanism == "mm":
            return self._mm(glucose_conc, interval)
        return self._fba(glucose_conc, interval)

    def update(self, state, interval):
        fields = state.get("fields", {})
        glucose = np.asarray(fields.get("glucose"))
        acetate = np.asarray(fields.get("acetate"))
        fp = self._footprint()
        area = max(int(fp.sum()), 1)
        local_glc = float(glucose[fp].mean()) if fp.any() else 0.0

        d_biomass, requested_d_glc, d_ac = self._metabolize(local_glc, interval)

        # Mass-balance: the FBA solution above is idealized (sized off the mean
        # local concentration), but only glucose actually present at the footprint
        # can be removed. Clamp the requested removal to what's available, then
        # scale BOTH biomass growth and acetate secretion by the same ratio the
        # removal itself got clamped by — otherwise, as local glucose runs low, the
        # cell keeps growing/secreting off glucose it never actually took up. This
        # is what makes growth genuinely nutrient-limited (plateaus as the field
        # depletes) rather than unbounded, which matters once the field is
        # non-uniform / depleting rather than a flat initial condition.
        available = -float(glucose[fp].sum()) if fp.any() else 0.0   # <= 0
        clamped_d_glc = max(requested_d_glc, available)
        ratio = (clamped_d_glc / requested_d_glc) if requested_d_glc < 0 else 1.0
        d_biomass *= ratio
        d_ac *= ratio
        # Steady-state regime only (default 0.0 -> no-op): logistic carrying capacity.
        # Scaling growth by (1 - biomass/B_cap) drives biomass to a stationary-phase
        # ceiling B_cap, so growth (and hence every metabolic flux) reaches a fixed
        # point instead of compounding exponentially — the condition for a verifiable
        # d(biomass)/dt -> 0 steady state. Only positive growth is capped; a dilution
        # term alone has no interior biomass fixed point in this coupling (see config).
        b_cap = float(self.config["biomass_capacity"])
        if b_cap > 0.0 and d_biomass > 0.0:
            d_biomass *= max(0.0, 1.0 - self.biomass / b_cap)
        self.biomass = max(self.biomass + d_biomass, 1e-9)

        # Write the clamped uptake/secretion back to the field. Glucose is removed
        # from each footprint pixel *proportional to that pixel's own glucose*
        # (rather than split evenly) so that on a non-uniform field a low-glucose
        # pixel gives up proportionally less and can never be driven negative —
        # each pixel's magnitude of removal is capped at its own current value by
        # construction. Acetate secretion (a genuine addition, not a depletion) is
        # still spread evenly across the footprint.
        dglc = np.zeros_like(glucose)
        dace = np.zeros_like(acetate)
        if fp.any():
            glc_fp = glucose[fp]
            total_fp = float(glc_fp.sum())
            weights = (glc_fp / total_fp) if total_fp > 0 else np.full(area, 1.0 / area)
            dglc[fp] = clamped_d_glc * weights
            dace[fp] = d_ac / area

        # Steady-state regime only (default rates 0.0 -> no-op): a cell-INDEPENDENT
        # standing supply/degradation field applied grid-wide, on top of the cell's own
        # footprint metabolism above. Glucose is replenished by first-order relaxation
        # toward a setpoint (a standing feed) and acetate decays first-order (a washout
        # sink); together with biomass dilution they close a chemostat-like flux balance
        # the pure-transient flagship cannot reach. These are genuine open-system source
        # terms — field mass is deliberately NOT conserved here (that is the point of a
        # steady state); the flagship's mass-balance control uses the default-off path.
        k_src = float(self.config["glucose_source_rate"])
        if k_src:
            dglc += k_src * (float(self.config["glucose_source_target"]) - glucose) * interval
        k_dec = float(self.config["acetate_decay_rate"])
        if k_dec:
            dace += -k_dec * acetate * interval

        # CHEMOTAXIS (default strength 0.0 -> no-op, flagship byte-identical): bias the
        # CPM cell up the SENSED glucose gradient. We take grad(glucose) of the shared
        # field averaged over the cell's current footprint and set viva-cpm's per-type
        # external-potential force f = chemotaxis_strength * grad(glucose). The engine
        # adds U(r) = -f.r per pixel, so a pixel-copy that shifts the footprint toward
        # higher glucose lowers H and is favoured in the Metropolis acceptance — directed
        # up-gradient motion, the "act" the flagship deferred. grad points toward higher
        # concentration, so the cell climbs the gradient (positive strength).
        chi = float(self.config["chemotaxis_strength"])
        if chi != 0.0 and fp.any():
            # np.gradient over [ny, nx] returns (d/dy, d/dx); lattice coords are (x, y).
            g_y, g_x = np.gradient(glucose)
            fx = chi * float(g_x[fp].mean())
            fy = chi * float(g_y[fp].mean())
            self.world.set_external_potential(1, fx, fy, 0.0)

        # grow the CPM cell from biomass, then step the world
        target = float(self.config["grow_per_biomass"]) * self.biomass
        self.world.set_target_volume(1, max(target, 4.0))
        self.world.step(int(self.config["mcs_per_update"]))

        vol = float(self.world.cell_volumes()[1])
        com = list(self.world.cell_coms()[1])[:2]
        return {"fields": {"glucose": dglc, "acetate": dace},
                "volume": vol, "position": com, "local_nutrient": local_glc,
                "biomass": self.biomass, "acetate_secreted": float(dace.sum())}
