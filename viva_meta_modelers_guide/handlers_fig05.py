"""Fig 5 · cell–environment coupling — EXECUTABLE handlers (the hardest figure).

The Fig 5b semantic composite draws a shared **environment** whose fields the
single cell senses and acts back on (uptake, traction), closing a minimal
sense/act loop. The draft processes are effect *signatures* (typed ports, no
dynamics); this module supplies conforming **handlers** with a genuine spatial
field so ``compile_composite`` (see compile.py) can swap each draft for its
handler and get an executable composite that actually diffuses.

REAL SPATIAL FIELD (not a scalar stand-in)
------------------------------------------
The signature types ``environment.chemical_field`` as a scalar ``concentration``.
The handler environment :data:`ENV` **refines** that store into a small 1-D
lattice — a length-9 ``map[float]`` grid (keys ``"0"``…``"8"``) — and
:class:`SpatialDiffusion` runs a real finite-difference diffusion step on it
(``D · ∇²field · interval``, zero-flux/Neumann edges). Mass is conserved to
round-off. The compiler auto-detects that the handlers' ``chemical_field`` ports
wire to a refined store and relaxes conformance for them (an ``array``/``map``
port conforming to a ``concentration`` signature port is legal *because* the env
refines that store), so the external interface (ports + wired paths) is
unchanged — only the field leaf's schema is enriched.

Why ``map[float]`` and not ``array`` / ``list``
-----------------------------------------------
process-bigraph's compile pipeline can only *merge* (``dict.update``) a refine
patch into the existing store leaf, and the Fig 5 leaves carry ``_type``,
``_value`` and ``_figure`` keys that cannot be removed. The ``array`` and
``list`` realizers do not read ``_default`` from such a leaf-dict and choke on
those extra keys (``array`` feeds every key into ``np.array`` → inhomogeneous
shape; ``list`` returns ``None``). ``map`` is the one container whose realizer
**skips** ``_``-prefixed keys and reads the plain numeric keys as the grid — and
its ``apply`` adds updates **element-wise**, exactly the accumulate semantics a
diffusion delta needs. So the field is a real process-bigraph grid store (a
``map[float]``) with real neighbour coupling; this is NOT the list-of-floats
fallback.

The refine patch therefore (a) sets ``_type: "map"`` and writes the initial
lattice as plain numeric keys ``"0"``…``"8"``, and (b) **overwrites** the two
inherited scalar ``_``-keys that would break parameterized-type reification:
``_value`` (the scalar's ``1.0``) → ``"float"`` — which is exactly ``map``'s
value-type field — and ``_figure`` (the store's SVG icon) → ``"float"``, because
when the store carries its own ``_type`` the realizer routes through
``access_type``/``reify_schema``, which calls ``core.access()`` on *every*
non-``_type``/``_default`` key as a type expression; a full SVG string is not a
parseable type and raises. Overwriting the icon is a cosmetic change confined to
the declared refine path (the interface — ports + wired paths — is untouched).

Handlers are auto-registered at ``local:<ClassName>`` by build_core (top-level
module); ports are declared config-independently so conformance is checkable
before instantiation. See handlers.py (Fig 6) for the exemplar Process style.
"""
from __future__ import annotations

from process_bigraph import Process


# ── field (grid) helpers ─────────────────────────────────────────────────────
GRID_N = 9  # a 9-cell 1-D lattice — MINIMAL but REAL.


def _init_grid() -> dict:
    """A length-9 lattice with a unit bump at the centre cell (index 4)."""
    grid = {str(i): 0.0 for i in range(GRID_N)}
    grid[str(GRID_N // 2)] = 1.0
    return grid


def _to_list(field) -> list[float]:
    """Read a ``map[float]`` field store into an index-ordered list of floats."""
    return [float(field[str(i)]) for i in range(len(field))]


def _laplacian(v: list[float]) -> list[float]:
    """Discrete 1-D Laplacian with zero-flux (Neumann) edges: the boundary cell
    uses itself as the outside neighbour, so no mass leaves the lattice."""
    n = len(v)
    lap = [0.0] * n
    for i in range(n):
        left = v[i - 1] if i > 0 else v[i]
        right = v[i + 1] if i < n - 1 else v[i]
        lap[i] = left - 2.0 * v[i] + right
    return lap


def _delta_map(deltas: list[float]) -> dict:
    """Pack an index-ordered delta list into a ``map[float]`` update dict; the
    Map ``apply`` adds it to the store cell-by-cell."""
    return {str(i): deltas[i] for i in range(len(deltas))}


def _f(default):  # a float config field
    return {"_type": "float", "_default": default}


# ── ReactionDiffusion signature → a REAL finite-difference diffusion handler ──
# signature ReactionDiffusion: in {chemical_field: concentration}
#                              out {chemical_field: concentration}
# (chemical_field is REFINED to a map[float] grid by ENV, so both ports are grids.)

class SpatialDiffusion(Process):
    """Real spatial diffusion on the chemical grid: returns the diffusion delta
    ``D · ∇²field · interval`` (zero-flux edges). Mass-conserving."""
    config_schema = {"diffusivity": _f(0.2)}

    def inputs(self):
        return {"chemical_field": "map[float]"}

    def outputs(self):
        return {"chemical_field": "map[float]"}

    def update(self, state, interval):
        field = _to_list(state["chemical_field"])
        lap = _laplacian(field)
        d = self.config["diffusivity"]
        return {"chemical_field": _delta_map([d * lap[i] * interval
                                              for i in range(len(field))])}


# ── ProductionDegradation signature → grid source + first-order decay ─────────
# signature ProductionDegradation: in {chemical_field: concentration}
#                                  out {chemical_field: concentration}

class ProductionDegradationField(Process):
    """A localized source injecting chemical at one grid cell plus first-order
    decay everywhere: dfield/dt = source·δ(source_index) − k·field."""
    config_schema = {
        "source_index": {"_type": "integer", "_default": 0},
        "source_rate": _f(0.05),
        "decay_rate": _f(0.01),
    }

    def inputs(self):
        return {"chemical_field": "map[float]"}

    def outputs(self):
        return {"chemical_field": "map[float]"}

    def update(self, state, interval):
        field = _to_list(state["chemical_field"])
        c = self.config
        deltas = [-c["decay_rate"] * field[i] * interval
                  for i in range(len(field))]
        src = c["source_index"]
        if 0 <= src < len(deltas):
            deltas[src] += c["source_rate"] * interval
        return {"chemical_field": _delta_map(deltas)}


# ── MechanicalStress signature → scalar relaxation toward barrier equilibrium ─
# signature MechanicalStress: in {mechanical_field: force, barriers: force}
#                             out {mechanical_field: force}

class MechanicalRelax(Process):
    """Relax the (scalar) mechanical field toward the barrier-imposed
    equilibrium: dσ/dt = relax_rate · (barriers − σ)."""
    config_schema = {"relax_rate": _f(0.3)}

    def inputs(self):
        return {"mechanical_field": "force", "barriers": "force"}

    def outputs(self):
        return {"mechanical_field": "force"}

    def update(self, state, interval):
        sigma = float(state.get("mechanical_field", 0.0))
        barriers = float(state.get("barriers", 0.0))
        return {"mechanical_field":
                self.config["relax_rate"] * (barriers - sigma) * interval}


# ── SingleCellProcesses signature → senses the local field, acts back ────────
# signature SingleCellProcesses:
#   in  {chemical_field: concentration, mechanical_field: force, location: volume}
#   out {location: volume, mass: mass, shape: volume,
#        uptake: chemical_flux, traction: force}
# chemical_field is the REFINED grid (input only); the cell reads it at its grid
# index. uptake/traction/location/mass/shape are SCALAR outputs (NOT the grid).

class SingleCellSpatial(Process):
    """The single cell samples the chemical grid at its own lattice index and
    acts back on the shared environment:

    * ``uptake``   — local chemical taken up (a flux to environment.uptake_flux);
    * ``mass``     — grows from local uptake (biomass yield);
    * ``shape``    — grows with the accumulated mass proxy;
    * ``traction`` — force exerted, driven by local chemical + mechanical field;
    * ``location`` — 1-D chemotactic drift up the local concentration gradient.
    """
    config_schema = {
        "cell_index": {"_type": "integer", "_default": 4},
        "uptake_rate": _f(0.1),
        "biomass_yield": _f(0.5),
        "shape_growth": _f(0.2),
        "traction_coef": _f(0.05),
        "migration_rate": _f(0.1),
    }

    def inputs(self):
        return {"chemical_field": "map[float]",
                "mechanical_field": "force",
                "location": "volume"}

    def outputs(self):
        return {"location": "volume", "mass": "mass", "shape": "volume",
                "uptake": "chemical_flux", "traction": "force"}

    def update(self, state, interval):
        field = _to_list(state["chemical_field"])
        n = len(field)
        c = self.config
        idx = max(0, min(c["cell_index"], n - 1))
        local = field[idx]
        mechanical = float(state.get("mechanical_field", 0.0))

        uptake = c["uptake_rate"] * local * interval
        mass_gain = c["biomass_yield"] * uptake
        shape_gain = c["shape_growth"] * uptake
        traction = c["traction_coef"] * (local + mechanical) * interval

        # chemotactic drift: move up the local concentration gradient.
        right = field[idx + 1] if idx < n - 1 else field[idx]
        left = field[idx - 1] if idx > 0 else field[idx]
        drift = c["migration_rate"] * 0.5 * (right - left) * interval

        return {
            "location": drift,
            "mass": mass_gain,
            "shape": shape_gain,
            "uptake": uptake,
            "traction": traction,
        }


# ── handler environment H (fed to compile_composite as ⟦Fig5⟧_H) ─────────────
# refine turns environment.chemical_field (scalar concentration) into the length-9
# map[float] grid: set _type -> "map", add the numeric grid keys, and overwrite
# the inherited scalar `_value` (-> "float", map's value-type field) and `_figure`
# (-> "float", so it survives reification as a parseable type token). All
# refine/init blocks are merged across the env by the compiler, so this single
# grid refinement applies to every handler wired to that store.
_GRID_REFINE = {"_type": "map", "_value": "float", "_figure": "float",
                **_init_grid()}

ENV = {
    "ReactionDiffusion": {
        "handler": "SpatialDiffusion",
        "config": {"diffusivity": 0.2},
        "refine": {"environment.chemical_field": _GRID_REFINE},
    },
    "ProductionDegradation": {
        "handler": "ProductionDegradationField",
        "config": {"source_index": 0, "source_rate": 0.05, "decay_rate": 0.01},
    },
    "MechanicalStress": {
        "handler": "MechanicalRelax",
        "config": {"relax_rate": 0.3},
        "init": {"environment.mechanical_field": 0.0,
                 "environment.barriers": 1.0},
    },
    "SingleCellProcesses": {
        "handler": "SingleCellSpatial",
        "config": {"cell_index": 4},
        "init": {"single_cell.location": 4.0,
                 "single_cell.mass": 1.0,
                 "single_cell.shape": 1.0},
    },
}
