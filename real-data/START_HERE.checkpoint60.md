# Real-data black-hole triage handoff

This bundle contains the approved Gaia DR3 non-single-star orbital anomaly
triage harness, its original baseline, and a selected, source-linked research
handoff. It is not a general black-hole detector. The original transit,
gravitational-wave and anomalous-star domains remain disabled. No new black
hole or independently validated inner orbit is claimed.

The latest [review queue](studies/nature-goal-20261031T224551Z/zhou-mrt-20261102T1041Z-01a193cc/REVIEW_QUEUE_V5.md)
adds a finite check against the full 19-candidate Zhou–Gu 2026 list: none of
the original 14 IDs matches that paper's 17 Table 2 or two Type I IDs. This
does not establish novelty. The source-linked report, public MRT body, exact-ID
comparison, provenance and tests are included under that study directory.
From this directory `python -B portable_zhou_check.py` independently repeats
the finite ID/Type comparison using the included MRT and frozen held-ID file;
it does not revalidate the publisher-page association. Its four preview pairs
and two Type I IDs are previously reviewed constants, not rederived from the
publisher page during this check. The page body and its native headers remain
on the originating PC, with hashes and links recorded.

On Windows, extract the bundle to a short path such as `C:\universe-handoff`.
An initial check encountered WinError 267 when launching a module-origin check
before the next test group from an existing 309-character working directory;
the exact OS cause was not isolated.

`baseline/original-v1.zip` is a byte-identical copy of the original delivered
ZIP, SHA-256 `c7bcf827bf4ddbdfec7fde5734594c879d18f21a0fb0d0562e17ba0c9ba950c1`.
`harness/` is the separately patched integration copy; it is **not** the
original ZIP. The approved patch and independent review are under `review/`.
Its guard is `558cef0d2d1cab72110c03e2089009ef8cdaf031c63247f8e345bfbbbb81953c`.
`artifacts/Universe_Search_Harness_Checkpoint53_20261102_01a193cc.zip` is the
previously audited full historical handoff,
SHA-256 `bff3862e1f6e42e31c94795f0ec547c7c7d0b6c07c6c8905f0c03405a2669d20`;
follow its own `START_HERE.md` for its nested overlays. Its older known-pattern
privacy scan is limited; the earlier audit records 275 inherited native request
records, 260 containing absolute workspace paths. The original downloaded ZIP
on the PC was not altered.

The preserved 500-row snapshot is quality-selected, not a representative sky
census: 17 anomalies, 14 held, two known black holes and one refuted case
excluded, zero released. The 14-object source matrix and latest queue are in
`studies/nature-goal-20261031T224551Z/`. Two of the 14 were already published compact-binary candidates and
are controls; novelty for the remaining 12 is unresolved. The source-linked
records and experiment ledger are evidence, not a fresh test set. Authoritative
scientific holdout custody remains on the originating PC and is quarantined
`DO_NOT_EVALUATE`; do not reset it or reuse historical sources as heldout.

`evidence/` contains the two selected public SEDR5 FITS products, the earlier
DR6 combined spectrum and a public sample CSV. The exact public catalogue
response bodies are in `studies/nature-goal-20261031T224551Z/`. The two
held-fibre queries returned HTTP 200 with zero-byte bodies;
these are unresolved, not confirmed catalogue nonmatches. The reference and
held products show numerically ascending blue and descending red wavelength
grids without applying a pixel-quality mask. The
research helper under `research/orientation/` applies a common reversible
permutation to six pixel arrays; this is index bookkeeping only, not validated
physical alignment, wavelength calibration, source attribution or RVs.

The exact source queries, bounds, prior identity checks, data hashes, limitations
and reviews are in `studies/nature-goal-20261031T224551Z/`. Native response headers and curl diagnostics from
the recent requests are deliberately excluded because some headers contain
potentially session-bearing cookies. No model weights, local environments,
credential files or arbitrary private caches were selected for this bundle.
Some selected provenance and request records contain absolute workspace paths;
review these paths before sharing the handoff with others. The known-pattern
scan of selected text is limited and is not proof that no secret exists.
`PORTABLE_MANIFEST.json` lists included members and their SHA-256 hashes.

For the runnable harness, use an isolated compatible Python environment and the
project's pinned `harness/requirements.lock`, then from `harness/` run:

```text
python -B -m harness2.cli.universe verify
```

This is a guard/provenance check, not a fresh heldout evaluation. Do not reseal
after a failure. The original test suite includes a historical real-snapshot
regression and must not be described as an untouched holdout. The bundled
snapshot lacks full covariance, so it is not a valid GPU covariance benchmark.
Do not use a model server or GPU without the recorded coordination and lease
rules; the user-managed server was not changed in this work.

For an offline paired-array reproducibility check, the recorded environment
was Windows Python 3.11.4 with NumPy 2.3.5 and Astropy 7.1.1; its selected
distribution hashes are in `requirements-fits.lock`. Other platforms or Python
builds need independently verified compatible distributions and lock hashes.
Run `python -B portable_check.py` from this directory.
It reads only the two included FITS products and checks hashes and in-memory
byte roundtrips. To repeat the synthetic helper tests, change to
`research/orientation/` and run `python -B -m unittest -v test_orientation_v1`.
The historical acquisition scripts under `studies/` retain original paths and
are archival evidence, not one-click replay commands; native headers remain
only on the originating PC. Direct links from the root report, current queue and
source matrix are included at their original relative paths. Older linked
records may require reconstructing the historical nested overlays.
