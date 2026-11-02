# Independent archive identification evidence — 2026-10-31

All 14 authorized held Gaia DR3 sources were checked. **Two distinct public LAMOST LRS observations were found; one has a catalogue LASP radial velocity. No multi-epoch radial-velocity constraint was obtained. All sources remain held.** DR6 and DR11 copies of an obsid are the same observation.

| Gaia DR3 source | Public spectral identity | Observation | Measured evidence and limits |
|---|---|---|---|
| 1533365584518328576 | LAMOST J122251.51+405302.1; obsid 294101037; uid G14984010306277 | 2015-01-08; MJD 57030 | DR11 exact Gaia ID and 0.0201-arcsec positional match. Catalogue K3; g-SNR 4.4, r-SNR 3.45; fibermask 0. No DR11 AFGK stellar-parameter row. Spectrum is available, but weak signal limits interpretation. |
| 4491401821468887552 | LAMOST J172600.40+093330.7; obsid 664307135; uid G14348033118988 | 2018-05-18; MJD 58256 | DR11 exact Gaia ID and 0.4021-arcsec positional match. Catalogue K5; g-SNR 16.62, r-SNR 53.7. LASP heliocentric RV −5.31 ± 4.36 km/s. fibermask 128 means documented bit 8 NEARWHOPPER: near a problematic neighbouring fibre. |

RV units/frame and fibre-bit meaning were verified against [official DR11 product documentation](https://lamost.org/dr11/v2.0/doc/lr-data-production-description), Tables 2 and 7. The reported RV error is the catalogue uncertainty, not a new calibration. The retrieved DR6 spectra are preserved as VOTable products, with wavelength in Angstrom. No spectral fitting, line-profile validation, SB1/SB2 classification, or luminous-companion exclusion was performed.

The separate science review found source 4491401821468887552 already in [Li et al. 2026, arXiv 2610.34715v1](https://arxiv.org/html/2610.34715v1) with one RV. That paper's source archive has no per-epoch table identifying this obsid/date. **Independence of the paper's single RV and this LAMOST observation is unknown.** The paper, DR6 and DR11 must not be counted as three observations; a fitted periastron epoch is not an observation date.

## Verified coverage

| Service / actual selection | Parsed result |
|---|---|
| [SIMBAD Harvard TAP](https://simbad.cfa.harvard.edu/simbad/sim-tap/): exact 14 Gaia DR3 IDs, plus 14 separate 5-arcsec cones | Zero rows for each target; an independent known Gaia BH1 control returns one identified record. Empty rows were not confused with null-valued records. |
| [GAVO LAMOST DR6](https://dc.g-vo.org/tableinfo/lamost6.ssa_lrs): 14 indexed 5-arcsec cones | Two LRS rows above, zero MRS rows. Two HTTPS spectrum products retrieved and XML metadata inspected. |
| [Official LAMOST DR11 v2.0 TAP](https://lamost.org/dr11/v2.0/vo): exact 14 DR3 IDs in LRS general, AFGK stellar and MRS general tables | Two LRS rows, one stellar-parameter row, zero MRS rows. An independent coordinate-box query followed by a spherical 5-arcsec check found the same two LRS rows and no extras. |
| [GALAH DR4 Data Central TAP](https://datacentral.org.au/vo/tap): allspec exact 14 DR3 IDs | Zero rows, without adding a quality cut. |
| GAVO RAVE DR5: 14 5-arcsec cones | Zero rows. |

The other 12 source IDs and every target's scoped result are in `IDENTIFICATION_EVIDENCE.json`. Survey footprints, catalogue release dates, magnitude/SNR cuts, input-target selection and crossmatch completeness limit these searches. Positional checks used catalogue coordinates without a proper-motion epoch fit; the two positive LAMOST associations also have exact official DR3 IDs. Zero matches do not establish novelty or physical exclusion.

## Unavailable or incomplete

- **APOGEE DR17:** a documented [SkyServer API](https://skyserver.sdss.org/dr17/Support/Api) query using all 14 Gaia-linked 2MASS identifiers failed before HTTP response (curl 28, connection timeout, HTTP 0). No APOGEE non-detection is inferred. The parent evidence marks source 5991734159714775296's 2MASS association as shared (`number_of_mates=1`); even a future APOGEE match would need blend attribution.
- **El-Badry 2021 EDR3 wide-binary catalogue:** Harvard VizieR `J/MNRAS/506/2269/catalog` returned one valid empty result for `Source2=632497706010874240`. The other three exact-ID queries and two targeted cones timed out after 35 s with no body. Searches for the suggested 2852726284550996352 / 2852726284550996224 and 632497706010874240 / 632544645708760576 pairs are incomplete. No catalogue confirmation, rejection, bound-pair or triple claim is made.
- Newer LAMOST releases, exhaustive other-survey coverage, spectral model fitting and repeat-epoch measurements were not tested.

## Execution and reproducibility

51 bounded read-only retrieval attempts are retained, including failures and diagnostic schema/documentation requests. Fixed native Windows curl used HTTPS, certificate validation, no redirect following, 35-s request caps, 4-MB response caps, and at most three concurrent requests. Two observed same-provider spectrum redirects were inspected, then their explicit HTTPS destinations queried separately. No accounts, credentials, model endpoints, GPU, background jobs or production changes were used.

Initial GAVO unindexed geometry queries returned HTTP 500 with server query timeouts; using the documented indexed `ssa_location` field resolved this. SIMBAD's TABLEDATA format and GALAH's advertised `votable` format resolved format mismatches. The initially guessed GALAH route returned 404; the documented endpoint succeeded. These diagnostics and bytes are retained. Many LAMOST DR11 `TAP_SCHEMA.columns.description` strings are visibly attached to unrelated fields; scientific semantics therefore use official product documentation and actual named records, not those description strings.

Each request `NAME.json` contains exact URL/query, command, UTC timestamps, HTTP/curl/TLS status and raw/header SHA256. Raw evidence is never overwritten. `IDENTIFICATION_EVIDENCE.json` contains exact-string source IDs and per-source findings; `EVIDENCE_MANIFEST.json` hashes the package. Offline reproduction from the session root:

```powershell
.\.venv-astra\Scripts\python.exe followups/held14-20261031T214650Z/evidence/identifications/summarize_identifications.py
```

The offline check passed: 14 targets, 2 distinct LAMOST observations, 1 LASP-RV source, 0 multi-epoch-RV sources found, and all 51 retrieval records' body/header hashes verified. This script rewrites only the derived summary; immutable request evidence stays intact.

Next useful measurement is a quality-controlled additional RV epoch with known instrument/frame and independently checked target association. For the flagged 4491 spectrum, inspect original pixel/fibre quality before using it in an orbital fit. These are evidence needs, not adopted release criteria.

