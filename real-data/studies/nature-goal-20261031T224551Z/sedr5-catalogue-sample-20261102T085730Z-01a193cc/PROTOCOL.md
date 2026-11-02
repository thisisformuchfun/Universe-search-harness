# SEDR5 catalogue sample preflight

Hypothesis: the survey's public sample CSV may reveal the actual `sexprv`
wire schema needed to make a later, exact-filename query for the already held
source. Success is a valid, bounded CSV header and response provenance. This
is a documentation/control lookup, not an observation of the held target.

The single fixed request is `GET https://dr5.lamost.org/sedr5/sexprv-sample.csv`,
linked by the [official release page](https://dr5.lamost.org/sedr5/). Limit
the response body to 262,144 bytes, one request, 30 seconds of curl transfer,
and no retry or redirect. Stop visibly on any transport, TLS, size, schema or
cleanup failure. Retain the exact request, native response and checksums in
this unique local directory; keep headers/diagnostics local pending privacy
review. Curl's body limit and 20 ms monitored header/diagnostic limits have
the same documented polling-overshoot caveat as the accepted prior capture.

Do not query the target, fit RVs, rank sources, change science criteria, use a
GPU or evaluate a holdout in this preflight. If a control sample is retrieved,
only its field names and structural row count will be inspected. The later
target query, if appropriate, needs its own frozen bounded request and review.
