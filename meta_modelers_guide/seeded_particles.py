"""SeededBrownianMovement -- a reproducible drop-in for spatio-flux's
``BrownianMovement`` (used by the ``disintegration-spatial`` flagship to
scatter shed debris particles).

Why this exists: upstream ``spatio_flux.processes.particles.BrownianMovement``
draws its per-step Brownian displacements from NumPy's *global* RNG
(``np.random.normal``) and its ``config_schema`` has no ``seed`` field, so its
scatter is not reproducible and a ``seed`` placed in the composite config is
silently ignored. Rather than fork/duplicate the parent's step logic (bounds
clamping, advection, absolute-position emission), this subclass simply pins the
global RNG stream *for the duration of each* ``update``: it swaps in a private
``RandomState`` seeded from ``config["seed"]``, calls the unchanged parent
``update``, then restores the caller's global RNG state so nothing outside this
process is perturbed. The private stream is carried forward across ticks, so a
whole run is deterministic given the seed.

Registered by ``meta_modelers_guide.core`` under its bare class name, so a
composite addresses it as ``local:SeededBrownianMovement``.
"""
from __future__ import annotations

import numpy as np
from spatio_flux.processes.particles import BrownianMovement


class SeededBrownianMovement(BrownianMovement):
    """``BrownianMovement`` with a reproducible per-process RNG stream.

    Behaviour is identical to the parent except that the Brownian steps are
    drawn from a private stream seeded by ``config["seed"]`` (default 1),
    making the debris scatter deterministic. Restoring the global RNG state
    after each ``update`` keeps this process side-effect-free on the shared
    NumPy global RNG.
    """

    config_schema = {
        **BrownianMovement.config_schema,
        "seed": {"_type": "integer", "_default": 1},
    }

    def initialize(self, config):
        super().initialize(config)
        # A private RandomState seeded from config; we persist only its opaque
        # state tuple and re-install it around each parent update() call.
        self._rng_state = np.random.RandomState(int(config.get("seed", 1))).get_state()

    def update(self, state, interval):
        saved = np.random.get_state()
        np.random.set_state(self._rng_state)
        try:
            return super().update(state, interval)
        finally:
            # Carry our private stream forward, then hand the global RNG back
            # exactly as we found it.
            self._rng_state = np.random.get_state()
            np.random.set_state(saved)
