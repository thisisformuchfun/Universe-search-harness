# Independent offline result reviews

Accepted 2026-11-02 UTC as descriptive numerical evidence. The execution
reviewer independently reproduced every reported count and proxy median within
`2e-15` tolerance; 96 selected FLUX/INVVAR/LOGLAM/PIXELMASK elements agreed
with independently decoded big-endian FITS bytes. The source and result
hashes matched; shape and labels were verified. No data or policy changed.

Both reviewers independently checked wavelength ordering: all three blue
frames have 4,135 strictly increasing adjacent pairs, and all three red frames
have 4,135 strictly decreasing pairs. Every frame has 4,136 finite, distinct
LOGLAM values. The red ordering is not a constant sentinel. The
[provider](https://dr5.lamost.org/sedr5/) describes a vacuum, heliocentric
wavelength convention but does not specify storage direction. Descent is not
evidence of corruption or of a correct wavelength solution. Neither audit
establishes physical alignment, source attribution or calibrated RV precision.

The signed FLUX×sqrt(INVVAR) median is only the documented conditional numeric
proxy, not validated S/N, usable-pixel yield, a quality gate or an RV claim.
The three minute labels are one observing sequence; six arms are not six
independent orbital epochs. Finite sentinels, sky, blends, correlated noise,
calibration and input units remain unresolved. No network, GPU or holdout
evaluation was used in this review.
