"""Measured Gaia NSS observables. No hidden truth, FAP, or companion-mass claims."""

from __future__ import annotations
import hashlib
import math
import re
import numpy as np

TERMS = ("a_thiele_innes", "b_thiele_innes", "f_thiele_innes", "g_thiele_innes")
COVARIANCE_ORDERS = {
    "Orbital": ("ra", "dec", "parallax", "pmra", "pmdec", *TERMS, "eccentricity", "period", "t_periastron"),
    "AstroSpectroSB1": (
        "ra",
        "dec",
        "parallax",
        "pmra",
        "pmdec",
        *TERMS,
        "c_thiele_innes",
        "h_thiele_innes",
        "center_of_mass_velocity",
        "eccentricity",
        "period",
        "t_periastron",
    ),
}
EXPECTED_BITS = {"Orbital": 8191, "AstroSpectroSB1": 65535}


def number(row, key):
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"missing/non-numeric {key}") from None
    if not math.isfinite(value):
        raise ValueError(f"non-finite {key}")
    return value


def identity(row):
    sid = row.get("source_id")
    if not isinstance(sid, str) or re.fullmatch(r"[0-9]+", sid) is None or not 0 < int(sid) < 2**63:
        raise ValueError("source_id must be a lossless decimal string")
    typ = row.get("nss_solution_type")
    if not isinstance(typ, str) or not typ:
        raise ValueError("missing solution type")
    return sid + ":" + typ


def photocentre(A, B, F, G, parallax, period):
    """Return angular a0 (mas) and f_phot in solar-mass units, NOT M2."""
    A, B, F, G, p, P = np.broadcast_arrays(A, B, F, G, parallax, period)
    if np.any(p <= 0) or np.any(P <= 0):
        raise ValueError("positive parallax/period required")
    u = (A * A + B * B + F * F + G * G) / 2
    # Algebraically nonnegative; max only compensates floating roundoff in this discriminant.
    disc = np.maximum(0.0, u * u - (A * G - B * F) ** 2)
    a = np.sqrt(u + np.sqrt(disc))
    f = (a / p) ** 3 / (P / 365.25) ** 2
    return a, f


def covariance(row):
    typ = row["nss_solution_type"]
    if typ not in COVARIANCE_ORDERS:
        raise ValueError("solution type covariance not supported; alternatives remain held")
    bit = number(row, "bit_index")
    if not bit.is_integer() or int(bit) != EXPECTED_BITS[typ]:
        raise ValueError("reduced/dependent parameterization not supported")
    names = COVARIANCE_ORDERS[typ]
    n = len(names)
    raw = row.get("corr_vec")
    if isinstance(raw, str):
        raw = raw.strip().strip("[]").replace(",", " ").split()
    if not isinstance(raw, (list, tuple, np.ndarray)):
        raise ValueError("missing corr_vec")
    c = np.array([float(v) for v in raw], dtype=np.float64)
    if len(c) != n * (n - 1) // 2 or not np.all(np.isfinite(c)) or np.any(np.abs(c) > 1):
        raise ValueError("invalid correlation length/value")
    R = np.eye(n)
    k = 0
    for j in range(1, n):
        for i in range(j):
            R[i, j] = R[j, i] = c[k]
            k += 1
    err = np.array([number(row, name + "_error") for name in names])
    if np.any(err <= 0):
        raise ValueError("nonpositive/missing standard error")
    # Do not silently repair an indefinite correlation matrix.
    if np.linalg.eigvalsh(R)[0] < -1e-10:
        raise ValueError("indefinite correlation matrix")
    full = err[:, None] * R * err[None, :]
    wanted = ("parallax", *TERMS, "period")
    idx = [names.index(x) for x in wanted]
    mean = np.array([number(row, x) for x in wanted])
    sub = full[np.ix_(idx, idx)]
    return mean, sub


def propagate(row, draws=4096, backend="numpy"):
    """Joint Gaussian approximation of served covariance; not an orbit refit/posterior."""
    if not 128 <= draws <= 1_000_000:
        raise ValueError("draws outside bounded range")
    mean, cov = covariance(row)
    seed = int.from_bytes(hashlib.sha256(identity(row).encode()).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    vals, vec = np.linalg.eigh(cov)
    if vals.min() < -1e-10:
        raise ValueError("indefinite covariance")
    # Tolerate numerical zero modes only, recorded by the explicit approximation label.
    z = rng.standard_normal((draws, 6))
    samples = mean + z @ (vec * np.sqrt(np.maximum(vals, 0))).T
    valid = (samples[:, 0] > 0) & (samples[:, 5] > 0) & np.isfinite(samples).all(axis=1)
    good = samples[valid]
    if not len(good):
        raise ValueError("no physically positive Monte Carlo draws")
    if backend == "numpy":
        _, f = photocentre(good[:, 1], good[:, 2], good[:, 3], good[:, 4], good[:, 0], good[:, 5])
    elif backend == "cuda":
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA explicitly requested but unavailable")
        x = torch.as_tensor(good, device="cuda", dtype=torch.float64)
        A, B, F, G = x[:, 1], x[:, 2], x[:, 3], x[:, 4]
        u = (A * A + B * B + F * F + G * G) / 2
        a = torch.sqrt(u + torch.sqrt(torch.clamp(u * u - (A * G - B * F) ** 2, min=0)))
        f = ((a / x[:, 0]) ** 3 / (x[:, 5] / 365.25) ** 2).cpu().numpy()
    else:
        raise ValueError("unknown backend")
    finite = np.isfinite(f)
    nonfinite_fraction = float(1 - finite.mean())
    f = f[finite]
    if not len(f):
        raise ValueError("No finite propagated observables")
    return {
        "nonfinite_derived_fraction": nonfinite_fraction,
        "method": "joint_gaussian_catalog_covariance_not_orbit_refit",
        "backend": backend,
        "draws": draws,
        "invalid_draw_fraction": float(1 - valid.mean()),
        "f_phot_q05": float(np.quantile(f, 0.05)),
        "f_phot_q50": float(np.quantile(f, 0.5)),
        "f_phot_q95": float(np.quantile(f, 0.95)),
        "caveat": "Conditional Gaussian propagation only; not mass, BH probability, or validated orbit.",
    }


def measure(row, draws=4096, backend="numpy"):
    key = identity(row)
    a, f = photocentre(*(number(row, k) for k in TERMS), number(row, "parallax"), number(row, "period"))
    if not math.isfinite(float(f)):
        raise ValueError("overflow/non-finite observable")
    result = {
        "record_id": key,
        "source_id": row["source_id"],
        "nss_solution_type": row["nss_solution_type"],
        "a0_mas": float(a),
        "f_phot_solar": float(f),
        "observable_not_companion_mass": True,
        "parallax_relative_error": number(row, "parallax_error") / number(row, "parallax"),
        "period_relative_error": number(row, "period_error") / number(row, "period"),
    }
    if result["parallax_relative_error"] <= 0 or result["period_relative_error"] <= 0:
        raise ValueError("nonpositive standard errors")
    try:
        result["efficiency"] = max(0.0, min(1.0, number(row, "efficiency")))
    except ValueError:
        result["efficiency"] = None
    try:
        result["uncertainty"] = propagate(row, draws, backend)
    except (ValueError, KeyError, TypeError, OverflowError) as e:
        result["uncertainty"] = {"status": "UNAVAILABLE", "reason": str(e)}
    return result
