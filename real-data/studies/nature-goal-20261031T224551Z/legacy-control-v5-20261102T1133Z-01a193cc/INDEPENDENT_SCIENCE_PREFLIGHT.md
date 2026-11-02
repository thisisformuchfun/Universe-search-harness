# Independent scientific preflight

The science reviewer `/root/ps1_science_review` reviewed the control concept on 2026-11-02 UTC. It is reasonable as a public DR9-north service/format/coverage control only. The documented example does not establish target-field coverage or demonstrate recovery of a 1.52-arcsec close pair. The actual FITS must be inspected for HDU identities, units, WCS, per-band coverage, finite pixels and inverse variance; overlapping bricks may yield unequal subimages.

The subimages are coadd products, already resampled. Their image photons differ from PS1's but DR9 astrometry uses Gaia DR2 and photometric calibration uses PS1. Inverse variance is not a PSF, saturation mask, or full noise model. PS1's one-detection i-band value cannot predict contrast in Legacy g/r/z; missing a peak does not prove absence, a physical companion, LAMOST-fibre attribution, an orbit or a black hole.

The reviewer proposed a later conditional, injection-calibrated Legacy-band feature test, only if coverage, local brightness-matched unsaturated comparison stars, masks, PSF wings, and detectable contrast are first demonstrated. A V1 128-pixel target field would omit the existing brighter comparison about 19.9 arcsec away. Such a test has not been frozen, run, approved as a new science criterion, or adopted. This study does not alter scientific criteria or the holdout ledger.

Sources: https://www.legacysurvey.org/dr9/description/ and https://www.legacysurvey.org/svtips/ .
