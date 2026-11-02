# SEDR5 held-fibre filename query

After independent review of the exact live-header mapping and the positive
sample control, a separate one-request run queried the previously retrieved
fibre observation for held Gaia DR3 `1533365584518328576`. The public endpoint
returned HTTP 200 with a **zero-byte body**. The parser stopped visibly; this
is neither a valid zero-row CSV nor proof that the catalogue lacks a record.
No RV, independent orbit or source-attribution evidence was recovered.

The fixed request and empty raw body, timestamps, checksums and process cleanup
are recorded in `capture-v1/`; see [post-capture review](INDEPENDENT_POST_CAPTURE_REVIEW.md).
The previous control returned three sample identity tuples but establishes
neither catalogue completeness nor the target's Gaia association. All 14
original anomalies remain held; the two published candidates remain controls.
No holdout, ranking or scientific release policy changed.

Native response headers contain potentially session-bearing cookies and must
remain local; do not print them, reuse cookies or package the headers. Native
diagnostic streams also remain local pending full privacy review.
