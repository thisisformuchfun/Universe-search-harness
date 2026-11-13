"""Fixed search and vetting criteria.

These numbers were written down before the first whole-catalogue run and are
hashed into every output. They are triage defaults, not validated physical
cuts. Changing one is a reviewed code change: never tune them on the controls
or to move a particular source between tiers.

History
  1  first full run.
  2  after that run and before any result was reported, three changes, each of which makes
     the search or the vetting stricter: (a) ill-conditioned single-precision covariances are
     refused and replaced by a significance-based error, because they invented huge orbits
     for near-circular solutions; (b) a 15% margin on the approximate main-sequence limits;
     (c) the published Shahaf et al. (2023) class probabilities as an independent test,
     because that paper's hierarchical-triple limit is stricter than the approximation here;
     and, from the first manual review of survivors: (d) a hidden main-sequence pair test for
     SB1 orbits; (e) a colour-magnitude position test for the primary; (f) a plausibility
     bound on the implied mass.
"""

from __future__ import annotations

import hashlib
import json

CRITERIA = {
    "version": "survey-criteria-2",
    # ---- find stage -----------------------------------------------------
    "draws": 4096,
    "coarse_draws": 256,  # first pass; rows within refine_fraction_of_cut get the full draw count
    "refine_fraction_of_cut": 0.8,
    "min_correlation_eigenvalue": 1e-4,  # below this the single-precision correlation block is not trusted
    "max_median_drift_factor": 1.5,  # Monte Carlo median f_phot must stay within this factor of the point estimate
    "seed": 20261112,
    "prefilter_point_m2_fraction": 0.5,  # rows whose point estimate is below this fraction of the cut skip Monte Carlo
    "m2_q05_min": 1.25,  # Msun; 5th-percentile minimum dark-companion mass to enter the shortlist
    "bh_range_m2_q05": 3.0,  # Msun; label only ("black-hole mass range IF dark and IF the orbit is right")
    "sb1_requires_m2_above_m1": True,  # an unseen companion lighter than a main-sequence primary is unremarkable
    "max_m1_fraction_error_floor": 0.05,
    # ---- vetting --------------------------------------------------------
    "significance_fail": 10.0,
    "significance_warn": 20.0,
    "goodness_of_fit_warn": 5.0,
    "goodness_of_fit_fail": 15.0,
    "dr3_baseline_days": 1038.0,  # 34 months of DR3 astrometry
    "period_error_fraction_warn": 0.1,
    "parallax_over_error_fail": 5.0,
    "parallax_over_error_warn": 10.0,
    "ipd_frac_multi_peak_warn": 2.0,
    "ipd_frac_multi_peak_fail": 10.0,
    "ipd_gof_harmonic_amplitude_warn": 0.1,
    "neighbour_radius_arcsec": 2.0,
    "neighbour_delta_g_fail": 4.0,  # a neighbour within the radius and less than this many mag fainter
    "bp_rp_excess_tolerance": 0.15,  # allowed excess above the Riello et al. (2021) locus
    "rv_min_transits": 8,
    "rv_ratio_low_fail": 0.25,  # observed RV range / range implied by the astrometric orbit
    "rv_ratio_high_warn": 2.5,
    "amrf_limit_margin": 1.15,  # the approximate mass-luminosity relation is only trusted to this factor
    "independent_class3_fail_below": 0.5,  # Shahaf et al. (2023) class-III probability
    "independent_class3_warn_below": 0.9,
    "implausible_m2_fail": 150.0,  # Msun; above any known stellar black hole: a bad orbit is far more likely
    "implausible_m2_warn": 40.0,
    "cmd_redder_than_ms_warn": 0.2,  # mag in BP-RP at fixed absolute magnitude
    "hidden_pair_flux_fail": 0.3,  # a main-sequence pair with the required total mass adds less than this fraction of light
    "astrospectro_dark_ratio_fail": 0.6,  # photocentre / spectroscopic primary orbit size
    "astrospectro_dark_ratio_warn": 0.85,
    "sb1_rv_ratio_low_fail": 0.4,
    "sb1_min_good_rv_obs": 10,
    "sb1_short_period_warn_days": 3.0,
    "evolved_logg_max": 3.6,
    "vet_after_new_candidates": 25,
}


def criteria_hash() -> str:
    return hashlib.sha256(json.dumps(CRITERIA, sort_keys=True).encode()).hexdigest()
