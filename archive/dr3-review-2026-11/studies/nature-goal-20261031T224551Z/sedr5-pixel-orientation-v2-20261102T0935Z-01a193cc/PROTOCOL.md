# Paired pixel-array orientation prototype

Revision 2, prepared 2026-11-02 UTC for independent review. Revision 1 was not
run; the science reviewer requested more precise wording about what a
permutation establishes. The preceding descriptive
check found each blue LOGLAM array strictly increasing and each red array
non-increasing. A separate direct read found the red values strictly decrease,
not remain constant. Descending storage is not itself an error. Hypothesis:
a small, non-production helper can orient a monotonic wavelength grid while
preserving the six stored vectors' existing index relationships and allowing
a byte-reversible roundtrip. Neither physical wavelength/pixel association nor
calibration is established by this operation.

Use only the already pinned SEDR5 FITS product and the prior result hash
`ce14934e290c8e1212f515f53158ab21d8ba8ce5bab9e38ff2c26187b53d2548`.
Require finite, strictly monotonic LOGLAM, equal one-dimensional shapes and
unmasked arrays. A rejected input means only that this prototype cannot orient
it; it does not establish that a spectrum is scientifically unusable.
Preserve array dtypes; for descending grids reverse LOGLAM,
FLUX, INVVAR, PIXELMASK, SKYFLUX and FLUXCORR **together**. Do not interpolate,
clip, derive RVs or write transformed spectra. Check that reversing back
recovers the original bytes for every field in every frame. Report only
orientation, endpoint log-wavelengths and byte-roundtrip results.

The [provider](https://dr5.lamost.org/sedr5/) describes these pixel arrays and
the vacuum heliocentric wavelength convention. Numeric ordering and a
bitwise roundtrip do not validate wavelength calibration, mask semantics,
source attribution, noise, RV accuracy, or physical quality. The three
same-sequence exposure labels do not establish independent, calibrated,
source-attributed orbital RV epochs; they may carry time information in a
later reviewed analysis. The separate per-line arrays in extensions 2 and 3
are not transformed or validated. This is a
CPU-only research prototype with synthetic tests and independent review; it is
not adopted in the production harness and changes no criterion, ranking,
release policy or holdout. No network or input modification is needed.
