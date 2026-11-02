# PS1 image independence and PSF feasibility

All 14 original sources remain held. This is an exploratory offline review
of existing data for Gaia DR3 1533365584518328576; it establishes no new
black-hole candidate, companion or orbit, and makes no release decision.

The saved i-stack header lists 30 distinct input image names. Eight begin
`o6784g`; the saved one-detection PS1 object's mean epoch is
`56784.29064815` MJD, with integer suffix `6784`. The [Pan-STARRS IPP data
model](https://svn.panstarrs.ifa.hawaii.edu/trac/ipp/wiki/IPP_data_model)
describes an exposure-name component as a truncated MJD. This match is a
lead for **possible overlap**, not proof of the same exposure or even of
contribution at the source pixel: time conventions, exposure/CCD identity,
masking and stack rejection remain unresolved. The stack and the single
catalogue detection must not be counted as independent evidence on this
basis. The provider's [detection](https://outerspace.stsci.edu/spaces/PANSTARRS/pages/298812397/PS1+Detection+table+fields)
and [frame/stack metadata](https://outerspace.stsci.edu/spaces/PANSTARRS/pages/298812451/PS1+Database+observational+metadata+tables)
describe identifiers needed for a future exposure-level lineage test.

The two interior peaks near saved, unpropagated Gaia positions are plausible
PSF-study leads, not verified reference stars. Their low signal in the wings,
unknown isolation and saturation, shared stack processing and lack of a
validated local noise model prevent a reliable contrast-matched recovery
test with this cutout alone. A brighter Gaia-position feature is clipped at
the edge. An independent reviewer reached the same conclusion. The survey
warns that [stack PSFs can vary on small scales](https://outerspace.stsci.edu/spaces/PANSTARRS/pages/298812391/PS1+Forced+Photometry+of+Sources).

The [provider documents stack `.wt` products as variance images](https://outerspace.stsci.edu/spaces/PANSTARRS/pages/298812350/PS1+Weight+Image),
with correlated-pixel caveats. That clarifies the upstream product type, not
the numerical calibration of this particular cutout. Its BUNIT/BTYPE are
absent and no covariance array is supplied as a separate HDU; the PS_COVAR
header flag alone is insufficient to construct a likelihood.

The independent science reviewer identified a coordinate-frame omission in
the first exploratory inventory. The corrected V2 transforms saved Gaia ICRS
positions to the FITS-declared FK5 WCS; the shift is about 0.008 arcsecond
and the same local maxima and clipped edge remain. Gaia's 2016 positions are
still unpropagated, and the WCS is not independently calibrated. The first
inventory and its output are retained; [change log](ENGINEERING_CHANGELOG_V2.md)
and [reproduction](REPRODUCIBILITY_V2.md) document the correction and the
separately fixed out-of-image slicing case.

No further archive request is justified by this feasibility inventory alone.
The present data do not resolve the source or the LAMOST fibre attribution.
A future independently reviewed analysis would need adequate local PSF and
noise validation; independent imaging or phase-resolved observations would add
different evidence. No observation has been scheduled. [Machine-readable
observations](OBSERVATIONS_V2.json) preserve input hashes, exact header names,
coordinates and limits; [independent review](INDEPENDENT_SCIENCE_REVIEW_V2.md)
records the audit. This work made no new native archive request and did not
use or reset the holdout. Documentation was consulted through web browsing.
