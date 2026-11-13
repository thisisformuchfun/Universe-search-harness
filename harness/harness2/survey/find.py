"""Find stage: vectorized search channels over the whole NSS table.

Two independent channels look for the same thing in different measurements:

  astrometric    photocentre orbits (Orbital family, AstroSpectroSB1)
  spectroscopic  single-lined RV orbits (SB1, SB1C)

Each computes, with catalogue covariance propagated by Monte Carlo, the minimum
companion mass required if the companion is dark. Rows whose 5th percentile
exceeds the fixed cut become *shortlisted anomalies*. Nothing here is a
detection; the vet stage exists to knock these down.
"""

from __future__ import annotations

import time

import numpy as np

from harness2.survey import physics as ph
from harness2.survey.context import lookup
from harness2.survey.criteria import CRITERIA

ASTRO_WANTED = ("parallax", "a_thiele_innes", "b_thiele_innes", "f_thiele_innes", "g_thiele_innes", "eccentricity", "period")
SPECTRO_EXTRA = ("c_thiele_innes", "h_thiele_innes")
SB1_WANTED = ("semi_amplitude_primary", "period", "eccentricity")
CHUNK_ROWS = 1024


def attach_context(table: dict, ctx: dict) -> dict:
    """Per-row primary mass and CMD quantities for any NSS selection.

    Primary mass, in order of preference:
      1. Gaia DR3 binary_masses m1 (published, main-sequence primaries only)
      2. main-sequence relation from the dereddened absolute G magnitude (approximate)
      3. a broad prior for evolved primaries, where neither applies
    """
    sid = table["source_id"]
    src, masses = ctx["source"], ctx["masses"]
    pos, found = lookup(src["source_id"], sid)
    out = {name: np.where(found, src[name][pos], np.nan) for name in src if src[name].dtype.kind == "f"}
    out["duplicated_source"] = np.where(found, src["duplicated_source"][pos], False)
    out["phot_variable_flag"] = np.where(found, src["phot_variable_flag"][pos], "")
    out["in_gaia_source_context"] = found
    # Spectroscopic solutions carry no astrometry in the NSS table: use gaia_source there.
    parallax = np.where(np.isfinite(table["parallax"]), table["parallax"], out["parallax"])
    out["parallax_used"] = parallax
    ag = np.where(np.isfinite(out["ag_gspphot"]), out["ag_gspphot"], 0.0)
    ebr = np.where(np.isfinite(out["ebpminrp_gspphot"]), out["ebpminrp_gspphot"], 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        abs_g = out["phot_g_mean_mag"] + 5 * np.log10(np.where(parallax > 0, parallax, np.nan) / 100.0) - ag
    colour = out["bp_rp"] - ebr
    evolved = (out["logg_gspphot"] < CRITERIA["evolved_logg_max"]) | ((colour > 0.85) & (abs_g < 4.5))
    out["abs_g0"], out["bp_rp0"], out["evolved_primary"] = abs_g, colour, evolved

    # binary_masses can hold several rows per source (one per combination method): take the first.
    uniq, first = np.unique(masses["source_id"], return_index=True)
    mpos, mfound = lookup(uniq, sid)
    mi = first[mpos]
    m1_pub = np.where(mfound, masses["m1"][mi], np.nan)
    use_pub = np.isfinite(m1_pub) & (m1_pub > 0)
    m1_ms = ph.ms_mass_from_abs_g(np.where(np.isfinite(abs_g), abs_g, 4.67))
    use_ms = ~use_pub & np.isfinite(abs_g) & ~evolved
    m1 = np.where(use_pub, m1_pub, np.where(use_ms, m1_ms, 1.2))
    sigma = np.where(
        use_pub,
        ph.lognormal_sigma(m1_pub, np.where(mfound, masses["m1_lower"][mi], np.nan), np.where(mfound, masses["m1_upper"][mi], np.nan)),
        np.where(use_ms, 0.2, 0.35),
    )
    out["m1"], out["m1_sigma_frac"] = m1, sigma
    out["m1_source"] = np.where(
        use_pub, "gaia_dr3_binary_masses", np.where(use_ms, "ms_relation_from_abs_g_approx", "broad_prior_evolved_or_no_photometry")
    )
    out["m1_ref"] = np.where(use_pub, masses["m1_ref"][mi], "")
    out["gaia_m2_lower"] = np.where(mfound, masses["m2_lower"][mi], np.nan)
    out["gaia_fluxratio_upper"] = np.where(mfound, masses["fluxratio_upper"][mi], np.nan)
    return out


def _q(backend, a):
    return backend.quantiles(a)[0]


def _count(backend, mask):
    return backend.to_numpy(mask.sum(1) if backend.torch is None else mask.sum(1).double())


def scan_astrometric(table: dict, ctx_cols: dict, backend=None, draws=None, seed=None, m2_cut=None):
    """Returns per-row result arrays for every astrometric solution in `table`."""
    backend = backend or ph.Backend()
    draws = draws or CRITERIA["draws"]
    seed = CRITERIA["seed"] if seed is None else seed
    m2_cut = CRITERIA["m2_q05_min"] if m2_cut is None else m2_cut
    n = len(table["source_id"])
    a0, f, cos_i = ph.photocentre(
        table["a_thiele_innes"], table["b_thiele_innes"], table["f_thiele_innes"], table["g_thiele_innes"], table["parallax"], table["period"]
    )
    usable = np.isfinite(f) & (table["parallax"] > 0) & (table["period"] > 0)
    m1 = ctx_cols["m1"]
    m2_point = np.where(usable, ph.dark_companion_mass(np.where(usable, f, 1.0), m1), np.nan)
    res = {
        "a0_mas": a0,
        "f_phot": f,
        "cos_i": cos_i,
        "m2_dark_point": m2_point,
        "amrf_point": np.where(usable, np.cbrt(np.where(usable, f, 1.0) / m1), np.nan),
        "k1_pred_point": ph.predicted_rv_semi_amplitude(a0, table["parallax"], table["period"], table["eccentricity"], cos_i),
        "covariance_method": np.full(n, "not_run_below_prefilter", dtype="U48"),
    }
    for name in ("f_phot", "m2_dark", "amrf", "k1_pred", "dark_ratio"):
        res[name + "_q"] = np.full((n, 3), np.nan)
    res["invalid_draw_fraction"] = np.full(n, np.nan)
    res["draws_used"] = np.zeros(n, dtype=np.int32)
    todo = usable & (m2_point >= CRITERIA["prefilter_point_m2_fraction"] * m2_cut)
    types = table["nss_solution_type"]
    for typ in np.unique(types[todo]):
        layout = ph.layout_for(str(typ))
        if layout is None:
            continue
        names, _bits = layout
        spectro = typ == "AstroSpectroSB1"
        wanted = ASTRO_WANTED + (SPECTRO_EXTRA if spectro else ())
        rows = np.flatnonzero(todo & (types == typ))
        sub = {k: v[rows] for k, v in table.items()}
        mean, cov, ok = ph.covariance_stack(sub, list(names), list(wanted), CRITERIA["min_correlation_eigenvalue"])
        # Fallback when the published covariance is unusable or ill-conditioned (typical of
        # near-circular orbits, where Thiele-Innes errors dwarf the values and only correlations
        # of +-0.999999 hold the orbit together): take the orbit-size error from the published
        # significance a0/sigma_a0 and treat parallax, period and eccentricity as independent.
        sig = sub["significance"]
        e_err = np.where(np.isfinite(sub["eccentricity_error"]) & (sub["eccentricity_error"] > 0), sub["eccentricity_error"], 1e-6)
        fmean = np.stack([sub["parallax"], a0[rows], sub["eccentricity"], sub["period"]], axis=1)
        ferr = np.stack([sub["parallax_error"], a0[rows] / np.where(sig > 0, sig, np.nan), e_err, sub["period_error"]], axis=1)
        fok = np.isfinite(fmean).all(1) & np.isfinite(ferr).all(1) & (ferr > 0).all(1)
        fcov = np.zeros((len(rows), 4, 4))
        d4 = np.arange(4)
        fcov[:, d4, d4] = np.where(fok[:, None], ferr, 1.0) ** 2
        cos_point = cos_i[rows]
        spec_point = np.sqrt(sub["c_thiele_innes"] ** 2 + sub["h_thiele_innes"] ** 2) if spectro else None
        mode = np.where(ok, 0, np.where(fok, 1, 2))  # 0 full covariance, 1 significance fallback, 2 unavailable
        labels = np.array(["full_published_covariance", "significance_based_orbit_size_error", "unavailable"])

        def monte_carlo(pick, n_draws, tag, full):
            xp = backend.xp

            def one(ci, sl):
                k = pick[sl]
                r = rows[k]
                nan = backend.asarray(np.nan)
                if full:
                    s = ph.draw(mean[k], cov[k], n_draws, ph.seed_for(seed, tag, ci), backend)
                    par, e, P = s[..., 0], s[..., 5], s[..., 6]
                    valid = (par > 0) & (P > 0) & (e >= 0) & (e < 1)
                    a0d, fd, cid = ph.photocentre(
                        s[..., 1], s[..., 2], s[..., 3], s[..., 4], xp.where(valid, par, nan), xp.where(valid, P, nan), xp
                    )
                    a1_spec = xp.sqrt(s[..., 7] ** 2 + s[..., 8] ** 2) if spectro else None
                else:
                    s = ph.draw(fmean[k], fcov[k], n_draws, ph.seed_for(seed, tag + "fallback", ci), backend)
                    par, a0s, e, P = s[..., 0], s[..., 1], s[..., 2], s[..., 3]
                    valid = (par > 0) & (P > 0) & (a0s > 0) & (e < 1)
                    e = xp.clip(e, 0.0, None)
                    a0d = xp.where(valid, a0s, nan)
                    fd = (a0d / par) ** 3 / (P / ph.DAYS_PER_YEAR) ** 2
                    cid = backend.asarray(cos_point[k])[:, None] + 0 * a0d
                    a1_spec = backend.asarray(spec_point[k])[:, None] + 0 * a0d if spectro else None
                zm = backend.randn((len(r), n_draws), ph.seed_for(seed, tag + "m1", ci))
                m1d = backend.asarray(m1[r])[:, None] * xp.exp(backend.asarray(ctx_cols["m1_sigma_frac"][r])[:, None] * zm)
                m2d = ph.dark_companion_mass(xp.where(valid, fd, backend.asarray(1.0)), m1d, xp)
                m2d = xp.where(valid, m2d, nan)
                res["f_phot_q"][r] = _q(backend, fd)
                res["m2_dark_q"][r] = _q(backend, m2d)
                res["amrf_q"][r] = _q(backend, (fd / m1d) ** (1.0 / 3.0))
                k1 = ph.predicted_rv_semi_amplitude(a0d, par, P, xp.where(valid, e, nan), cid, xp)
                res["k1_pred_q"][r] = _q(backend, k1)
                if spectro:
                    sin_i = xp.sqrt(xp.clip(1 - cid * cid, 0.0, None))
                    res["dark_ratio_q"][r] = _q(backend, (a0d / par) * sin_i / a1_spec)
                res["invalid_draw_fraction"][r] = 1 - _count(backend, valid) / n_draws
                res["draws_used"][r] = n_draws

            ph.run_chunks(one, enumerate(ph.chunks(len(pick), max(32, CHUNK_ROWS * 256 // n_draws))), backend)

        # Coarse pass over everything above the prefilter, full draws only near or above the cut.
        coarse = min(draws, CRITERIA["coarse_draws"])
        monte_carlo(np.flatnonzero(mode == 0), coarse, str(typ) + "coarse", True)
        # A Gaussian draw whose median disagrees with the catalogue point estimate is not
        # describing this orbit. Those rows are sent to the fallback as well.
        with np.errstate(invalid="ignore", divide="ignore"):
            drift = np.abs(np.log(res["f_phot_q"][rows, 1] / f[rows]))
        off = (mode == 0) & ~(drift <= np.log(CRITERIA["max_median_drift_factor"]))
        mode[off & fok] = 1
        mode[off & ~fok] = 2
        for name in ("f_phot", "m2_dark", "amrf", "k1_pred", "dark_ratio"):
            res[name + "_q"][rows[mode != 0]] = np.nan
        monte_carlo(np.flatnonzero(mode == 1), coarse, str(typ) + "coarse", False)
        res["covariance_method"][rows] = labels[mode]
        if draws > coarse:
            near = res["m2_dark_q"][rows, 0] >= CRITERIA["refine_fraction_of_cut"] * m2_cut
            monte_carlo(np.flatnonzero(near & (mode == 0)), draws, str(typ), True)
            monte_carlo(np.flatnonzero(near & (mode == 1)), draws, str(typ), False)
    res["shortlisted"] = res["m2_dark_q"][:, 0] >= m2_cut
    return res


def scan_sb1(table: dict, ctx_cols: dict, backend=None, draws=None, seed=None, m2_cut=None):
    backend = backend or ph.Backend()
    draws = draws or CRITERIA["draws"]
    seed = CRITERIA["seed"] if seed is None else seed
    m2_cut = CRITERIA["m2_q05_min"] if m2_cut is None else m2_cut
    n = len(table["source_id"])
    K, P = table["semi_amplitude_primary"], table["period"]
    e = np.where(np.isfinite(table["eccentricity"]), table["eccentricity"], 0.0)  # SB1C: circular by construction
    usable = np.isfinite(K) & np.isfinite(P) & (K > 0) & (P > 0)
    fm = np.where(usable, ph.sb1_mass_function(np.where(usable, K, 1.0), np.where(usable, P, 1.0), e), np.nan)
    m1 = ctx_cols["m1"]
    m2_point = np.where(usable, ph.dark_companion_mass(np.where(usable, fm, 1.0), m1), np.nan)
    res = {
        "f_spec": fm,
        "m2_dark_point": m2_point,
        "covariance_method": np.full(n, "not_run_below_prefilter", dtype="U48"),
        "f_spec_q": np.full((n, 3), np.nan),
        "m2_dark_q": np.full((n, 3), np.nan),
        "invalid_draw_fraction": np.full(n, np.nan),
        "draws_used": np.zeros(n, dtype=np.int32),
    }
    todo = np.flatnonzero(usable & (m2_point >= CRITERIA["prefilter_point_m2_fraction"] * m2_cut))
    e_err = np.where(np.isfinite(table["eccentricity_error"]) & (table["eccentricity_error"] > 0), table["eccentricity_error"], 1e-6)
    sub = {k: v[todo] for k, v in table.items() if k != "corr_vec"}
    sub["eccentricity"], sub["eccentricity_error"] = e[todo], e_err[todo]
    mean, cov, ok = ph.diagonal_stack(sub, list(SB1_WANTED))
    res["covariance_method"][todo] = np.where(ok, "diagonal_errors_no_correlations", "unavailable")
    rows, mean, cov = todo[ok], mean[ok], cov[ok]
    xp = backend.xp

    def monte_carlo(pick, n_draws, tag):
        def one(ci, sl):
            k = pick[sl]
            r = rows[k]
            s = ph.draw(mean[k], cov[k], n_draws, ph.seed_for(seed, tag, ci), backend)
            Kd, Pd, ed = s[..., 0], s[..., 1], s[..., 2]
            valid = (Kd > 0) & (Pd > 0) & (ed < 1)
            nan = backend.asarray(np.nan)
            fd = xp.where(valid, ph.sb1_mass_function(Kd, Pd, xp.clip(ed, 0.0, None), xp), nan)
            zm = backend.randn((len(r), n_draws), ph.seed_for(seed, tag + "m1", ci))
            m1d = backend.asarray(m1[r])[:, None] * xp.exp(backend.asarray(ctx_cols["m1_sigma_frac"][r])[:, None] * zm)
            m2d = xp.where(valid, ph.dark_companion_mass(xp.where(valid, fd, backend.asarray(1.0)), m1d, xp), nan)
            res["f_spec_q"][r] = _q(backend, fd)
            res["m2_dark_q"][r] = _q(backend, m2d)
            res["invalid_draw_fraction"][r] = 1 - _count(backend, valid) / n_draws
            res["draws_used"][r] = n_draws

        ph.run_chunks(one, enumerate(ph.chunks(len(pick), max(32, CHUNK_ROWS * 256 // n_draws))), backend)

    coarse = min(draws, CRITERIA["coarse_draws"])
    monte_carlo(np.arange(len(rows)), coarse, "SB1coarse")
    if draws > coarse:
        monte_carlo(np.flatnonzero(res["m2_dark_q"][rows, 0] >= CRITERIA["refine_fraction_of_cut"] * m2_cut), draws, "SB1")
    short = res["m2_dark_q"][:, 0] >= m2_cut
    if CRITERIA["sb1_requires_m2_above_m1"]:
        short &= res["m2_dark_q"][:, 0] > m1
    res["shortlisted"] = short
    return res


def _num(x):
    x = float(x)
    return x if np.isfinite(x) else None


def _triple(q):
    return {"q05": _num(q[0]), "q50": _num(q[1]), "q95": _num(q[2])}


CONTEXT_FIELDS = (
    "parallax_used",
    "phot_g_mean_mag",
    "bp_rp",
    "abs_g0",
    "bp_rp0",
    "ruwe",
    "ipd_frac_multi_peak",
    "ipd_gof_harmonic_amplitude",
    "phot_bp_rp_excess_factor",
    "radial_velocity",
    "radial_velocity_error",
    "rv_nb_transits",
    "rv_amplitude_robust",
    "rv_chisq_pvalue",
    "rv_renormalised_gof",
    "teff_gspphot",
    "logg_gspphot",
    "ag_gspphot",
    "grvs_mag",
    "vbroad",
    "l",
    "b",
)
ORBIT_FIELDS = (
    "ra",
    "dec",
    "parallax",
    "parallax_error",
    "period",
    "period_error",
    "eccentricity",
    "eccentricity_error",
    "significance",
    "goodness_of_fit",
    "efficiency",
    "bit_index",
    "flags",
    "astrometric_n_good_obs_al",
    "rv_n_good_obs_primary",
    "semi_amplitude_primary",
    "semi_amplitude_primary_error",
    "conf_spectro_period",
)


def candidates(channel: str, table: dict, ctx_cols: dict, res: dict) -> list[dict]:
    """Shortlisted rows as plain JSON records. Source IDs stay lossless decimal strings."""
    out = []
    lim_single, lim_triple = ph.amrf_limits(ctx_cols["m1"])
    for i in np.flatnonzero(res["shortlisted"]):
        sid = str(int(table["source_id"][i]))
        typ = str(table["nss_solution_type"][i])
        rec = {
            "candidate_id": f"{sid}:{typ}",
            "source_id": sid,
            "nss_solution_type": typ,
            "channel": channel,
            "orbit": {k: _num(table[k][i]) for k in ORBIT_FIELDS},
            "context": {k: _num(ctx_cols[k][i]) for k in CONTEXT_FIELDS},
            "primary": {
                "m1": _num(ctx_cols["m1"][i]),
                "m1_sigma_frac": _num(ctx_cols["m1_sigma_frac"][i]),
                "m1_source": str(ctx_cols["m1_source"][i]),
                "m1_ref": str(ctx_cols["m1_ref"][i]),
                "evolved_primary": bool(ctx_cols["evolved_primary"][i]),
                "gaia_m2_lower": _num(ctx_cols["gaia_m2_lower"][i]),
                "gaia_fluxratio_upper": _num(ctx_cols["gaia_fluxratio_upper"][i]),
            },
            "duplicated_source": bool(ctx_cols["duplicated_source"][i]),
            "phot_variable_flag": str(ctx_cols["phot_variable_flag"][i]),
            "m2_dark_point": _num(res["m2_dark_point"][i]),
            "m2_dark": _triple(res["m2_dark_q"][i]),
            "covariance_method": str(res["covariance_method"][i]),
            "invalid_draw_fraction": _num(res["invalid_draw_fraction"][i]),
            "draws": int(res["draws_used"][i]),
            "meaning": "Minimum companion mass IF the companion is dark and IF the catalogue orbit and primary mass are right. Not a mass measurement.",
        }
        if channel == "astrometric":
            rec.update(
                a0_mas=_num(res["a0_mas"][i]),
                f_phot=_num(res["f_phot"][i]),
                f_phot_q=_triple(res["f_phot_q"][i]),
                cos_i=_num(res["cos_i"][i]),
                amrf=_triple(res["amrf_q"][i]),
                amrf_limit_single_ms=_num(lim_single[i]),
                amrf_limit_ms_triple=_num(lim_triple[i]),
                k1_pred_kms=_triple(res["k1_pred_q"][i]),
            )
            if typ == "AstroSpectroSB1":
                rec["astrospectro_dark_ratio"] = _triple(res["dark_ratio_q"][i])
        else:
            rec.update(f_spec=_num(res["f_spec"][i]), f_spec_q=_triple(res["f_spec_q"][i]))
        rec["mass_range_label"] = (
            "BH_MASS_RANGE_IF_DARK" if rec["m2_dark"]["q05"] >= CRITERIA["bh_range_m2_q05"] else "NS_MASS_RANGE_IF_DARK"
        )
        out.append(rec)
    return out


def run_find(table: dict, ctx: dict, backend=None, shard=None, shards=1):
    """Run both channels over one shard of the table. Returns (candidates, stats)."""
    backend = backend or ph.Backend()
    types = table["nss_solution_type"]
    in_shard = np.ones(len(types), bool) if shard is None else ((table["source_id"] >> 35) % shards) == shard  # HEALPix level-12 pixel, so shards interleave on the sky
    stats, found = {}, []
    for channel, mask, scan in (
        ("astrometric", np.char.startswith(types, "Orbital") | (types == "AstroSpectroSB1"), scan_astrometric),
        ("spectroscopic", (types == "SB1") | (types == "SB1C"), scan_sb1),
    ):
        started = time.time()
        sel = np.flatnonzero(mask & in_shard)
        sub = {k: v[sel] for k, v in table.items()}
        cols = attach_context(sub, ctx)
        res = scan(sub, cols, backend)
        cands = candidates(channel, sub, cols, res)
        found += cands
        stats[channel] = {
            "rows_scanned": int(len(sel)),
            "rows_monte_carlo": int((res["covariance_method"] != "not_run_below_prefilter").sum()),
            "covariance_methods": {str(k): int(v) for k, v in zip(*np.unique(res["covariance_method"], return_counts=True))},
            "point_m2_above_cut": int(np.nansum(res["m2_dark_point"] >= CRITERIA["m2_q05_min"])),
            "shortlisted": len(cands),
            "seconds": round(time.time() - started, 3),
            "backend": backend.label,
        }
    return found, stats
