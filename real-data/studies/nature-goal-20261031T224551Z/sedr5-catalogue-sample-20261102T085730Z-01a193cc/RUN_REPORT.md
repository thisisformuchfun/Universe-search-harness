# SEDR5 catalogue sample preflight

2026-11-02 UTC. The [official release](https://dr5.lamost.org/sedr5/) links a
sample CSV for the single-exposure RV catalogue. One fixed, bounded public GET
retrieved it successfully; the independently checked result contains 29
distinct columns and nine structurally consistent rows. Exact request, raw
response, hash, timestamp, limits, and process cleanup are recorded in
`capture-v1/`. See `PROTOCOL.md` and `INDEPENDENT_POST_CAPTURE_REVIEW.md`.

This did not query any held star. It demonstrates the example's structure,
not the search form's predicate semantics, data completeness, units, null
values, source attribution, or any orbital solution. A separately reviewed
same-predicate positive control is needed before an exact-filename target
query. No holdout or RV inference was performed. Headers and native diagnostic
streams remain local pending a fuller privacy review.
