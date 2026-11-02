# Independent reference metadata and ordering reviews

Accepted 2026-11-02 UTC for this exact public reference product. Both reviewers
independently verified the unique sample row against the FITS extension's plan,
spectrograph, fibre and finite bounded catalogue coordinates. The sample's
nominal minute appears once in each arm among six distinct label pairs; the
extension has no OBSID card. These are catalogue and nominal-minute consistency
checks, not proof of exact exposure/photon identity or exclusive stellar light.

Both reviewers independently found three blue grids with 4,135 increasing
adjacent pairs and three red grids with 4,135 decreasing pairs, all with 4,136
finite values and no equal pairs. The execution reviewer also checked 24
selected LOGLAM values against native big-endian FITS bytes; product hash,
size and modification time remained unchanged. The held product has the same
per-arm pattern. The two products are different observations from the same
instrument and pipeline; this is not independent calibration or proof of a
universal convention. PIXELMASK was not applied, and finite sentinels remain
possible. No flux, RV, orbit, novelty or disposition was inferred.

The header comments and original date strings are preserved. Under a nominal
fixed UTC+08, uniform-day interpretation, DATE-OBS is 1,501.12 seconds later
than converted DATE-BEG. Its meaning remains unresolved; nothing was corrected.
Result SHA-256
`1fe80f1410d5e7758def6cdcc16172360a37251352690c71f07a92994b2ac455`.
No network, writes, GPU or holdout were used in these independent reviews.
