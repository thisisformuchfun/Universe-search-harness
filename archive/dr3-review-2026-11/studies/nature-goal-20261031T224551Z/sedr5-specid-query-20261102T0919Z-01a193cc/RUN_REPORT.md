# SEDR5 observation-ID diagnostic

The independently reviewed control-first query recovered all three expected
sample identity records by the documented observation-ID field. The separately
requested ID derived from the held fibre product returned HTTP 200 with a
zero-byte body; the parser stopped. The earlier filename query returned the
same kind of empty body. Neither is a confirmed zero-row table, a catalogue
nonmatch, or an RV measurement. The target ID's exact catalogue formatting and
UTC/local date convention are not independently established.

Further identical target requests are unlikely to add information. Existing
single-exposure spectra, calibrated source-attributed phase-resolved RVs and
resolved-light evidence are distinct possible routes. All 14 original objects
remain held; two are published candidates used as controls, and novelty for
the other 12 is unresolved. No scientific criterion, release policy, ranking,
GPU or holdout changed. See [protocol](PROTOCOL.md),
[prior evidence](PRIOR_EVIDENCE.md), and [independent review](INDEPENDENT_POST_CAPTURE_REVIEW.md).

Native headers contain potentially session-bearing cookies and remain local;
do not print, reuse, copy or package them. Diagnostic streams remain local.
