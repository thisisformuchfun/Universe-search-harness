# Clarification of pixel-value wording

The preserved V1 and V2 observation JSON files say a pixel maximum is “not a
flux.” That wording is imprecise. The [PS1 cutout documentation](https://outerspace.stsci.edu/spaces/PANSTARRS/pages/298812251/PS1+Image+Cutout+Service)
describes stack FITS cutouts as converted to a linear flux scale. A sampled
pixel can therefore be a flux-scaled image value; it is not, by itself, an
integrated and calibrated source-flux measurement, a source flux ratio, a
detection significance, an isolated-star identification, or a PSF fit.
The original JSON files remain unchanged and must be read with this
clarification. No numerical results or scientific dispositions change.
