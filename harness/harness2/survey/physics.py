"""Vectorized orbit observables for whole-catalogue runs.

Everything here is a measured or derived *observable under a stated assumption*.
`m2_dark` is the companion mass that would be required IF the companion emitted
no light and IF the catalogue orbit and the primary-mass estimate were right. It
is a triage quantity, not a mass measurement.

The same kernels run on NumPy (CPU) or PyTorch (CPU, CUDA or MPS) through a
small backend shim, so a GPU is used when present and never assumed.
"""

from __future__ import annotations

import math
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from harness2.universe.detectors.signal_pipeline import COVARIANCE_ORDERS, EXPECTED_BITS

DAYS_PER_YEAR = 365.25
AU_PER_YEAR_KMS = 29.784692  # 2*pi AU / Julian year, in km/s
SB1_CONSTANT = 1.0361e-7  # f(M)[Msun] = C * (1-e^2)^1.5 * K[km/s]^3 * P[d]

# Approximate main-sequence mass -> absolute G magnitude, after the Pecaut & Mamajek
# (2013, updated) dwarf table. Used only for triage: the primary-mass fallback and the
# luminous-companion limits. Not a substitute for a fitted primary mass.
MS_MASS = np.array([0.10, 0.23, 0.44, 0.57, 0.70, 0.87, 1.00, 1.08, 1.33, 1.61, 1.88, 2.30, 3.40, 5.00])
MS_ABS_G = np.array([14.3, 11.3, 9.30, 8.16, 6.87, 5.65, 4.67, 4.34, 3.37, 2.50, 1.80, 1.00, -0.20, -1.10])
MS_BP_RP = np.array([4.60, 3.30, 2.55, 1.98, 1.33, 0.98, 0.82, 0.76, 0.60, 0.45, 0.30, 0.07, -0.08, -0.20])
_LOG_MS_MASS = np.log10(MS_MASS)


def ms_colour_at_abs_g(abs_g):
    """Approximate main-sequence BP-RP colour at a given absolute G magnitude."""
    return float(np.interp(-abs_g, -MS_ABS_G, MS_BP_RP))


# ----------------------------------------------------------------- backends


class Backend:
    """NumPy by default. `torch:<device>` moves the Monte Carlo kernel to PyTorch."""

    def __init__(self, name="numpy"):
        self.name = name
        if name == "numpy":
            self.xp, self.torch, self.device = np, None, "cpu"
            return
        if not name.startswith("torch"):
            raise ValueError("backend must be numpy, torch, torch:cpu, torch:cuda or torch:mps")
        import torch  # optional dependency

        device = name.split(":", 1)[1] if ":" in name else ("cuda" if torch.cuda.is_available() else "cpu")
        if device.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable")
        if device == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError("MPS requested but unavailable")
        self.xp, self.torch, self.device = torch, torch, device
        # MPS has no float64; results there are float32 and labelled as such.
        self.dtype = torch.float32 if device == "mps" else torch.float64

    @property
    def label(self):
        return "numpy" if self.torch is None else f"torch:{self.device}"

    def asarray(self, a):
        if self.torch is None:
            return np.asarray(a, dtype=np.float64)
        return self.torch.as_tensor(np.asarray(a, dtype=np.float64), dtype=self.dtype, device=self.device)

    def to_numpy(self, a):
        return a if self.torch is None else a.detach().cpu().numpy().astype(np.float64)

    def randn(self, shape, seed):
        # Draws always come from NumPy so every backend sees identical random numbers.
        return self.asarray(np.random.default_rng(seed).standard_normal(shape))

    def sort(self, a, axis):
        return np.sort(a, axis=axis) if self.torch is None else self.torch.sort(a, dim=axis).values

    def quantiles(self, a, qs=(0.05, 0.5, 0.95)):
        """Row-wise quantiles ignoring NaN, by sorting (NaN sorts last). Returns NumPy (rows, len(qs))."""
        xp = self.xp
        n_valid = self.to_numpy((~xp.isnan(a)).sum(1) if self.torch is None else (~xp.isnan(a)).sum(1).double())
        if self.torch is None and len(n_valid) and n_valid.min() == a.shape[1]:
            # No NaN anywhere: select just the needed order statistics instead of a full sort.
            kth = sorted({int(k) for q in qs for k in (math.floor(q * (a.shape[1] - 1)), min(a.shape[1] - 1, math.floor(q * (a.shape[1] - 1)) + 1))})
            s = np.partition(a, kth, axis=1)
        else:
            s = self.to_numpy(self.sort(a, 1))
        rows = np.arange(s.shape[0])
        out = np.full((s.shape[0], len(qs)), np.nan)
        ok = n_valid > 0
        for k, q in enumerate(qs):
            pos = q * (n_valid - 1)
            lo = np.clip(np.floor(pos).astype(int), 0, s.shape[1] - 1)
            hi = np.clip(lo + 1, 0, np.maximum(n_valid.astype(int) - 1, 0))
            frac = pos - lo
            val = s[rows, lo] * (1 - frac) + s[rows, hi] * frac
            out[ok, k] = val[ok]
        return out, n_valid


# ------------------------------------------------------- closed-form pieces


def photocentre(A, B, F, G, parallax, period, xp=np):
    """Angular photocentre semi-major axis a0 (mas) and f_phot (Msun).

    Identical algebra to the sealed per-row `signal_pipeline.photocentre`.
    """
    u = (A * A + B * B + F * F + G * G) / 2
    v = A * G - B * F
    disc = xp.clip(u * u - v * v, 0.0, None)
    a0sq = u + xp.sqrt(disc)
    a0 = xp.sqrt(a0sq)
    f = (a0 / parallax) ** 3 / (period / DAYS_PER_YEAR) ** 2
    cos_i = xp.clip(v / a0sq, -1.0, 1.0)
    return a0, f, cos_i


def dark_companion_mass(f, m1, xp=np, iterations=16):
    """Solve m2^3 / (m1 + m2)^2 = f for m2 (dark companion, photocentre = primary).

    Newton from above the root: the function is increasing and convex there, so
    the iteration descends monotonically and cannot overshoot.
    """
    f = xp.clip(f, 1e-12, None)
    m2 = xp.maximum(4.0 * f, (4.0 * f * m1 * m1) ** (1.0 / 3.0)) + 1e-9
    for _ in range(iterations):
        s = m1 + m2
        g = m2 * m2 * m2 - f * s * s
        dg = 3.0 * m2 * m2 - 2.0 * f * s
        m2 = m2 - g / dg
    return m2


def ms_abs_g(mass):
    return np.interp(np.log10(np.clip(mass, MS_MASS[0], MS_MASS[-1])), _LOG_MS_MASS, MS_ABS_G)


def ms_mass_from_abs_g(abs_g):
    """Fallback primary mass from the dereddened absolute magnitude, main sequence assumed."""
    return 10 ** np.interp(-np.asarray(abs_g, float), -MS_ABS_G, _LOG_MS_MASS)


def _amrf_limits_for(m1, q_grid):
    q = q_grid[None, :]
    m1c = np.asarray(m1, float)[:, None]
    base = q / (1 + q) ** (2.0 / 3.0)
    lum1 = 10 ** (-0.4 * ms_abs_g(m1c))
    # Single main-sequence companion of mass q*m1.
    s_single = 10 ** (-0.4 * ms_abs_g(q * m1c)) / lum1
    a_single = base * np.abs(1 - s_single * (1 + q) / (q * (1 + s_single)))
    # Close pair of equal main-sequence stars with total mass q*m1 (hierarchical triple).
    s_triple = 2 * 10 ** (-0.4 * ms_abs_g(q * m1c / 2)) / lum1
    a_triple = base * np.abs(1 - s_triple * (1 + q) / (q * (1 + s_triple)))
    single = np.where(q <= 1.0, a_single, 0.0).max(1)
    triple = np.where(q <= 2.0, a_triple, 0.0).max(1)
    return single, triple


_Q_GRID = np.linspace(0.01, 2.0, 400)
_M1_GRID = np.linspace(0.1, 3.0, 117)
_LIM_SINGLE, _LIM_TRIPLE = _amrf_limits_for(_M1_GRID, _Q_GRID)


def amrf_limits(m1):
    """Largest astrometric mass-ratio function A = (f_phot/m1)^(1/3) that (a) one
    main-sequence companion, (b) a close main-sequence pair, can produce for a
    main-sequence primary of mass m1 (Shahaf et al. 2019, 2023 triage logic, with
    the approximate mass-luminosity relation above)."""
    m1 = np.clip(np.asarray(m1, float), _M1_GRID[0], _M1_GRID[-1])
    return np.interp(m1, _M1_GRID, _LIM_SINGLE), np.interp(m1, _M1_GRID, _LIM_TRIPLE)


def sb1_mass_function(K, period, ecc, xp=np):
    return SB1_CONSTANT * xp.clip(1 - ecc * ecc, 0.0, None) ** 1.5 * K**3 * period


def predicted_rv_semi_amplitude(a0, parallax, period, ecc, cos_i, xp=np):
    """K1 (km/s) the astrometric orbit implies if the photocentre is the primary."""
    sin_i = xp.sqrt(xp.clip(1 - cos_i * cos_i, 0.0, None))
    return AU_PER_YEAR_KMS * (a0 / parallax) * sin_i / ((period / DAYS_PER_YEAR) * xp.sqrt(xp.clip(1 - ecc * ecc, 1e-9, None)))


# -------------------------------------------------------- batched covariance


def layout_for(solution_type: str):
    """Parameter order of the published covariance, or None when unsupported.

    The Orbital family (Orbital, OrbitalAlternative*, OrbitalTargetedSearch*) shares
    one 12-parameter model in Gaia DR3. This is a DR3 statement only.
    """
    if solution_type == "AstroSpectroSB1":
        return COVARIANCE_ORDERS["AstroSpectroSB1"], EXPECTED_BITS["AstroSpectroSB1"]
    if solution_type.startswith("Orbital"):
        return COVARIANCE_ORDERS["Orbital"], EXPECTED_BITS["Orbital"]
    return None


def covariance_stack(table: dict, names, wanted, min_eigenvalue=0.0):
    """Mean vectors and covariance sub-blocks for rows that all share one layout.

    Returns (mean[n,k], cov[n,k,k], ok[n]). Rows whose correlation matrix is
    missing, out of range or indefinite get ok=False; they are never repaired.
    """
    n, p = len(table["source_id"]), len(names)
    ncorr = p * (p - 1) // 2
    corr = table["corr_vec"][:, :ncorr].astype(np.float64)
    ok = (table["corr_len"] == ncorr) & np.isfinite(corr).all(1) & (np.abs(corr) <= 1).all(1)
    R = np.broadcast_to(np.eye(p), (n, p, p)).copy()
    k = 0
    for j in range(1, p):
        for i in range(j):
            R[:, i, j] = R[:, j, i] = np.where(ok, corr[:, k], 0.0)
            k += 1
    err = np.stack([table[name + "_error"] for name in names], axis=1)
    ok &= np.isfinite(err).all(1) & (err > 0).all(1)
    ok &= np.linalg.eigvalsh(R)[:, 0] >= -1e-10
    idx = [names.index(w) for w in wanted]
    mean = np.stack([table[w] for w in wanted], axis=1)
    ok &= np.isfinite(mean).all(1)
    sub_err = np.where(ok[:, None], err[:, idx], 1.0)
    sub_R = R[:, idx][:, :, idx]
    # Correlations are published in single precision. When the block being sampled is
    # close to singular, rounding alone changes the answer, so it is refused, not used.
    ok &= np.linalg.eigvalsh(sub_R)[:, 0] >= min_eigenvalue
    cov = sub_err[:, :, None] * sub_R * sub_err[:, None, :]
    return mean, cov, ok


def diagonal_stack(table: dict, wanted):
    """Uncorrelated fallback when the published covariance cannot be used. Labelled as such."""
    mean = np.stack([table[w] for w in wanted], axis=1)
    err = np.stack([table[w + "_error"] for w in wanted], axis=1)
    ok = np.isfinite(mean).all(1) & np.isfinite(err).all(1) & (err > 0).all(1)
    cov = np.zeros((len(mean), len(wanted), len(wanted)))
    d = np.arange(len(wanted))
    cov[:, d, d] = np.where(ok[:, None], err, 1.0) ** 2
    return mean, cov, ok


def draw(mean, cov, draws, seed, backend: Backend):
    """Gaussian samples [rows, draws, k] from stacked covariances via batched eigh."""
    xp = backend.xp
    m, c = backend.asarray(mean), backend.asarray(cov)
    w, v = xp.linalg.eigh(c)
    # Symmetric square root: unique, so every backend produces the same samples
    # whatever sign or order its eigensolver picks for the eigenvectors.
    root = (v * xp.sqrt(xp.clip(w, 0.0, None))[:, None, :]) @ xp.swapaxes(v, 1, 2)
    z = backend.randn((mean.shape[0], draws, mean.shape[1]), seed)
    return m[:, None, :] + z @ root


def lognormal_sigma(m1, lower, upper, floor=0.05):
    """Fractional 1-sigma on m1 from a published [lower, upper] interval."""
    m1, lower, upper = (np.asarray(x, float) for x in (m1, lower, upper))
    sig = (upper - lower) / (2 * np.where(m1 > 0, m1, np.nan))
    sig = np.where(np.isfinite(sig) & (sig > 0), sig, 0.15)
    return np.clip(sig, floor, 0.6)


def run_chunks(fn, jobs, backend: Backend, workers=None):
    """Run fn over chunk jobs. NumPy releases the GIL in the heavy kernels, so CPU
    chunks run on a thread pool; a torch device gets them one at a time."""
    jobs = list(jobs)
    workers = workers or min(8, os.cpu_count() or 1)
    if backend.torch is not None or workers <= 1 or len(jobs) <= 1:
        for job in jobs:
            fn(*job)
        return
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(lambda job: fn(*job), jobs))


def chunks(n, size):
    for start in range(0, n, size):
        yield slice(start, min(n, start + size))


def seed_for(base_seed: int, tag: str, chunk_index: int) -> int:
    return (base_seed * 1_000_003 + sum(tag.encode()) * 7919 + chunk_index) % (2**63 - 1)


def relative(value, error):
    return float(error) / abs(float(value)) if value and math.isfinite(value) and math.isfinite(error) else math.nan
