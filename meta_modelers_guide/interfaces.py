"""Fig 4 & Fig 5 draft processes — the cellular interface and its coupling.

These are *draft* processes: typed, unit-bearing ports plus a **behavior**
contract that says what the process senses, affects, and must keep in bounds —
**without committing to a mechanism** (no rate law, no update dynamics). They
render in the bigraph as interface cards (Fig 4) or a wired coupling topology
(Fig 5), and are auto-registered at ``local:<ClassName>`` by ``build_core``.

Contract convention used throughout the guide:

* ``summary``     — one line: what the process is.
* ``behavior``    — what it does, described functionally (no equations).
* ``senses``      — the interface variables it reads.
* ``affects``     — the interface variables it writes / controls.
* ``constraints`` — conservation laws / viability bounds it must respect.
* ``ports``       — every port with its biological unit.

``math`` is added only where the paper commits to a specific mechanism.
"""
from __future__ import annotations

from process_bigraph import DraftProcess, draft_process


# ─────────────────────────────────────────────────────────────────────────────
# Fig 4a — interaction-modality cards (unwired: ports + contract only)
# Each card is one channel of the cellular interface (Fig 4a).
# ─────────────────────────────────────────────────────────────────────────────
@draft_process(
    name="NutrientExchange",
    inputs={"nutrient_ext": "concentration", "boundary": "area"},
    outputs={"nutrient_uptake": "chemical_flux", "secretion": "chemical_flux"},
    contract={
        "summary": "Nutrient exchange — chemical flux across the cell boundary.",
        "behavior": "Moves matter between the cell and its environment: takes up "
                    "nutrients and releases secretions/waste across the membrane.",
        "senses": "external nutrient concentration; available boundary area.",
        "affects": "the environmental nutrient pool via directed chemical fluxes.",
        "constraints": "mass is conserved across the boundary; flux is bounded by "
                       "transporter capacity and available area.",
        "ports": {
            "nutrient_ext": "external nutrient concentration (mol·L⁻¹)",
            "boundary": "membrane exchange area (m²)",
            "nutrient_uptake": "uptake flux, into cell (mol·s⁻¹)",
            "secretion": "secretion/waste flux, out of cell (mol·s⁻¹)",
        },
    },
)
class NutrientExchange(DraftProcess):
    pass


@draft_process(
    name="MotileForce",
    inputs={"energy": "energy"},
    outputs={"force": "force"},
    contract={
        "summary": "Motile force generation — mechanical output for movement.",
        "behavior": "Consumes free energy to generate a propulsive/traction force "
                    "on the environment (e.g. flagellar thrust, crawling).",
        "senses": "internal available energy.",
        "affects": "the mechanical interface — a force exerted on surroundings.",
        "constraints": "force output is bounded by energy supply; energy is not "
                       "created (thermodynamic consistency).",
        "ports": {
            "energy": "free energy available for motility (J)",
            "force": "propulsive force exerted (kg·m·s⁻², N)",
        },
    },
)
class MotileForce(DraftProcess):
    pass


@draft_process(
    name="Growth",
    inputs={"substrate": "chemical_flux"},
    outputs={"growth_rate": "growth_rate", "mass": "mass"},
    contract={
        "summary": "Growth — conversion of uptake into biomass.",
        "behavior": "Turns incoming substrate flux into new cellular material, "
                    "expanding mass and setting the instantaneous growth rate.",
        "senses": "the net substrate flux delivered by exchange/metabolism.",
        "affects": "cell mass and the reported growth rate.",
        "constraints": "growth rate ≥ 0 and bounded by substrate supply; biomass "
                       "yield respects mass/energy balance.",
        "ports": {
            "substrate": "net substrate flux available for biosynthesis (mol·s⁻¹)",
            "growth_rate": "specific growth rate (hr⁻¹)",
            "mass": "cell biomass (kg)",
        },
    },
)
class Growth(DraftProcess):
    pass


@draft_process(
    name="ElectricalSignaling",
    inputs={"membrane_potential": "voltage"},
    outputs={"signal": "signaling_rate", "current": "current"},
    contract={
        "summary": "Electrical signaling — information exchange via charge.",
        "behavior": "Encodes and transmits information by modulating transmembrane "
                    "currents and potential (e.g. action potentials, gap-junction "
                    "coupling).",
        "senses": "the membrane potential.",
        "affects": "transmembrane current and the outgoing signaling rate.",
        "constraints": "charge is conserved; signaling rate bounded by channel "
                       "kinetics and the electrochemical gradient.",
        "ports": {
            "membrane_potential": "transmembrane potential (V)",
            "signal": "information rate carried by the signal (bits·s⁻¹)",
            "current": "transmembrane current (C·s⁻¹, A)",
        },
    },
)
class ElectricalSignaling(DraftProcess):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Fig 4b — the minimal cellular interface (one boxed cell exposing all ports)
# Physical ports + higher-level cellular ports; subports named in the contract.
# ─────────────────────────────────────────────────────────────────────────────
@draft_process(
    name="CellularInterface",
    inputs={
        # environmental drivers the cell senses
        "chemical_ext": "concentration",
        "mechanical_ext": "force",
        "electrical_ext": "voltage",
        "thermal_ext": "temperature",
    },
    outputs={
        # physical exchange ports
        "chemical": "chemical_flux",
        "mechanical": "force",
        "electrical": "current",
        "thermal": "heat_flux",
        # higher-level cellular ports
        "growth_rate": "growth_rate",
        "shape": "volume",
        "signaling": "signaling_rate",
        "objective": "objective",
        "viability": "viability",
    },
    contract={
        "summary": "The minimal cellular interface — physical + cellular ports.",
        "behavior": "Abstracts a cell as a bounded, goal-directed system: it "
                    "senses environmental gradients and exposes a small set of "
                    "controllable exchange variables plus higher-level cellular "
                    "descriptors, standing in for all internal mechanism.",
        "senses": "external chemical, mechanical, electrical, and thermal state.",
        "affects": "chemical flux, mechanical force, electrical current, and heat "
                   "exchange; and reports growth rate, shape, signaling, objective, "
                   "and viability.",
        "constraints": "physical fluxes obey mass and energy balance; the cell is "
                       "a valid description only while viability bounds "
                       "(temperature, pH, toxin levels) hold.",
        "subports": "chemical refines into {nutrient uptake, secretions, gene "
                    "exchange}; mechanical refines into {adhesion, motility, "
                    "tension} (Fig 4b).",
        "ports": {
            "chemical_ext": "sensed external concentration (mol·L⁻¹)",
            "mechanical_ext": "sensed external force (kg·m·s⁻², N)",
            "electrical_ext": "sensed external potential (V)",
            "thermal_ext": "sensed environmental temperature (°C)",
            "chemical": "chemical exchange flux (mol·s⁻¹)",
            "mechanical": "mechanical force exchanged (kg·m·s⁻², N)",
            "electrical": "electrical current (C·s⁻¹, A)",
            "thermal": "heat transfer (J·s⁻¹, W)",
            "growth_rate": "specific growth rate (hr⁻¹)",
            "shape": "cell shape / volume (m³; area m²)",
            "signaling": "signaling information rate (bits·s⁻¹)",
            "objective": "goal function value, e.g. biomass (dimensionless)",
            "viability": "in-bounds fraction; 1 = viable, 0 = disintegration (0–1)",
        },
    },
)
class CellularInterface(DraftProcess):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Fig 5b — cell–environment coupling (wired topology)
# Environmental processes act on shared fields; the cell couples through them.
# ─────────────────────────────────────────────────────────────────────────────
@draft_process(
    name="ReactionDiffusion",
    inputs={"chemical_field": "concentration"},
    outputs={"chemical_field": "concentration"},
    contract={
        "summary": "Reaction–diffusion — spreads and transforms chemical fields.",
        "behavior": "Relaxes chemical gradients over space and interconverts "
                    "species, setting how fast perturbations propagate through the "
                    "environment.",
        "senses": "the environmental chemical field.",
        "affects": "the same chemical field (smoothing + reaction).",
        "constraints": "total chemical mass conserved except for reaction sources/"
                       "sinks; non-negativity of concentrations.",
        "ports": {
            "chemical_field": "environmental chemical concentration field (mol·L⁻¹)",
        },
    },
)
class ReactionDiffusion(DraftProcess):
    pass


@draft_process(
    name="ProductionDegradation",
    inputs={"chemical_field": "concentration"},
    outputs={"chemical_field": "concentration"},
    contract={
        "summary": "Production / degradation — chemical sources and sinks.",
        "behavior": "Adds or removes chemical species in the environment "
                    "(e.g. buffered supply, abiotic decay), independent of cells.",
        "senses": "the environmental chemical field.",
        "affects": "the chemical field via zeroth/first-order source and sink terms.",
        "constraints": "concentrations stay non-negative; sinks bounded by "
                       "available amount.",
        "ports": {
            "chemical_field": "environmental chemical concentration field (mol·L⁻¹)",
        },
    },
)
class ProductionDegradation(DraftProcess):
    pass


@draft_process(
    name="MechanicalStress",
    inputs={"mechanical_field": "force", "barriers": "force"},
    outputs={"mechanical_field": "force"},
    contract={
        "summary": "Mechanical stress — force fields and physical barriers.",
        "behavior": "Propagates and relaxes mechanical stress in the environment "
                    "and enforces physical barriers/boundaries the cell pushes on.",
        "senses": "the environmental force field and barrier configuration.",
        "affects": "the mechanical force field.",
        "constraints": "momentum balance; barrier forces are reactive "
                       "(oppose penetration).",
        "ports": {
            "mechanical_field": "environmental stress field (kg·m·s⁻², N)",
            "barriers": "reactive barrier force (kg·m·s⁻², N)",
        },
    },
)
class MechanicalStress(DraftProcess):
    pass


@draft_process(
    name="SingleCellProcesses",
    inputs={
        "chemical_field": "concentration",
        "mechanical_field": "force",
        "location": "volume",
    },
    outputs={
        "location": "volume",
        "mass": "mass",
        "shape": "volume",
        "uptake": "chemical_flux",
        "traction": "force",
    },
    contract={
        "summary": "Single-cell processes — the cell's side of the coupling.",
        "behavior": "Bundles the internal processes that read local environmental "
                    "state and act back on it: uptake/secretion into the chemical "
                    "field and traction onto the mechanical field, updating the "
                    "cell's own location, mass, and shape.",
        "senses": "local chemical and mechanical fields at the cell's location.",
        "affects": "the shared fields (uptake, traction) and the cell's internal "
                   "state (location, mass, shape) — closing the sense/act loop.",
        "constraints": "matter and momentum exchanged with the environment are "
                       "conserved; the cell stays within viability bounds.",
        "ports": {
            "chemical_field": "local chemical concentration (mol·L⁻¹)",
            "mechanical_field": "local stress (kg·m·s⁻², N)",
            "location": "cell position / occupied volume (m³)",
            "mass": "cell biomass (kg)",
            "shape": "cell shape / volume (m³)",
            "uptake": "flux exchanged with the field (mol·s⁻¹)",
            "traction": "force exerted on the field (kg·m·s⁻², N)",
        },
    },
)
class SingleCellProcesses(DraftProcess):
    pass


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
