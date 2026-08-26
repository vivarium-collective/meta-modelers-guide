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
replication/repair maintains the DNA pool. Driver pools (nutrients_ext, transporters,
genes, DNA, enzymes, regulation, ribosomal_subunits) are seeded by the environment;
products start at zero and must be made. A small ribosome seed bootstraps the loop.

**Rates are grounded in E. coli literature (time in seconds), so the "time
hierarchy" of the central dogma is quantitative** (Bremer & Dennis 2008; Milo &
Phillips, *Cell Biology by the Numbers*; Bernstein et al. 2002):

* transcription elongation ≈ 45 nt·s⁻¹, representative gene ≈ 1000 nt;
* translation elongation ≈ 15 aa·s⁻¹, representative protein ≈ 300 aa;
* mRNA half-life ≈ 3 min → decay ``k = ln2/180 s⁻¹``;
* protein/ribosome loss = dilution at a 30-min doubling → ``k = ln2/1800 s⁻¹``.

Each single-writer product pool carries its own first-order loss (self-tracked,
so no new ports), giving steady states of mRNA ≈ 1–10 and protein ≈ 10²–10³ copies
— mRNA equilibrating within minutes, protein over ~an hour.

Handlers auto-registered at ``local:<ClassName>`` by build_core; ports are declared
config-independently for pre-instantiation conformance. Mirrors handlers_fig08b.py.
"""
from __future__ import annotations

import math

from process_bigraph import Process

_LN2 = math.log(2.0)  # 0.6931…, for half-life → first-order rate conversions


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
    """Transcribe DNA into RNA at the E. coli elongation rate, damped by the
    regulation complex, minus first-order mRNA decay:

        synthesis = (elong_nt_per_s / gene_length_nt) · dna · genes / (1 + regulation)
        decay     = (ln2 / mrna_halflife_s) · rna

    Elongation ≈ 45 nt·s⁻¹ over a ≈1000-nt gene ⇒ ~0.045 transcripts·s⁻¹ per active
    template; mRNA half-life ≈ 3 min. Steady state rna ≈ synthesis/decay ≈ few copies.
    ``rna`` is written only here, so its running total is self-tracked to apply decay
    without a new input port."""
    config_schema = {"elong_nt_per_s": _f(45.0), "gene_length_nt": _f(1000.0),
                     "mrna_halflife_s": _f(180.0)}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._rna = 0.0   # products start at zero (matches ENV; no rna seed)

    def inputs(self):
        return {"dna": "concentration", "genes": "concentration",
                "regulation": "concentration"}

    def outputs(self):
        return {"rna": "concentration"}

    def update(self, state, interval):
        dna = float(state.get("dna", 0.0))
        genes = float(state.get("genes", 0.0))
        reg = float(state.get("regulation", 0.0))
        c = self.config
        k_txn = c["elong_nt_per_s"] / c["gene_length_nt"]     # transcripts·s⁻¹ per template
        synthesis = k_txn * dna * genes / (1.0 + reg)
        k_decay = _LN2 / c["mrna_halflife_s"]                 # ln2/180 s⁻¹
        d_rna = (synthesis - k_decay * self._rna) * interval
        self._rna += d_rna
        return {"rna": d_rna}


class TranslationODE(Process):
    """Translate RNA into protein at the E. coli elongation rate, on a
    ribosome-saturating capacity and drawing on metabolite building blocks, minus
    first-order protein dilution:

        synthesis  = (elong_aa_per_s / protein_length_aa) · rna
                     · [ribosome/(km_rib+ribosome)] · [metabolites/(km_met+metabolites)]
        dilution   = (ln2 / doubling_time_s) · proteins

    Elongation ≈ 15 aa·s⁻¹ over a ≈300-aa protein ⇒ ~0.05 proteins·s⁻¹ per mRNA at
    saturating ribosome/metabolite supply; protein loss is dilution at a 30-min
    doubling. With rna ≈ 6, steady-state protein ≈ synthesis/dilution ≈ few hundred
    copies. The ribosome enters through a saturating term (so the ribosome→protein→
    ribosome loop stays bounded, not autocatalytic). ``proteins`` is written only
    here, so its total is self-tracked to apply dilution without a new port."""
    config_schema = {"elong_aa_per_s": _f(15.0), "protein_length_aa": _f(300.0),
                     "doubling_time_s": _f(1800.0), "km_met": _f(0.5), "km_rib": _f(0.5)}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._protein = 0.0   # products start at zero

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
        k_tr = c["elong_aa_per_s"] / c["protein_length_aa"]   # proteins·s⁻¹ per mRNA
        met_supply = met / (c["km_met"] + met) if (c["km_met"] + met) else 0.0
        rib_supply = rib / (c["km_rib"] + rib) if (c["km_rib"] + rib) else 0.0
        synthesis = k_tr * rna * rib_supply * met_supply
        k_dil = _LN2 / c["doubling_time_s"]                   # ln2/1800 s⁻¹
        d_prot = (synthesis - k_dil * self._protein) * interval
        self._protein += d_prot
        return {"proteins": d_prot}


class SubunitAssemblyODE(Process):
    """Assemble ribosomes from proteins + ribosomal subunits, minus dilution:
    rate = k · proteins · ribosomal_subunits − (ln2/doubling_time)·ribosome. Closes
    the loop back to translation. Dilution at the 30-min doubling bounds the pool;
    ``ribosome`` is written only here, self-tracked from its seed so dilution is
    applied without a new input port."""
    config_schema = {"k": _f(0.2), "doubling_time_s": _f(1800.0),
                     "ribosome_init": _f(0.5)}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._ribosome = self.config["ribosome_init"]   # matches the ENV bootstrap seed

    def inputs(self):
        return {"proteins": "concentration", "ribosomal_subunits": "count"}

    def outputs(self):
        return {"ribosome": "count"}

    def update(self, state, interval):
        prot = float(state.get("proteins", 0.0))
        sub = float(state.get("ribosomal_subunits", 0.0))
        c = self.config
        k_dil = _LN2 / c["doubling_time_s"]
        d_rib = (c["k"] * prot * sub - k_dil * self._ribosome) * interval
        self._ribosome += d_rib
        return {"ribosome": d_rib}


class ReplicationAndRepairODE(Process):
    """Maintain the DNA pool from the gene template at balanced growth: synthesis =
    (ln2/doubling_time)·genes offsets dilution (ln2/doubling_time)·dna, so the DNA
    copy number is held at its genome set point (dna → genes) over a 30-min doubling
    — replication balancing dilution, not runaway growth. ``dna`` is written only
    here, self-tracked from its seed so no new port is needed."""
    config_schema = {"doubling_time_s": _f(1800.0), "dna_init": _f(1.0)}

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._dna = self.config["dna_init"]   # matches the ENV DNA seed

    def inputs(self):
        return {"dna": "concentration", "genes": "concentration"}

    def outputs(self):
        return {"dna": "concentration"}

    def update(self, state, interval):
        genes = float(state.get("genes", 0.0))
        k = _LN2 / self.config["doubling_time_s"]
        d_dna = (k * genes - k * self._dna) * interval
        self._dna += d_dna
        return {"dna": d_dna}


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
    "Transcription": {"handler": "TranscriptionODE",
                      "config": {"elong_nt_per_s": 45.0, "gene_length_nt": 1000.0,
                                 "mrna_halflife_s": 180.0}},
    "Translation": {"handler": "TranslationODE",
                    "config": {"elong_aa_per_s": 15.0, "protein_length_aa": 300.0,
                               "doubling_time_s": 1800.0, "km_met": 0.5, "km_rib": 0.5}},
    "SubunitAssembly": {"handler": "SubunitAssemblyODE",
                        "config": {"k": 0.2, "doubling_time_s": 1800.0,
                                   "ribosome_init": 0.5}},
    "ReplicationAndRepair": {"handler": "ReplicationAndRepairODE",
                             "config": {"doubling_time_s": 1800.0, "dna_init": 1.0}},
}
