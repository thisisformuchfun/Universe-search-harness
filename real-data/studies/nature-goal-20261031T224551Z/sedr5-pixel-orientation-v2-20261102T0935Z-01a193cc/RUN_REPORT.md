# Paired pixel-array orientation prototype

The already saved SEDR5 product has three blue wavelength arrays in ascending
order and three red arrays in descending order. The reviewed research-only
helper reversed each descending frame's six stored per-pixel vectors together,
then reversed the operation. Every one of the 36 field/frame combinations
returned to its original bytes and dtype in memory; the source file was not
changed. Eight synthetic tests and two independent reviews passed.

This is reversible bookkeeping of the existing index relationships, not proof
that the input fields are physically aligned or calibrated. The separate
per-line arrays were not transformed. No spectrum was fitted, no RV or
companion inferred, and no release criterion, ranking or holdout changed.
The code is an unadopted prototype, not part of the production harness.

See the [protocol](PROTOCOL.md), [result](RESULTS.json),
[independent review](INDEPENDENT_POST_CAPTURE_REVIEW.md) and
[previous pixel inventory](../sedr5-pixel-feasibility-v2-20261102T0928Z-01a193cc/RUN_REPORT.md).
