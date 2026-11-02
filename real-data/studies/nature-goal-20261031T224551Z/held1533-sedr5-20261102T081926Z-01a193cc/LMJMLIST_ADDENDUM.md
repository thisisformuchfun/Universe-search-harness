# Exposure-list cross-check, independently reviewed

In the hash-pinned DR6 combined FITS primary header, `LMJMLIST` is
`82124924-82124952-82124981`; `NEXP_B=3` and `NEXP_R=1`. The header's own
comment describes the former as a local modified Julian minute list. These
three numbers match the three MJM labels in the independently retrieved
SEDR5 single-exposure product, each of which is listed for a blue and a red
arm. This reinforces the previously recorded shared observation lineage.

The official [LAMOST DR5 FITS description](https://dr5.lamost.org/v3/doc/data-production-description)
and [DR12 FITS description](https://www.lamost.org/dr12/v2.0/doc/lr-data-production-description)
describe `LMJMLIST` as a list of local modified Julian minutes of exposures,
and label `NEXP_B` and `NEXP_R` as valid blue and red exposure counts. They
do not, on this evidence, establish which SEDR5 frames contributed to the DR6
coadd or whether corresponding reductions retained the same underlying
exposure data. The DR5 and DR12 documentation is supportive context rather than
a substitute for a DR6-specific processing trace.

The match does not prove that Gaia DR3 1533365584518328576 is the only source
of fibre light, that separate frames have independent RV calibrations, or that
there is an independent orbit. The timestamp-convention discrepancy remains
unresolved. All scientific holds and release criteria remain unchanged.

Inputs: DR6 combined FITS `294101037.raw`, SHA-256
`2bfdfe2b133b1f5d9f880ae81be5002b48b7eb89cb8c45f538e048542cc32e06`;
SEDR5 product `product.raw`, SHA-256
`7a33d6a4ff8594c33b43181309bc5ad4e0739e6245943e06ba099172d04742de`.

The independent science reviewer verified the header, matching minute labels
and cited descriptions, and accepted this interpretation with the contributor
wording refinement incorporated above. Review recorded 2026-11-02 UTC.
