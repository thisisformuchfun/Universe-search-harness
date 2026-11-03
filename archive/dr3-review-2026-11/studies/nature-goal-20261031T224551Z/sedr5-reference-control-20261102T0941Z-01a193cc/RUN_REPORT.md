# SEDR5 different-observation reference control

Three bounded public GETs retrieved a 550,080-byte SEDR5 product for a known
catalogue example. Its extension header matches the sample's plate,
spectrograph, fibre and finite catalogue coordinates; the sample's nominal
minute appears in both arms. The FITS extension has no OBSID card. These facts
support a catalogue-linked fibre/product and minute-consistency check, not
independent astrometry, photon identity or source attribution.

All three blue LOGLAM arrays are strictly ascending and all three red arrays
strictly descending, the same numerical pattern as the held-source product.
Two observations from the same survey and pipeline do not establish a universal
storage convention, physical wavelength/pixel alignment, calibration or RV
accuracy. Counts include all pixels without applying PIXELMASK; finite
sentinels and other quality issues remain possible. The fixed UTC+08,
uniform-day conversion of local DATE-BEG differs from the DATE-OBS-labelled
UTC value by 1,501.12 s; the header conventions remain unresolved.

No flux or RV was analyzed, no orbit or black-hole candidate established, and
no release criterion, ranking or holdout changed. All 14 original anomalies
remain held; two are published candidate controls and 12 have unresolved
novelty. See [capture audit](INDEPENDENT_CAPTURE_AUDIT.md),
[metadata protocol](METADATA_PROTOCOL_V2.md),
[metadata result](metadata-v2/RESULTS.json), and
[independent reviews](INDEPENDENT_METADATA_V2_POST_REVIEW.md).
Native transport headers and diagnostics stay local pending privacy review.
