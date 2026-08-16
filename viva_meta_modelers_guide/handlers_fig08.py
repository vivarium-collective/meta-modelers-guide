"""Fig 8 · nested hierarchy — executable handlers for the six molecular processes
wired through the ECM→membrane→cytoplasm→nucleus→chromosome place graph.

The Fig 8b semantic composite is the deepest nesting in the atlas: processes act
on stores buried up to six levels down (``cytoplasm.nucleus.chromosome.chromatin.
nucleosome.DNA``). This module supplies conforming handlers so ``compile_composite``
produces a running gene-expression cascade *without touching the place graph* — the
strongest test of interface preservation (law 2) on a deep tree.

The six handlers form a coupled expression loop: transmembrane transport imports
nutrients; metabolism turns nutrients + enzymes into metabolites + energy;
transcription reads DNA/genes (damped by regulation) into RNA; translation reads
RNA + metabolites on the ribosome pool into proteins; subunit assembly builds
ribosomes from proteins + subunits (closing the loop back to translation); and
replication/repair grows the DNA pool. Driver pools (nutrients_ext, transporters,
genes, DNA, enzymes, regulation, ribosomal_subunits) are seeded by the environment;
products start at zero and must be made. A small ribosome seed bootstraps the loop.

Handlers auto-registered at ``local:<ClassName>`` by build_core; ports are declared
config-independently for pre-instantiation conformance. Mirrors handlers_fig09b.py.
"""
from __future__ import annotations

from process_bigraph import Process


def _f(default):
    return {"_type": "float", "_default": default}


class TransmembraneTransportODE(Process):
    """Import nutrients across the membrane at a transporter-catalysed rate:
    flux = k · nutrients_ext · transporters. The imported flux fills the cytoplasmic
    nutrient pool (and a little metabolite), and is reported on the flux port."""
    config_schema = {"k": _f(0.3), "metabolite_frac": _f(0.1)}

    def inputs(self):
        return {"nutrients_ext": "concentration", "transporters": "concentration"}

    def outputs(self):
        return {"nutrients": "concentration", "metabolites": "concentration",
                "flux": "chemical_flux"}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._last_flux = 0.0

    def update(self, state, interval):
        ext = float(state.get("nutrients_ext", 0.0))
        tr = float(state.get("transporters", 0.0))
        flux = self.config["k"] * ext * tr
        d_flux = flux - self._last_flux
        self._last_flux = flux
        return {"nutrients": flux * interval,
                "metabolites": self.config["metabolite_frac"] * flux * interval,
                "flux": d_flux}


class CellMetabolismODE(Process):
    """Enzyme-catalysed conversion of imported nutrients into metabolites + energy:
    rate = k · nutrients · enzymes (enzymes catalytic, not consumed)."""
    config_schema = {"k": _f(0.25), "metabolite_yield": _f(0.6), "energy_yield": _f(0.4)}

    def inputs(self):
        return {"nutrients": "concentration", "enzymes": "concentration"}

    def outputs(self):
        return {"metabolites": "concentration", "energy": "energy"}

    def update(self, state, interval):
        nut = float(state.get("nutrients", 0.0))
        enz = float(state.get("enzymes", 0.0))
        rate = self.config["k"] * nut * enz
        return {"metabolites": self.config["metabolite_yield"] * rate * interval,
                "energy": self.config["energy_yield"] * rate * interval}


class TranscriptionODE(Process):
    """Transcribe DNA into RNA at a gene-templated rate, damped by the regulation
    complex: rate = k · dna · genes / (1 + regulation)."""
    config_schema = {"k": _f(0.3)}

    def inputs(self):
        return {"dna": "concentration", "genes": "concentration",
                "regulation": "concentration"}

    def outputs(self):
        return {"rna": "concentration"}

    def update(self, state, interval):
        dna = float(state.get("dna", 0.0))
        genes = float(state.get("genes", 0.0))
        reg = float(state.get("regulation", 0.0))
        rate = self.config["k"] * dna * genes / (1.0 + reg)
        return {"rna": rate * interval}


class TranslationODE(Process):
    """Translate RNA into protein on the ribosome pool, drawing on metabolite
    building blocks: rate = k · rna · ribosome · (metabolites / (km + metabolites))."""
    config_schema = {"k": _f(0.4), "km": _f(0.5)}

    def inputs(self):
        return {"rna": "concentration", "metabolites": "concentration",
                "ribosome": "count"}

    def outputs(self):
        return {"proteins": "concentration"}

    def update(self, state, interval):
        rna = float(state.get("rna", 0.0))
        met = float(state.get("metabolites", 0.0))
        rib = float(state.get("ribosome", 0.0))
        c = self.config
        supply = met / (c["km"] + met) if (c["km"] + met) else 0.0
        return {"proteins": c["k"] * rna * rib * supply * interval}


class SubunitAssemblyODE(Process):
    """Assemble ribosomes from proteins + ribosomal subunits: rate = k · proteins ·
    ribosomal_subunits. Closes the loop back to translation."""
    config_schema = {"k": _f(0.2)}

    def inputs(self):
        return {"proteins": "concentration", "ribosomal_subunits": "count"}

    def outputs(self):
        return {"ribosome": "count"}

    def update(self, state, interval):
        prot = float(state.get("proteins", 0.0))
        sub = float(state.get("ribosomal_subunits", 0.0))
        return {"ribosome": self.config["k"] * prot * sub * interval}


class ReplicationAndRepairODE(Process):
    """Grow/maintain the DNA pool from the gene template: rate = k · genes
    (first-order template-directed replication and repair)."""
    config_schema = {"k": _f(0.05)}

    def inputs(self):
        return {"dna": "concentration", "genes": "concentration"}

    def outputs(self):
        return {"dna": "concentration"}

    def update(self, state, interval):
        genes = float(state.get("genes", 0.0))
        return {"dna": self.config["k"] * genes * interval}


# ── handler environment ⟦Fig8⟧_H ──────────────────────────────────────────────
# Seed the driver pools (external nutrients, transporters, genes, DNA, enzymes,
# regulation, ribosomal subunits) + a small ribosome seed to bootstrap the loop.
# init sets a leaf's ``_default`` (realize ignores ``_value``); all entries' inits
# are merged by the compiler.
_CYTO = "cytoplasm"
_DNA = "cytoplasm.nucleus.chromosome.chromatin.nucleosome.DNA"
_RIBOSOME = "cytoplasm.organelles.ribosomal_complex.ribosome"
_SUBUNITS = "cytoplasm.organelles.ribosomal_complex.ribosomal_subunits"

ENV = {
    "TransmembraneTransport": {
        "handler": "TransmembraneTransportODE",
        "config": {"k": 0.3, "metabolite_frac": 0.1},
        "init": {
            "extracellular_matrix.interstitial_matrix": 1.0,   # nutrients_ext
            "membrane.transmembrane_transporters": 1.0,        # transporters
            f"{_CYTO}.enzymes": 1.0,
            "cytoplasm.nucleus.genes": 1.0,
            _DNA: 1.0,
            "cytoplasm.nucleus.transcription_regulation_complex": 1.0,
            _SUBUNITS: 1.0,
            _RIBOSOME: 0.5,   # bootstrap seed so translation can start
        },
    },
    "CellMetabolism": {"handler": "CellMetabolismODE",
                       "config": {"k": 0.25, "metabolite_yield": 0.6, "energy_yield": 0.4}},
    "Transcription": {"handler": "TranscriptionODE", "config": {"k": 0.3}},
    "Translation": {"handler": "TranslationODE", "config": {"k": 0.4, "km": 0.5}},
    "SubunitAssembly": {"handler": "SubunitAssemblyODE", "config": {"k": 0.2}},
    "ReplicationAndRepair": {"handler": "ReplicationAndRepairODE", "config": {"k": 0.05}},
}
