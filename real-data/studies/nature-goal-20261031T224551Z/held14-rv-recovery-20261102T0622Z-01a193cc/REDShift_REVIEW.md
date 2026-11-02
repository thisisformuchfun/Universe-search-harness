# Recovered catalogue redshift for Gaia DR3 1533365584518328576

The already saved LAMOST DR12 general-catalogue row for this exact string
identifier contains `z = -0.00023659` and `z_err = 0.00001158`. Its spectrum
is observation **294101037**, taken on 2015-01-08. The prior queue correctly
said that no LASP stellar-parameter RV row was retrieved, but did not report
this general-catalogue redshift. This is a recovered field in an existing
observation, not a newly obtained observation or an independent RV series.

For orientation only, adopting the optical `v = cz` convention gives
**−70.93 km/s** and scaling the reported `z_err` by `c` gives **3.47 km/s**.
The latter is not demonstrated to be a calibrated one-sigma uncertainty.
Neither number is an adopted orbit-fitting measurement: the exact catalogue
velocity convention, zero point and low-S/N uncertainty calibration need
verification. The DR12 row reports g/r S/N of 4.4/3.45, K3 classification,
and fibre mask 0. A clear mask does not establish a reliable velocity or
isolate all light entering the fibre.

The independently saved **DR6 product of the same observation** has the same
redshift and error and reports `ZFLAG=PIPELINE`, `HELIO=True` and
`HELIO_RV=-19.88282 km/s`. This indicates a heliocentric correction in that
reduction; it does not by itself establish the precise reference frame or
calibration of the DR12 catalogue redshift. Do not add the correction again.
The saved FITS header labels `DATE-OBS=2015-01-08T21:25:00` as median UTC;
it lists three blue and one red exposure, with differing integration times.
The effective epoch of a fitted velocity and effects of combining exposures
remain unverified. [LAMOST's DR12 documentation](https://www.lamost.org/dr12/v2.0/doc/lr-data-production-description)
describes the general-catalogue redshift, the FITS flags and observation time.

DR12's catalogue associates the spectrum with the exact Gaia source ID and
the saved coordinates are close to the Gaia 2016 position. The association
uses catalogue crossmatching and does not prove which light entered the fibre.
The same row lists Gaia G=16.177345 and PS1 i=20.6068, with other PS bands
marked −999. These are different passbands and may be affected by catalog
selection or quality. Their discrepancy is an identification/photometry lead,
not a demonstrated error or a physical companion.

As a same-survey arithmetic check, the already published candidate
4491401821468887552 has a DR12 general-row `cz` close to its same-observation
LASP RV, −5.31 ± 4.36 km/s. Its DR6 FITS says `ZFLAG=LASP`, unlike the
target's `PIPELINE`, and reports a different redshift error than DR12. This
comparison is neither an independent exposure nor a validation of the target
pipeline redshift or its uncertainty.

Two independent reviewers checked the saved rows, FITS header, hashes,
identity linkage, arithmetic and scientific limitations. The input paths,
sizes, hashes and reproducible extraction are in [EXTRACTED_EVIDENCE.json](EXTRACTED_EVIDENCE.json)
and [extract_saved_evidence.py](extract_saved_evidence.py). A prospective PS1
check is separately scoped and must not be treated as completed until its own
result exists. No scientific gate, source disposition or holdout changed.
