# Independent metadata reviews

Root transcription of the independent reviews on 2026-11-02 UTC. The science
reviewer `/root/ps1_science_review` and execution reviewer
`/root/ps1_execution_review` accepted `metadata-v2/METADATA.json`, SHA256
`23d9d3b4c06fbd2c9d04990d0364c3eca68c26c2dfabd268f0b508bc16339102`.

Both reviewers independently checked the matching plan, spectrograph, fibre,
catalogue coordinates, coordinate frame and local observing interval; the six
MJM/COLOR/EXPTIME/FIBERMASK metadata entries; the conditional 1,500.8-second
date-label difference; and the distinction between DR5's three rows per arm
and DR6's three-blue/one-red exposure counts. The execution reviewer confirmed
the saved input and script hashes, Python/Astropy versions and actual FITS HDU
types. The five V2 synthetic tests were independently rerun read-only.

These agreements support a same-fibre observation association. They do not
establish which frames contributed to DR6, independent photons, source
attribution, a calibrated RV or an orbit. The reviewers did not run the main
extractor, inspect flux values, use the network or GPU, write files, or
evaluate the holdout. The execution reviewer did not independently verify the
provider's ASCII-format wording from locally saved evidence; the official
documentation is linked in the report.
