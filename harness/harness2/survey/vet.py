"""Vet stage: an automated battery that tries to knock each shortlisted anomaly down.

Every test returns PASS, WARN, FAIL or NA with the numbers it used. The battery
is adversarial by design: it looks for an ordinary explanation (bad orbit, blend,
luminous companion, hierarchical triple, already published) and a candidate only
keeps the top tier if none is found and every core test could actually be run.

The top tier is still a *held anomaly*. Nothing here can release a candidate or
call it a black hole, and "no literature match" is recorded as exactly that: it
is never evidence of novelty.
"""

from __future__ import annotations

import math

import numpy as np

from harness2.survey import evidence as ev
from harness2.survey import physics as ph
from harness2.survey.criteria import CRITERIA
from harness2.survey.net import NetError

TIERS = (
    "EXCLUDED_PUBLISHED_PRIOR",
    "HELD_FAILED_VETTING",
    "HELD_WITH_CAVEATS",
    "HELD_SURVIVED_AUTOMATED_VETTING",
)
TIER_MEANING = {
    "EXCLUDED_PUBLISHED_PRIOR": "Already in a compact-companion catalogue or discussed in that context. Not new.",
    "HELD_FAILED_VETTING": "At least one test found an ordinary explanation or a quality failure. Held.",
    "HELD_WITH_CAVEATS": "No failure, but at least one warning or a core test that could not be run. Held.",
    "HELD_SURVIVED_AUTOMATED_VETTING": "No ordinary explanation found by these automated checks. Still a held anomaly "
    "that needs independent orbit validation and human review. Not a discovery.",
}
CORE_TESTS = {
    "astrometric": ("orbit_significance", "ms_triple_excluded", "blend_image_parameters", "blend_neighbours", "prior_literature"),
    "spectroscopic": ("orbit_significance", "sb1_rv_range_consistency", "sb1_hidden_pair", "blend_neighbours", "prior_literature"),
}


def _t(name, result, detail, **values):
    return {"test": name, "result": result, "detail": detail, "values": values}


def _ok(x):
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


def excess_locus(bp_rp):
    """Expected BP/RP flux excess for an isolated source (Riello et al. 2021, table 2)."""
    x = bp_rp
    if x < 0.5:
        return 1.154360 + 0.033772 * x + 0.032277 * x * x
    if x < 4.0:
        return 1.162004 + 0.011464 * x + 0.049255 * x * x - 0.005879 * x**3
    return 1.057572 + 0.140537 * x


# ------------------------------------------------------------ shared tests


def t_significance(c):
    s = c["orbit"]["significance"]
    if not _ok(s):
        return _t("orbit_significance", "NA", "no significance published", significance=s)
    if s < CRITERIA["significance_fail"]:
        return _t("orbit_significance", "FAIL", "orbit significance below the reliability floor", significance=s)
    if s < CRITERIA["significance_warn"]:
        return _t("orbit_significance", "WARN", "orbit significance is modest", significance=s)
    return _t("orbit_significance", "PASS", "orbit is highly significant", significance=s)


def t_goodness_of_fit(c):
    g = c["orbit"]["goodness_of_fit"]
    if not _ok(g):
        return _t("orbit_goodness_of_fit", "NA", "no goodness of fit published", goodness_of_fit=g)
    if g > CRITERIA["goodness_of_fit_fail"]:
        return _t("orbit_goodness_of_fit", "FAIL", "the orbit model fits the data poorly", goodness_of_fit=g)
    if g > CRITERIA["goodness_of_fit_warn"]:
        return _t("orbit_goodness_of_fit", "WARN", "the orbit model leaves excess residuals", goodness_of_fit=g)
    return _t("orbit_goodness_of_fit", "PASS", "residuals consistent with the orbit model", goodness_of_fit=g)


def t_period(c):
    p, pe = c["orbit"]["period"], c["orbit"]["period_error"]
    frac = pe / p if _ok(pe) and _ok(p) and p > 0 else None
    if p > CRITERIA["dr3_baseline_days"]:
        return _t("period_coverage", "WARN", "period longer than the DR3 time baseline: orbit not fully covered", period=p, period_error_fraction=frac)
    if frac is not None and frac > CRITERIA["period_error_fraction_warn"]:
        return _t("period_coverage", "WARN", "period is poorly constrained", period=p, period_error_fraction=frac)
    return _t("period_coverage", "PASS", "period within the baseline and well constrained", period=p, period_error_fraction=frac)


def t_solution_type(c):
    typ = c["nss_solution_type"]
    if "Alternative" in typ or "Targeted" in typ:
        return _t("solution_type", "WARN", "alternative or targeted-search solution, processed outside the main orbit pipeline", nss_solution_type=typ)
    return _t("solution_type", "PASS", "standard pipeline solution", nss_solution_type=typ)


def t_covariance(c):
    m = c["covariance_method"]
    if m == "full_published_covariance":
        return _t("covariance_propagation", "PASS", "full published covariance propagated", method=m, draws=c.get("draws"))
    if c["channel"] == "spectroscopic":
        return _t("covariance_propagation", "NA", "this engine propagates SB1 errors without correlations", method=m, draws=c.get("draws"))
    if m == "significance_based_orbit_size_error":
        return _t(
            "covariance_propagation",
            "WARN",
            "published covariance is ill-conditioned for this orbit; orbit-size error taken from the published significance",
            method=m,
            draws=c.get("draws"),
        )
    return _t("covariance_propagation", "WARN", "correlations unavailable: uncertainties are approximate", method=m, draws=c.get("draws"))


def t_primary(c):
    p = c["primary"]
    if p["evolved_primary"]:
        return _t("primary_mass_basis", "WARN", "primary looks evolved: main-sequence reasoning and the mass estimate are unreliable", **p)
    if p["m1_source"] == "gaia_dr3_binary_masses":
        return _t("primary_mass_basis", "PASS", "primary mass from Gaia DR3 binary_masses", **p)
    return _t("primary_mass_basis", "WARN", "primary mass from an approximate relation", **p)


def t_mass_plausibility(c):
    m = c["m2_dark"]["q05"]
    if m > CRITERIA["implausible_m2_fail"]:
        return _t("mass_plausibility", "FAIL", "implied mass exceeds any known stellar black hole: the orbit solution is far more likely wrong", m2_dark_q05=m)
    if m > CRITERIA["implausible_m2_warn"]:
        return _t("mass_plausibility", "WARN", "implied mass is extreme: a wrong orbit is the likelier explanation", m2_dark_q05=m)
    return _t("mass_plausibility", "PASS", "implied mass is within the range of known compact objects", m2_dark_q05=m)


def t_cmd_position(c):
    x = c["context"]
    if not _ok(x["abs_g0"]) or not _ok(x["bp_rp0"]):
        return _t("primary_cmd_position", "NA", "no absolute magnitude or colour")
    expected = ph.ms_colour_at_abs_g(x["abs_g0"])
    offset = x["bp_rp0"] - expected
    vals = dict(abs_g0=x["abs_g0"], bp_rp0=x["bp_rp0"], ms_colour=expected, offset=offset, extinction_applied=_ok(x["ag_gspphot"]))
    if offset > CRITERIA["cmd_redder_than_ms_warn"]:
        why = "evolved primary" if vals["extinction_applied"] else "evolved primary or uncorrected reddening (no extinction estimate)"
        return _t("primary_cmd_position", "WARN", "primary is redder than the main sequence at its luminosity: " + why, **vals)
    return _t("primary_cmd_position", "PASS", "primary lies on the main sequence within tolerance", **vals)


def t_sb1_hidden_pair(c):
    """Could two fainter main-sequence stars with the required total mass hide in the primary's light?"""
    x = c["context"]
    if not _ok(x["abs_g0"]):
        return _t("sb1_hidden_pair", "NA", "no absolute magnitude for the primary")
    m = c["m2_dark"]["q05"]
    ratio = float(2 * 10 ** (-0.4 * (ph.ms_abs_g(m / 2) - x["abs_g0"])))
    vals = dict(m2_dark_q05=m, each_star_mass=m / 2, pair_to_system_flux=ratio)
    if ratio < CRITERIA["hidden_pair_flux_fail"]:
        return _t("sb1_hidden_pair", "FAIL", "a close pair of fainter main-sequence stars supplies the mass and stays hidden: ordinary triple", **vals)
    if ratio < 1.0:
        return _t("sb1_hidden_pair", "WARN", "a main-sequence pair with this mass would be faint but possibly detectable", **vals)
    return _t("sb1_hidden_pair", "PASS", "a main-sequence pair with this mass would outshine the primary", **vals)


def t_blend_image(c):
    x = c["context"]
    frac, amp, dup = x["ipd_frac_multi_peak"], x["ipd_gof_harmonic_amplitude"], c["duplicated_source"]
    vals = dict(ipd_frac_multi_peak=frac, ipd_gof_harmonic_amplitude=amp, duplicated_source=dup)
    if not _ok(frac) or not _ok(amp):
        return _t("blend_image_parameters", "NA", "image parameters unavailable", **vals)
    if frac > CRITERIA["ipd_frac_multi_peak_fail"]:
        return _t("blend_image_parameters", "FAIL", "many transits show a double peak: resolved blend", **vals)
    if frac > CRITERIA["ipd_frac_multi_peak_warn"] or amp > CRITERIA["ipd_gof_harmonic_amplitude_warn"] or dup:
        return _t("blend_image_parameters", "WARN", "image parameters hint at a second source", **vals)
    return _t("blend_image_parameters", "PASS", "image parameters consistent with one source", **vals)


def t_neighbours(c, neighbours):
    if neighbours is None:
        return _t("blend_neighbours", "NA", "neighbour query unavailable")
    close = [n for n in neighbours if _ok(n["sep_arcsec"])]
    bright = [n for n in close if n["delta_g"] is None or n["delta_g"] < CRITERIA["neighbour_delta_g_fail"]]
    vals = dict(radius_arcsec=CRITERIA["neighbour_radius_arcsec"], neighbours=close[:5])
    if bright:
        return _t("blend_neighbours", "FAIL", "a comparably bright Gaia source lies inside the blend radius", **vals)
    if close:
        return _t("blend_neighbours", "WARN", "a faint Gaia source lies inside the blend radius", **vals)
    return _t("blend_neighbours", "PASS", "no other Gaia source inside the blend radius", **vals)


def t_colour_excess(c):
    x = c["context"]
    if not _ok(x["bp_rp"]) or not _ok(x["phot_bp_rp_excess_factor"]):
        return _t("colour_excess", "NA", "BP/RP photometry unavailable")
    cstar = x["phot_bp_rp_excess_factor"] - excess_locus(x["bp_rp"])
    if cstar > CRITERIA["bp_rp_excess_tolerance"]:
        return _t("colour_excess", "WARN", "BP/RP flux excess above the single-source locus: possible contamination", c_star=cstar)
    return _t("colour_excess", "PASS", "BP/RP flux excess consistent with one source", c_star=cstar)


def t_variability(c, membership):
    if membership is None:
        return _t("gaia_variability_tables", "NA", "membership queries unavailable")
    sid = c["source_id"]
    hits = sorted(t for t, ids in membership.items() if sid in ids)
    if "vari_eclipsing_binary" in hits:
        res = "FAIL" if c["channel"] == "spectroscopic" else "WARN"
        return _t("gaia_variability_tables", res, "Gaia classifies this source as an eclipsing binary: a stellar companion or inner pair is likely", tables=hits)
    if "nss_acceleration_astro" in hits or "nss_non_linear_spectro" in hits:
        return _t("gaia_variability_tables", "WARN", "Gaia also publishes a competing non-orbital solution for this source", tables=hits)
    return _t("gaia_variability_tables", "PASS", "no conflicting Gaia variability or trend solution", tables=hits)


def t_other_solutions(c, others):
    rows = [o for o in others if o["nss_solution_type"] != c["nss_solution_type"]]
    if not rows:
        return _t("other_nss_solutions", "PASS", "single NSS orbit solution for this source", solutions=[])
    p = c["orbit"]["period"]
    clash = [o for o in rows if _ok(o["period"]) and abs(o["period"] - p) / p > 0.1]
    if clash:
        return _t("other_nss_solutions", "WARN", "another NSS solution for this source has a different period", solutions=rows)
    return _t("other_nss_solutions", "PASS", "other NSS solutions agree on the period", solutions=rows)


def t_flame(c, flame):
    if flame is None:
        return _t("flame_evolutionary_stage", "NA", "no FLAME parameters for this source")
    stage = flame.get("evolstage_flame")
    if _ok(stage) and stage > 420 and not c["primary"]["evolved_primary"]:
        return _t("flame_evolutionary_stage", "WARN", "FLAME places the primary beyond the main sequence", **flame)
    return _t("flame_evolutionary_stage", "PASS", "FLAME stage consistent with the primary classification", **flame)


def t_literature(c, lit):
    """lit: {'known': entry|None, 'catalogues': [keys], 'simbad': dict|None, 'checked': [...], 'incomplete': [...]}"""
    reasons = []
    if lit["known"]:
        reasons.append("policy known-object list: " + lit["known"]["status"])
    reasons += ["published catalogue: " + k for k in lit["catalogues"]]
    sb = lit["simbad"]
    if sb:
        if sb.get("compact_otype"):
            reasons.append("SIMBAD object type " + sb["otype"])
        reasons += ["SIMBAD reference " + b for b in sb.get("policy_bibcodes", [])]
        reasons += ["SIMBAD reference in compact-companion context: " + r["bibcode"] for r in sb.get("compact_context_refs", [])[:5]]
    vals = dict(checked=lit["checked"], incomplete=lit["incomplete"], simbad=sb and {k: sb.get(k) for k in ("found", "main_id", "otype", "nbref")}, recent_bibcodes=(sb or {}).get("bibcodes", [])[:8])
    if reasons:
        return _t("prior_literature", "PRIOR", "already published or discussed as a compact-companion candidate", reasons=reasons, **vals)
    if lit["incomplete"]:
        return _t("prior_literature", "NA", "literature check incomplete: " + "; ".join(lit["incomplete"]), **vals)
    return _t(
        "prior_literature",
        "PASS",
        "no match in the sources checked. This is NOT evidence of novelty: the check is a finite list.",
        **vals,
    )


# -------------------------------------------------------- astrometric tests


def t_parallax(c):
    o = c["orbit"]
    snr = o["parallax"] / o["parallax_error"] if _ok(o["parallax_error"]) and o["parallax_error"] > 0 else None
    if snr is None:
        return _t("parallax_quality", "NA", "no parallax error")
    if snr < CRITERIA["parallax_over_error_fail"]:
        return _t("parallax_quality", "FAIL", "distance too uncertain for a mass scale", parallax_over_error=snr)
    if snr < CRITERIA["parallax_over_error_warn"]:
        return _t("parallax_quality", "WARN", "distance is uncertain", parallax_over_error=snr)
    return _t("parallax_quality", "PASS", "distance well measured", parallax_over_error=snr)


def t_ms_alternatives(c):
    a = c["amrf"]["q05"]
    single, triple = c["amrf_limit_single_ms"], c["amrf_limit_ms_triple"]
    vals = dict(amrf_q05=a, amrf_q50=c["amrf"]["q50"], limit_single_ms=single, limit_ms_triple=triple)
    out = []
    if c["primary"]["evolved_primary"]:
        note = "main-sequence limits do not apply to an evolved primary"
        return [_t("ms_companion_excluded", "NA", note, **vals), _t("ms_triple_excluded", "NA", note, **vals)]
    out.append(
        _t("ms_companion_excluded", "PASS", "photocentre orbit too large for one main-sequence companion", **vals)
        if a > single
        else _t("ms_companion_excluded", "FAIL", "a single main-sequence companion can reproduce the photocentre orbit", **vals)
    )
    margin = CRITERIA["amrf_limit_margin"]
    out.append(
        _t("ms_triple_excluded", "PASS", "photocentre orbit too large for a close main-sequence pair", **vals)
        if a > margin * triple
        else _t("ms_triple_excluded", "WARN", "above the close main-sequence pair limit only within the uncertainty of the approximate mass-luminosity relation", margin=margin, **vals)
        if a > triple
        else _t("ms_triple_excluded", "FAIL", "a hierarchical triple with a close main-sequence pair can reproduce the photocentre orbit", **vals)
    )
    return out


def t_independent_class(c, classes):
    """Shahaf et al. (2023) classified about 101,000 DR3 astrometric orbits with their own
    mass-luminosity relation. Disagreement with that published result is a failure here."""
    name = "independent_amrf_classification"
    if classes is None:
        return _t(name, "NA", "published classification unavailable")
    entry = classes.get(c["source_id"])
    if entry is None or entry["p_class3"] is None:
        return _t(name, "NA", "source is not in the published classified sample", source=ev.SHAHAF_TABLE["bibcode"])
    vals = dict(entry, source=ev.SHAHAF_TABLE["bibcode"])
    if entry["p_class3"] < CRITERIA["independent_class3_fail_below"]:
        return _t(name, "FAIL", "the published classification finds a luminous companion or triple more likely than a compact one", **vals)
    if entry["p_class3"] < CRITERIA["independent_class3_warn_below"]:
        return _t(name, "WARN", "the published classification does not firmly exclude a luminous triple", **vals)
    return _t(name, "PASS", "the published classification also excludes luminous companions", **vals)


def t_rv_astrometric(c):
    x, o = c["context"], c["orbit"]
    k1 = c["k1_pred_kms"]["q50"]
    amp, n = x["rv_amplitude_robust"], x["rv_nb_transits"]
    if not _ok(amp) or not _ok(n) or n < CRITERIA["rv_min_transits"] or not _ok(k1) or k1 <= 0:
        return _t("rv_amplitude_consistency", "NA", "too few Gaia RV transits to test the astrometric orbit", rv_nb_transits=n, rv_amplitude_robust=amp, k1_pred_kms=k1)
    ratio = amp / (2 * k1)
    vals = dict(rv_amplitude_robust=amp, predicted_full_range_kms=2 * k1, ratio=ratio, rv_nb_transits=n)
    covered = o["period"] <= CRITERIA["dr3_baseline_days"] and (o["eccentricity"] or 0) < 0.6
    if ratio < CRITERIA["rv_ratio_low_fail"]:
        if covered:
            return _t("rv_amplitude_consistency", "FAIL", "Gaia's own radial velocities move far less than the astrometric orbit requires", **vals)
        return _t("rv_amplitude_consistency", "WARN", "radial velocities move less than predicted, but the orbit is eccentric or not fully covered", **vals)
    if ratio > CRITERIA["rv_ratio_high_warn"]:
        return _t("rv_amplitude_consistency", "WARN", "radial velocities move more than this orbit explains: possible inner binary or wrong orbit", **vals)
    return _t("rv_amplitude_consistency", "PASS", "Gaia radial-velocity range is consistent with the astrometric orbit", **vals)


def t_astrospectro(c):
    r = c.get("astrospectro_dark_ratio")
    if not r or not _ok(r["q50"]):
        return _t("astrospectro_darkness", "NA", "not a combined astrometric and spectroscopic solution")
    vals = dict(photocentre_over_primary_orbit=r)
    if r["q95"] < CRITERIA["astrospectro_dark_ratio_fail"]:
        return _t("astrospectro_darkness", "FAIL", "photocentre orbit much smaller than the primary's: the companion contributes light", **vals)
    if r["q50"] < CRITERIA["astrospectro_dark_ratio_warn"]:
        return _t("astrospectro_darkness", "WARN", "photocentre orbit smaller than the primary's: companion may contribute light", **vals)
    return _t("astrospectro_darkness", "PASS", "photocentre follows the primary: no sign of companion light", **vals)


# ------------------------------------------------------ spectroscopic tests


def t_sb1_rv_range(c):
    x, o = c["context"], c["orbit"]
    amp, k = x["rv_amplitude_robust"], o["semi_amplitude_primary"]
    if not _ok(amp) or not _ok(k) or k <= 0:
        return _t("sb1_rv_range_consistency", "NA", "no robust RV amplitude in gaia_source")
    ratio = amp / (2 * k)
    vals = dict(rv_amplitude_robust=amp, orbit_full_range_kms=2 * k, ratio=ratio)
    if ratio < CRITERIA["sb1_rv_ratio_low_fail"] and (o["eccentricity"] or 0) < 0.6:
        return _t("sb1_rv_range_consistency", "FAIL", "fitted semi-amplitude far exceeds the observed RV range: likely spurious orbit", **vals)
    if ratio > CRITERIA["rv_ratio_high_warn"]:
        return _t("sb1_rv_range_consistency", "WARN", "observed RV range exceeds the fitted orbit", **vals)
    return _t("sb1_rv_range_consistency", "PASS", "observed RV range matches the fitted orbit", **vals)


def t_sb1_quality(c):
    x, o = c["context"], c["orbit"]
    out = []
    n = o["rv_n_good_obs_primary"]
    out.append(
        _t("sb1_sampling", "PASS", "enough good RV epochs", rv_n_good_obs_primary=n)
        if _ok(n) and n >= CRITERIA["sb1_min_good_rv_obs"]
        else _t("sb1_sampling", "WARN", "few good RV epochs", rv_n_good_obs_primary=n)
    )
    notes = []
    if o["period"] < CRITERIA["sb1_short_period_warn_days"]:
        notes.append("short period: contact, ellipsoidal or mass-transfer binaries are common here")
    if _ok(x["vbroad"]) and x["vbroad"] > 60:
        notes.append("broad lines: Gaia RVs are less reliable")
    if _ok(x["teff_gspphot"]) and x["teff_gspphot"] > 7500:
        notes.append("hot primary: Gaia RVs are less reliable")
    if c["phot_variable_flag"] == "VARIABLE":
        notes.append("photometrically variable")
    vals = dict(period=o["period"], vbroad=x["vbroad"], teff_gspphot=x["teff_gspphot"], phot_variable_flag=c["phot_variable_flag"])
    out.append(_t("sb1_known_failure_modes", "WARN" if notes else "PASS", "; ".join(notes) or "none of the common SB1 failure modes apply", **vals))
    return out


# ------------------------------------------------------------------ driver


def gather(candidates, fetcher, catalogue_specs, release="gaiadr3", catalogue_cache=None):
    """All remote evidence for a batch, with per-source failures recorded, not hidden."""
    ids = sorted({c["source_id"] for c in candidates}, key=int)
    pack = {"shahaf_classes": None, "positions": None, "neighbours": None, "membership": None, "flame": None, "simbad": None, "catalogues": {}, "errors": {}, "provenance": {}}
    if not ids:
        return pack

    def attempt(name, fn):
        try:
            value, prov = fn()
            pack[name] = value
            pack["provenance"][name] = prov
        except NetError as exc:
            pack["errors"][name] = str(exc)

    cache = {} if catalogue_cache is None else catalogue_cache
    attempt("schema", lambda: (True, ev.check_schema(fetcher, release)))
    attempt("positions", lambda: ev.gaia_positions(fetcher, ids, release))
    if pack.get("positions"):
        attempt("neighbours", lambda: ev.gaia_neighbours(fetcher, pack["positions"], CRITERIA["neighbour_radius_arcsec"], release))
    attempt("membership", lambda: ev.gaia_membership(fetcher, ids, release))
    attempt("flame", lambda: ev.gaia_flame(fetcher, ids, release))
    attempt("simbad", lambda: ev.simbad(fetcher, ids))
    if "shahaf_classes" not in cache:
        attempt("shahaf_classes", lambda: ev.shahaf_classification(fetcher))
        if pack.get("shahaf_classes") is not None:
            cache["shahaf_classes"] = pack["shahaf_classes"]
    pack["shahaf_classes"] = cache.get("shahaf_classes")
    for spec in catalogue_specs:
        try:
            if spec["key"] not in cache:
                cache[spec["key"]] = ev.vizier_catalog_ids(fetcher, spec)
            members, prov = cache[spec["key"]]
            pack["catalogues"][spec["key"]] = members
            pack["provenance"]["catalogue:" + spec["key"]] = prov
        except NetError as exc:
            pack["errors"]["catalogue:" + spec["key"]] = str(exc)
    return pack


def vet_one(c, pack, known, bundled_members, policy_bibcodes, nss_index, catalogue_specs):
    sid = c["source_id"]
    tests = [t_significance(c), t_goodness_of_fit(c), t_period(c), t_covariance(c), t_primary(c), t_cmd_position(c), t_mass_plausibility(c)]
    if c["channel"] == "astrometric":
        tests += [
            t_solution_type(c),
            t_parallax(c),
            *t_ms_alternatives(c),
            t_independent_class(c, pack.get("shahaf_classes")),
            t_rv_astrometric(c),
            t_astrospectro(c),
        ]
    else:
        tests += [t_sb1_rv_range(c), t_sb1_hidden_pair(c), *t_sb1_quality(c)]
    tests += [
        t_blend_image(c),
        t_neighbours(c, None if pack["neighbours"] is None else pack["neighbours"].get(sid, [])),
        t_colour_excess(c),
        t_variability(c, pack["membership"]),
        t_other_solutions(c, nss_index.get(sid, [])),
        t_flame(c, None if pack["flame"] is None else pack["flame"].get(sid)),
    ]
    sb = None if pack["simbad"] is None else dict(pack["simbad"].get(sid, {}))
    if sb:
        sb["policy_bibcodes"] = [b for b in sb.get("bibcodes", []) if b in policy_bibcodes]
    compact_keys = {s["key"] for s in catalogue_specs if s.get("kind") == "compact_candidates"}
    cats = [k for k, members in bundled_members.items() if sid in members]
    cats += [k for k, members in pack["catalogues"].items() if k in compact_keys and sid in members and k not in cats]
    checked = ["policy/known_objects.json", *sorted(bundled_members), *sorted(pack["catalogues"])]
    incomplete = []
    if pack["simbad"] is None:
        incomplete.append("SIMBAD unavailable")
    else:
        checked.append("SIMBAD identifiers and bibliography")
    incomplete += [k + " unavailable" for k in pack["errors"] if k.startswith("catalogue:")]
    lit = t_literature(c, {"known": known.get(sid), "catalogues": cats, "simbad": sb, "checked": checked, "incomplete": incomplete})
    notes = [k for k, members in pack["catalogues"].items() if k not in compact_keys and sid in members]
    physics = classify(tests, c["channel"], literature=None)
    return {
        "candidate_id": c["candidate_id"],
        "source_id": sid,
        "channel": c["channel"],
        "position_deg": None if not pack.get("positions") else pack["positions"].get(sid),
        "tier": classify(tests, c["channel"], literature=lit),
        "physics_tier_ignoring_literature": physics,
        "tests": tests + [lit],
        "also_listed_in": notes,
        "counts": {r: sum(t["result"] == r for t in tests) for r in ("PASS", "WARN", "FAIL", "NA")},
        "evidence_incomplete": sorted(pack["errors"]),
        "release_enabled": False,
        "discovery_claim": False,
    }


def classify(tests, channel, literature):
    if literature is not None and literature["result"] == "PRIOR":
        return "EXCLUDED_PUBLISHED_PRIOR"
    results = {t["test"]: t["result"] for t in tests}
    if literature is not None:
        results["prior_literature"] = literature["result"]
    if "FAIL" in results.values():
        return "HELD_FAILED_VETTING"
    core = [t for t in CORE_TESTS[channel] if literature is not None or t != "prior_literature"]
    core_missing = [t for t in core if results.get(t) == "NA"]
    # An evolved primary makes the main-sequence triple test inapplicable; that is a caveat, not a pass.
    if "WARN" in results.values() or core_missing:
        return "HELD_WITH_CAVEATS"
    return "HELD_SURVIVED_AUTOMATED_VETTING"


def nss_solution_index(table, source_ids):
    """Every NSS solution for the given sources, from the local bulk table."""
    wanted = np.array(sorted({int(s) for s in source_ids}), dtype=np.int64)
    rows = np.flatnonzero(np.isin(table["source_id"], wanted))
    out = {}
    for i in rows:
        p = float(table["period"][i])
        out.setdefault(str(int(table["source_id"][i])), []).append(
            {"nss_solution_type": str(table["nss_solution_type"][i]), "period": p if math.isfinite(p) else None}
        )
    return out


def vet_batch(
    candidates, table, fetcher, catalogue_specs, known, bundled_members, policy_bibcodes, release="gaiadr3", catalogue_cache=None
):
    pack = gather(candidates, fetcher, catalogue_specs, release, catalogue_cache)
    index = nss_solution_index(table, [c["source_id"] for c in candidates])
    reports = [vet_one(c, pack, known, bundled_members, policy_bibcodes, index, catalogue_specs) for c in candidates]
    summary = {"evidence_errors": pack["errors"], "evidence_provenance": pack["provenance"]}
    return reports, summary
