# SEDR5 metadata inspection protocol, V2

Scope: describe the retrieved SEDR5 FITS metadata beside the previously saved
DR6 combined-spectrum header. Do not fit spectra, estimate radial velocities,
rank sources, change scientific criteria, or evaluate the holdout.

The SEDR5 product SHA256 is
`7a33d6a4ff8594c33b43181309bc5ad4e0739e6245943e06ba099172d04742de`.
The previously saved DR6 combined-product SHA256 is
`2bfdfe2b133b1f5d9f880ae81be5002b48b7eb89cb8c45f538e048542cc32e06`.
Read selected identity and time header cards and only the table metadata
columns MJM, COLOR, EXPTIME and FIBERMASK. Preserve source files unchanged.

The [provider documentation](https://dr5.lamost.org/sedr5/) defines MJM as
minutes from the stated epoch in Beijing time to exposure start. Construct
nominal minute labels under fixed UTC+08:00, uniform 1,440-minute civil days
and no leap-second modeling. These labels are not demonstrated exact exposure
starts or accuracy bounds; the provider's quantization and full time-scale
conventions remain unverified. Compare local DATE-BEG with DATE-OBS labelled
UTC conditionally, retaining any discrepancy without correcting either value.
Retain the DR6 DATE-OBS value and its separate median-UTC comment.

Matching plate, fibre and catalogue coordinates support an association between
the observation records. They do not prove shared retained photons, identical
release calibration, or that the Gaia source was the only light in the fibre.
Blue and red rows at the same time are separate arms, not separate nights.
Zero fibre-mask values do not validate source attribution or RV quality.
An absent OBSID card in one extension does not establish its absence elsewhere.

Write derived metadata into a fresh, exclusively created local directory.
The historical scientific holdout remains quarantined.
