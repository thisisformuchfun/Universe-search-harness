# SEDR5 follow-up of Gaia DR3 1533365584518328576

**Result: one related, publicly retrieved observation product; no new orbit or
black-hole candidate.** The original source remains held. All 14 original
anomalies remain held; two are already published compact-binary candidates and
novelty remains unresolved for the other 12.

The official SEDR5 archive returned a 550,080-byte FITS product. Its extension
header agrees with the previously saved DR6 combined product on plate
`HD122456N425117B01`, spectrograph 1, fibre 37, FK5/J2000 catalogue
coordinates and local observing interval. SEDR5 extension 1 does not contain
the DR6 numeric OBSID card. This evidence strongly supports the same fibre
observation, but does not establish which source supplied the light or which
frames contributed to the DR6 combined spectrum.

The product reports three blue and three red frame records; one record in each
arm has each of the MJM minute labels 82124924, 82124952 and 82124981. Each
reports a 1,500-second duration and zero fibre mask. Equal minute labels do not
prove exact simultaneity. These are same-night frame metadata, not independent nights. The
DR6 header reports three valid blue exposures and one valid red exposure; the
relationship to the SEDR5 frames is unverified. A zero fibre mask is not a
measurement-quality or blend validation. No flux or RV value was analyzed.

Using the [provider's Beijing-time MJM definition](https://dr5.lamost.org/sedr5/)
and a fixed UTC+08, uniform-day model gives nominal UTC minute labels 20:44,
21:12 and 21:41 on 2015-01-08. The provider's quantization and full time-scale
conventions are not established, so these are not exact start times or accuracy
bounds. Under the same conditional timezone interpretation, the SEDR5 header's
`DATE-OBS`, labelled UTC start, is 1,500.8 seconds later than its local
`DATE-BEG`. Its `MJD=57030` card is labelled local while the local start's
calendar day corresponds to 57031. DR6 separately labels its `DATE-OBS` as
median UTC and records MJD 57030 and LMJD 57031. Neither discrepancy was
silently corrected.

The product opens as one primary HDU and three binary-table extensions. The
[provider page](https://dr5.lamost.org/sedr5/) describes ASCII table
extensions, so the actual format must be inspected rather than assumed.
The [metadata output](metadata-v2/METADATA.json),
[inspection protocol](METADATA_PROTOCOL_V2.md),
[science and execution review](INDEPENDENT_METADATA_REVIEW.md), and
[capture audit](INDEPENDENT_CAPTURE_AUDIT.md) preserve the detailed evidence.

Four serial fixed HTTPS requests returned HTTP 200 with TLS verification and
no redirects; 956,275 response-body bytes were saved. The product SHA256 is
`7a33d6a4ff8594c33b43181309bc5ad4e0739e6245943e06ba099172d04742de`.
The 20-test capture suite and five-test metadata suite passed on Windows
Python 3.11.4; reviewers separately checked the bounded scope. Native headers
and diagnostic streams remain local pending full privacy review. The
previous 500-row reference run and historical holdout were not changed.

The [SEDR5 catalogue form](https://nadc.china-vo.org/data/data/general/sedr5/sexprv/f)
was inspected in a browser to identify a possible survey-measured RV lookup;
no catalogue query had been submitted when this report was written. Any such
measurement would reuse the same observation and would require source,
quality, timing and uncertainty checks. It cannot independently confirm an
orbit by itself.
