# Offline SEDR5 pixel feasibility

The hash-pinned public FITS product contains six arrays of 4,136 pixels.
The tested descriptive check found finite stored FLUX, INVVAR and LOGLAM,
positive stored INVVAR and numeric zero PIXELMASK across every array element.
These counts do **not** establish valid science pixels: finite sentinels, mask
conventions, units, calibration, background, blending and correlated noise
remain unresolved. The recorded signed FLUX×sqrt(INVVAR) medians are an
unvalidated numeric proxy, not S/N or an RV-precision estimate.

Independent checks found three blue wavelength grids strictly increasing and
three red grids strictly decreasing. The provider's documentation does not
specify ordering direction; this alone does not show a bad solution. Any later
reorientation must preserve all associated pixel vectors together. The data
cover one observing sequence, not six independent orbital epochs.

No RV fit, new orbit, black-hole discovery, release criterion or holdout
evaluation resulted. See [protocol](PROTOCOL.md), [result](RESULTS.json),
[review](INDEPENDENT_POST_CAPTURE_REVIEW.md) and the 11 synthetic tests. The
initial unrun V1 is preserved after reviewers found numerical edge cases.
