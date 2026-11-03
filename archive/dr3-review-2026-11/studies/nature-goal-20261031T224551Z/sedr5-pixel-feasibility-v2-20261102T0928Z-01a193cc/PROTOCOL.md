# Offline SEDR5 pixel-array feasibility check

Revision 2, prepared 2026-11-02 UTC for independent review. Revision 1 was
not run on real pixels: independent reviewers found synthetic overflow,
integer-ordering, unequal-label and masked-array failures, now covered by
regressions. Hypothesis: the already saved
six-arm-frame product for held Gaia DR3 `1533365584518328576` may contain
enough numerically usable arrays to motivate a later calibrated spectral
analysis. This check describes the arrays; it does not establish usable RVs,
source attribution, a companion or an orbit, and it changes no release rule.

Read only the SHA-256-pinned public SEDR5 FITS product
`7a33d6a4ff8594c33b43181309bc5ad4e0739e6245943e06ba099172d04742de`.
Verify the actual six-by-4,136 shapes and preserved MJM/arm labels before
reporting. Per frame count finite FLUX, finite INVVAR, positive INVVAR, finite
LOGLAM, zero-valued PIXELMASK and their conjunction. Count finite adjacent
LOGLAM pairs with non-increasing values. No mask-bit meaning is inferred:
zero is merely the stored numeric value. Reject masked arrays, rather than
silently dropping their masks. Finite numeric values can still be undocumented
sentinels. Numerical wavelength ordering does not validate the wavelength
solution, reference frame, spectral resolution or RV accuracy.

For the conjunction only, report the median signed `FLUX * sqrt(INVVAR)` as
an **unvalidated numeric proxy**, conditional on the undocumented-in-this-check
assumption that INVVAR is the inverse variance corresponding to FLUX in the
same units. It is not an adopted S/N measurement, calibrated uncertainty,
template-match threshold, usable-pixel count or completeness statistic. This
subset is explicitly filtered by the stated numeric conjunction; its median
can depend on sky, spectral structure, pixel correlations, missingness and
arm-specific processing. Do not clip negative flux or replace missing values;
an empty proxy set produces JSON null. Compute the two-middle-value median
without float overflow, and compare wavelength entries without changing dtype.
Do not compare against an orbit, fit spectra, infer velocity, subtract sky,
classify a blend or select a candidate.
The six arm-frame summaries are from one sequence, not six independent
orbital epochs.

The [provider documentation](https://dr5.lamost.org/sedr5/) describes the
arrays and says LOGLAM wavelengths are vacuum and heliocentric; it refers mask
semantics to another release. [Bai et al.](https://arxiv.org/html/2106.12715v2)
explain that RV errors depend on S/N, spectral type and time separation, and
warn about adjacent fibres and sky backgrounds. Their population scatter must
not be assigned as this target's error. Use CPU, no network, no holdout, no
changes to the saved product or production pipeline. Run synthetic tests and
obtain independent science and execution review before the real-data check.
