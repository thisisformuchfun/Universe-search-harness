# Gaia DR4 readiness

Status on 3 November 2026: the harness runs on Gaia DR3. The DR4 tooling below is in place, and no guarded code or policy has been changed for DR4.

## What is coming

- ESA has scheduled Gaia DR4 for Wednesday 2 December 2026 ([Gaia news 2026](https://www.cosmos.esa.int/web/gaia/news-2026)).
- It covers 66 months of observations. DR3 covered 34.
- It is the first Gaia release to publish epoch data: per-transit astrometry, photometry and spectroscopy.
- Confirm the archive schema name, table names and data model on the day. This repository assumes the schema follows the `gaiadr2`, `gaiadr3` pattern and is called `gaiadr4`. That is unconfirmed, so pass the real name with `--release`.

## Why it matters here

DR3 gives one catalog orbit solution per source. The pipeline can therefore only triage, computing f_phot from the Thiele-Innes coefficients, and the agent can only check quality flags and the literature. Epoch astrometry changes that:

- Orbits can be refit from the measurements instead of trusting one catalog solution.
- The alternatives that currently force a hold can be tested directly: bad fits, blended light, luminous companions and triples.
- DR3 candidates that DR4 confirms or refutes become new controls. Refuted ones would be the first labeled negatives, which the current positives-only control set lacks.
- The 14 held sources get their strongest test so far. A DR4 orbit that keeps a held source anomalous leaves it held for human review. It is not a discovery (see `AGENTS.md`).

## Ready now

| Item | Path | What it does |
| --- | --- | --- |
| Readiness checker | `scripts/dr4_readiness.py` | Compares a release's archive schema with every table and column the harness queries, lists candidate epoch and cross-release tables, and samples NSS covariance layouts against the parser |
| Watchlist | `data/dr4/watchlist.csv` | The 54 DR3 sources to pull first: 14 held and 42 controls (2 Li 2026 sources are both). Regenerate with `scripts/dr4_readiness.py watchlist --out data/dr4/watchlist.csv` |
| Daily watch | `../.github/workflows/dr4-watch.yml` | Checks the archive once a day, runs DR3 as a positive control first, and uploads the reports. It fails when DR4 appears with a schema the harness cannot read unchanged |
| Tests | `tests/test_dr4_readiness.py` | Offline tests, including drift checks against the connector and the agent policy |

```sh
cd harness
python scripts/dr4_readiness.py requirements                        # what the harness reads, offline
python scripts/dr4_readiness.py check --release gaiadr3 --sample 0  # positive control
python scripts/dr4_readiness.py check --release gaiadr4 --out runs/dr4-readiness.json
```

### Reading a check report

| Status | Meaning | Exit |
| --- | --- | --- |
| `NOT_PUBLISHED` | The archive has no tables under that schema yet | 0, or 1 with `--require-published` |
| `SCHEMA_COMPATIBLE` | Every column the harness selects exists, and sampled covariance layouts are accepted by the parser. This is not a science validation | 0 |
| `NEEDS_PARSER_REVIEW` | The columns exist, but sampled `Orbital`/`AstroSpectroSB1` rows have a `bit_index` or `corr_vec` layout the parser rejects, or no such rows were found | 1 |
| `INCOMPATIBLE` | A table or selected column is missing, so DR3 queries would fail. `missing_core_columns` lists the ones the science cannot do without | 1 |
| `ARCHIVE_ERROR` | The request failed. That says nothing about whether the release exists. Retry later; never substitute cached or simulated data | 2 |

`candidate_tables` lists table names containing words like `epoch`, `neighbourhood` or `dr3`. They are pointers for a human to read in the data model, not interpretations.

## DR3 assumptions in guarded code

All of these are guarded (`AGENTS.md` rule 2). They change in one reviewed PR, after the checker has run on the real DR4 schema.

| File | DR3 assumption | Expected change |
| --- | --- | --- |
| `harness2/universe/connectors/public_archives.py` | `gaiadr3.nss_two_body_orbit` in `nss_query`, `gaia_ranked_pilot`, `gaia_schema`, `probe`; `gaiadr3.gaia_source` in `gaia_context`; `query_gaia_dr3_tap`; DR3 ID column names in `ID_FIELDS` | Take the release as a parameter, keeping the DR3 path reproducible |
| `harness2/universe/detectors/signal_pipeline.py` | `COVARIANCE_ORDERS` and `EXPECTED_BITS` accept only the exact DR3 layouts (66 or 105 correlations) | Extend only after the check's layout report and the DR4 data model agree |
| `harness2/agent/tools.py` | SIMBAD query `'Gaia DR3 <id>'`; tool descriptions and errors say DR3; `gaia_quality` reads `policy.gaia_release` | Literature tools keep DR3 identifiers until SIMBAD and VizieR index DR4 IDs |
| `harness2/agent/loop.py` | System prompt says Gaia DR3 | Name the release the run uses |
| `harness2/cli/universe.py` | SIMBAD review links use `Gaia+DR3+` | Same as tools |
| `policy/agent_tools.json` | `gaia_release: gaiadr3`, `gaia_quality_columns`; VizieR catalogs list DR3 IDs | Change `gaia_release` only after the check passes |
| `policy/scientific_policy.json` | DR3 caveats URL; the f_phot threshold of 3 is a DR3 triage default | Link DR4 caveats; review the threshold against DR4 uncertainties |
| `data/pilot/*`, `data/controls/controls_v1.json` | DR3 snapshot and controls keyed by DR3 IDs | Leave unchanged. DR4 gets new files |

The dashboard snapshot (`dashboard/src/snapshot.json`) is also DR3 and is not guarded.

## Release-day runbook

0. **Before 2 December**, from a machine with archive access, run `check --release gaiadr3 --sample 2000`. It confirms the checker against a known schema and answers an open question in `SCIENCE.md`: whether live DR3 `corr_vec` values use the compact layout the parser accepts or the nominal 231-entry storage.
1. **Check DR4.** Run `check --release gaiadr4 --out runs/dr4-readiness.json`. Expect a heavily loaded archive. Treat `ARCHIVE_ERROR` as a failure and retry later.
2. **Read the data model** for each missing column and each table under `candidate_tables`. Record decisions, with links, in `docs/DR4_SCHEMA_NOTES.md`.
3. **Map identifiers.** Gaia `source_id` values can change between releases. DR3 shipped `gaiadr3.dr2_neighbourhood` for DR2 to DR3; use the official DR4 equivalent to map every watchlist ID. Never assume a DR3 ID names the same source in DR4, and don't match on position alone: the bundled snapshot has no proper motions.
4. **Take a snapshot.** Pull the watchlist sources (NSS orbit, `gaia_source`, epoch astrometry) into a new dated snapshot under `data/dr4/`, with its own manifest and hashes. The DR3 baseline in `AGENTS.md` rule 12 must still reproduce.
5. **Change the code in one reviewed PR:**
   - make the connector release-aware
   - set `gaia_release`
   - add covariance layouts
   - update prompts and tool descriptions
   - add an `epoch_astrometry` tool that takes validated arguments only (`AGENTS.md` rule 7)
   - add tests
   
   After human review, run `python scripts/seal_release.py`.
6. **Build new controls.** Create `data/controls/controls_v2.json` (a new file) from DR3 candidates that DR4 confirms or refutes, with a fresh tune/test split. The one-shot test ledger is keyed by the controls hash, so v2 gets exactly one test run of its own.
7. **Record fixtures.** Run one `--tools record` pass on DR4 and commit the fixtures so reruns are free.
8. **Update docs.** Refresh the README, this file and the dashboard. Remove the daily watch workflow once the switch is merged.

## Rules that do not change

- The agent has no discovery verdict, and DR4 does not add one.
- No literature match is not novelty. Expect SIMBAD, VizieR and ADS to lag DR4 identifiers for months.
- A run labeled live uses live data. If the archive is overloaded, the run fails; it does not fall back to cached or simulated records.
- The test split is spent once.
