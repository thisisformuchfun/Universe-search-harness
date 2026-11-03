# Independent offline roundtrip reviews

Accepted 2026-11-02 UTC for the non-production bookkeeping prototype. Both
reviewers independently verified the pinned product, six frame labels and
orientation result. All blue LOGLAM grids ascend and all red grids descend.
The result SHA-256 is
`145fb3c39056823ddbdf2a34484f724be930d2a2f71c53e4f6491b6199401a7d`.

The execution reviewer independently performed 36 field/frame permutations
using native FITS byte blocks: all six pixel vectors in each frame roundtripped
to their original bytes. Source size, modification time and SHA-256 remained
unchanged during the read. The science reviewer independently confirmed the
same dtype and byte roundtrips. Extensions 2 and 3's separate line arrays were
not transformed or validated.

This verifies reversible bookkeeping of the stored index relationships only.
It does not establish physical wavelength/pixel association, calibration,
source attribution, noise, RV accuracy or an independent orbit. No network,
GPU, holdout or input modification occurred in the independent reviews.
