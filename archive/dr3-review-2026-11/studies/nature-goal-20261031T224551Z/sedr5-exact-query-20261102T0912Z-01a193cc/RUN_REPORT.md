# SEDR5 catalogue control: stopped on live schema difference

On 2026-11-02 UTC, one bounded public control POST returned HTTP 200, TLS
verification result 0, no redirects and three CSV records. The run's parser
expected the downloaded sample's unprefixed 29-field header; the live query
instead returned the same ordered fields prefixed `sexprv_`. The parser stopped
with `ValueError`, the child exited, the lease was released, and **the target
was not requested**. This was a format mismatch, not an HTTP denial. The exact
original response and failure remain unchanged in `capture-v1/`.

Both independent reviewers checked that all three control filenames match the
literal sample filename and that the unique frozen sample tuple occurs once.
One reviewer additionally checked that the three saved sample and response
identity tuples match. No RV values were analyzed. This is a limited positive
form-control result, not proof of catalogue completeness or target identity.
See [independent audit](INDEPENDENT_CONTROL_AUDIT.md). A separately reviewed
new run is required to use an exact, tested mapping for the observed prefix.

The native response headers contain potentially session-bearing cookie fields.
Keep the entire header local and exclude it from portable archives, logs and
messages. Native diagnostic streams remain local pending full privacy review.
There was no holdout evaluation, ranking, scientific policy change or GPU use.
