# Reference identity and wavelength-order check

Revision 2, prepared 2026-11-02 UTC for independent review, after the reference
transport. Revision 1 was not executed: reviewers found synthetic finite-coordinate,
contradictory-OBSID and ambiguous-frame-label guard gaps. Test whether the
hash-pinned FITS extension header matches the public sample's plan, spectrograph,
fibre and finite, sky-bounded catalogue coordinates, and whether distinct,
well-formed MJM/arm labels include the sample's `82211011`. This is nominal-minute
consistency, not proof of the exact sample exposure or shared photons. The sample's
filename and specid are catalogue identity strings; the FITS extension has no
OBSID card, so do not invent one; if a card is present, require it to match the
sample's exact integer. Matching catalogue coordinates do not supply
independent astrometry or prove exclusive light attribution.

Read the six-by-4,136 LOGLAM values and MJM/COLOR labels only; report finite,
strictly ascending, strictly descending, equal or mixed adjacent-pair counts
per frame without reordering. Counts include all LOGLAM elements, including any
provider-flagged pixels or undocumented finite sentinels; this does not inspect
PIXELMASK or establish a usable wavelength grid. Preserve date-header values and
comments, with their time-scale interpretation unresolved. Compare direction
descriptively with the earlier
held product. A match documents two products from the same instrument/pipeline,
not a universal convention or independent calibration. A mismatch does not
prove corruption. This does not examine flux, fit RVs, establish an orbit,
change a scientific criterion or evaluate a holdout.

Pin the raw reference product, original sample, capture result, code, protocol
and synthetic tests. No network, GPU, new source selection, input mutation or
model server is involved. Keep native transport headers local.
