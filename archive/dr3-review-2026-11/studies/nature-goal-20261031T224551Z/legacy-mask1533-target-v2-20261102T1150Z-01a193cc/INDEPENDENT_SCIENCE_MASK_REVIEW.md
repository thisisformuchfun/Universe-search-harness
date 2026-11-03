# Independent target-mask science review

On 2026-11-02 UTC `/root/ps1_science_review` independently verified raw SHA256 `cd1409e6d636e7bfa284f16ca985adfb151ff81a6c384485bb0f8feea9a061c4`, the physical headers before bounded reads, and FITS verification without warnings. The correct brick `1857p410` has an optical HCOMPRESS int16 3600x3600 mask and two uint8 WISE masks, with 100x100 tiles. A bounded 26x82 optical section was sufficient and did not load the full optical array. No producer CHECKSUM or DATASUM cards were present.

Numerical WCS matches the saved target-image brick grid after offsets (2381,109). Astropy's raw-numeric and frame-aware FK5/ICRS mappings differ by approximately 0.00801 arcsec at this field, but select identical 5x5 pixel sets at the three nominal positions. These two mappings do not establish the true source position or cover epoch, proper motion, parallax, orbital motion, PS1 errors or absolute calibration.

| Position | SATUR_R | SATUR_Z | ALLMASK_Z | MEDIUM |
|---|---:|---:|---:|---:|
| Gaia 2016 target | 0/25 | 25/25 | 21/25 | 0/25 |
| PS1 one-detection mean | 0/25 | 17/25 | 5/25 | 0/25 |
| Gaia 2016 bright neighbor | 25/25 | 25/25 | 22/25 | 25/25 |

[DR9's definitions](https://www.legacysurvey.org/dr9/bitmasks/) say SATUR_R/Z indicates saturation in at least one corresponding input image. The target z flags are consistent with the previously observed zero weights but do not prove their cause; 21/25 ALLMASK_Z and 25/25 zero-weight pixels are distinct measurements. The neighbor's positive r weights do not establish an unsaturated PSF reference given its r saturation flags. MEDIUM is based on the survey's Gaia mask and is not an independent detection. Clear bits do not certify pixel quality. Synthetic single, combined and signed 16-bit decoding checks passed independently. These facts do not establish a companion, fibre attribution, an orbit or a black hole.
