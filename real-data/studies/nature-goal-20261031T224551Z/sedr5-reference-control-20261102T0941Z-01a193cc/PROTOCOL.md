# SEDR5 independent reference-product control

Prepared 2026-11-02 UTC for independent review. Hypothesis: a public SEDR5
product corresponding to the already verified catalogue example may show
whether the held observation's descending red LOGLAM grids are also present in
one different observation. A matching reference would be a useful control,
not proof of a universal storage convention, calibration, physical array
association, Gaia source attribution, or an orbit.

The fixed reference is the public sample record with specid
`20150309HD110643N151055B0215142` and filename
`20150309/HD110643N151055B02/20150309_HD110643N151055B02_15_142.fit`.
The [official SEDR5 release](https://dr5.lamost.org/sedr5/) documents these
path components. A hash-pinned, previously retrieved official archive root
listing contains the exact day child `20150309/`; it is a historical index
snapshot, not a guarantee of current availability. Validate the saved public
sample and root listing before making any request.

Make at most three serial HTTPS GETs: the exact day listing, then the exact
plan listing only if the day response has one unambiguous literal plan link,
then the exact FITS file only if the plan response has one unambiguous literal
filename link. Use the previously reviewed transport, no retries, redirects,
cookies, credentials, alternate paths or shared cache. Limits: 500,000 bytes
per index, 4,000,000 bytes for the product, 45 s curl transfer per request,
210 s total deadline, at least one second between requests; monitored header
and diagnostic caps can overshoot between 20 ms polls. Preserve raw responses,
exact requests, hashes and cleanup status in a unique directory. Never
overwrite a live acquisition lease. Native headers and diagnostics remain
local pending privacy review.

Transport and FITS prefix do not validate product identity. A later,
separately reviewed offline check must verify actual FITS metadata against the
sample observation fields before treating it as a reference, and any ordering
comparison remains descriptive. No source selection, ranking, RV fit,
scientific criterion, release policy, GPU or holdout evaluation is authorized.
