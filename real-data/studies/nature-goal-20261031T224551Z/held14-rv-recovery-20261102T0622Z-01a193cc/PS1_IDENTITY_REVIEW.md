# PS1 identity context for Gaia DR3 1533365584518328576

Two frozen public PS1 DR2 mean-catalogue requests returned HTTP 200: the
previously saved exact-object control and the `ps_id` value from the LAMOST
row, `157061857151801289`. The latter returned one exact-key row whose
`iMeanPSFMag=20.606800079345703` numerically matches the saved DR12
`mag_ps_i` value. This is consistent with a relationship between the records;
the LAMOST crossmatch and estimator lineage have not been established.

The returned row has **one total detection, one i-band detection and one
measurement in the i-band mean**. Its provider-reported i error is 0.064394;
the i standard deviation and the g/r magnitudes and errors are `-999`, which
are missing values. Raw `qualityFlag=32`, `iFlags=4120`, and
`astrometryCorrectionFlag=0` are preserved. Those flags do not establish a
reliable detection or independent calibration.

The PS1 mean position is about **1.519 arcseconds** from the saved, unpropagated
Gaia 2016.0 position and about **1.498 arcseconds** from the saved LAMOST
input/observing coordinate. The PS1 `epochMean` is MJD 56784.29064815,
approximately May 2014; its time scale is not stated in that field. A science
reviewer calculated that the saved Gaia single-star proper motion would shift
the position only about 0.015 arcsecond over the nominal epoch difference.
That calculation omits parallax, orbital displacement, uncertainties,
covariances and possible catalogue systematics. Neither separation is a match
significance or proof of a mismatch, physical companion, contamination, or
the source of light entering the LAMOST fibre.

The saved identifier and numerical PS i value match this returned PS1 row;
the data lineage, source association and photometric quality remain open.
The comparison with Gaia G uses different passbands and epochs.
The next useful evidence is a quality-checked, spatially resolved view or
source-attributed spectroscopy; repeated exact-key queries would add no
information. The [frozen protocol](ps1-identity-v1/PROTOCOL.json),
[target body](ps1-identity-v1/lamost_psid_target.raw), and
[machine-readable comparison](PS1_IDENTITY_EVIDENCE.json) preserve the
queries, inputs and hashes. Native request and header files remain local.

Both independent reviewers checked the response and its limitations. No
source disposition, orbit, release policy or scientific holdout changed.
PS1 field descriptions are available in the [provider's mean-object schema](https://outerspace.stsci.edu/spaces/PANSTARRS/pages/298812411/PS1+MeanObjectView+table+fields).
