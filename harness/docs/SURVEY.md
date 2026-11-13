# Whole-catalogue survey and vetting

`harness2-survey` searches the entire Gaia DR3 `nss_two_body_orbit` table instead of a 500-row sample, through two independent channels, and then runs an automated vetting battery on what it finds. It is additive: the sealed triage path, policy, controls and the 500/17/14/2/1/0 baseline are unchanged.

> [!IMPORTANT]
> The best possible outcome of vetting is `HELD_SURVIVED_AUTOMATED_VETTING`. That is still a held anomaly for human review. No tier means "new black hole", and "no literature match" is recorded as exactly that, never as novelty.

## Commands

```sh
cd harness
harness2-survey acquire --store data/cache/bulk          # once: bulk table plus context, about 3 minutes
harness2-survey run --store data/cache/bulk --out runs/survey-YYYYMMDD
harness2-survey bench --store data/cache/bulk --backends numpy torch:cpu
```

`run` writes `summary.json`, `review_queue.csv`, `candidates.json`, `vetting.json`, `controls_check.json`, `provenance.json`, `evidence_index.json`, `run_manifest.json` and an `agent_run/` directory that `harness2-agent investigate --run <out>/agent_run --held` can read.

To rerun vetting without touching the network, point at recorded responses: `--evidence replay --evidence-dir <earlier run>/evidence`. A replayed run says so in `summary.json` (`vetting_evidence_mode`) and in every provenance entry.

## What changed against the sealed pipeline

| | Sealed `harness2-universe run --live` | `harness2-survey` |
| --- | --- | --- |
| Acquisition | TAP pages of 500 rows, two pages by default | ESA's bulk file for the whole table, checked against ESA's published MD5; context pulled in parallel ID ranges with an exact expected ID set per range |
| Rows searched | 500 to 1,000 | all 443,205 solutions |
| Channels | photocentre mass function | astrometric (Orbital family, AstroSpectroSB1) and spectroscopic (SB1, SB1C) |
| Statistic | `f_phot`, no primary mass | minimum dark-companion mass using a primary mass, with covariance and primary-mass uncertainty propagated |
| Compute | one row at a time | batched NumPy on a thread pool, or PyTorch on CPU, CUDA or MPS |
| Follow-up | one archive query per candidate per tool | one query per few hundred candidates |
| Vetting | none; everything above threshold is held | about 20 tests per candidate, four tiers |

## Find stage

For every astrometric solution the engine computes the photocentre semi-major axis and `f_phot` with the same algebra as the sealed code (tested to machine precision on the bundled snapshot), then solves `m2^3 / (m1 + m2)^2 = f_phot` for `m2`: the companion mass required **if the companion is dark and the orbit and primary mass are right**. The spectroscopic channel does the same with the SB1 mass function at `sin i = 1`.

The primary mass comes from, in order: Gaia DR3 `binary_masses`; an approximate main-sequence relation from the dereddened absolute G magnitude; a broad prior when the primary looks evolved. The source is recorded per candidate, and anything but the first is a vetting warning.

Uncertainty is a Monte Carlo over the published covariance (astrometric) or the diagonal errors (SB1), plus a lognormal primary-mass error. Correlations are published in single precision; when the sampled block is close to singular, or the Monte Carlo median drifts from the catalogue value, the covariance is refused and the orbit-size error is taken from the published significance instead (a vetting warning). A coarse 256-draw pass covers every row above a prefilter; rows near or above the cut are redone with 4,096 draws. A row is shortlisted when the 5th percentile of `m2` is at least 1.25 Msun (and, for SB1, above the primary mass).

All thresholds live in `harness2/survey/criteria.py`, with a history of every change and why. Version 1 was fixed before the first full run; version 2 tightened the search and vetting after the first manual review and before any result was reported. The hash is in every `run_manifest.json`. They are triage defaults, not validated physical cuts.

## Vet stage

Vetting runs automatically inside `run`: whenever at least `--vet-after` shortlisted candidates are waiting (25 by default) and again at the end. Each test returns PASS, WARN, FAIL or NA with the numbers it used.

| Test | Looks for |
| --- | --- |
| `orbit_significance`, `orbit_goodness_of_fit`, `period_coverage`, `parallax_quality`, `solution_type` | an unreliable orbit |
| `covariance_propagation`, `primary_mass_basis` | weak inputs to the mass estimate |
| `primary_cmd_position`, `mass_plausibility` | a primary off the main sequence; an implied mass no stellar remnant has |
| `independent_amrf_classification` | disagreement with the class probabilities published by Shahaf et al. (2023) for about 101,000 orbits |
| `sb1_hidden_pair` | an SB1 mass that two fainter main-sequence stars could supply unseen |
| `ms_companion_excluded`, `ms_triple_excluded` | a luminous companion or a hierarchical triple that reproduces the photocentre orbit (Shahaf et al. triage logic, approximate mass-luminosity relation) |
| `rv_amplitude_consistency` | Gaia's own radial velocities moving much less, or much more, than the astrometric orbit requires |
| `astrospectro_darkness` | for combined solutions: a photocentre orbit smaller than the primary's spectroscopic orbit, which means the companion emits light |
| `sb1_rv_range_consistency`, `sb1_sampling`, `sb1_known_failure_modes` | spurious or poorly sampled SB1 orbits, hot or broad-lined primaries, short-period contact systems |
| `blend_image_parameters`, `blend_neighbours`, `colour_excess` | blended light |
| `gaia_variability_tables`, `other_nss_solutions`, `flame_evolutionary_stage` | conflicting Gaia classifications |
| `prior_literature` | the policy known-object list, the bundled catalogues, verified VizieR catalogues, source IDs printed in six arXiv papers that have no VizieR table, and the SIMBAD bibliography |

Tiers, from worst to best:

| Tier | Meaning |
| --- | --- |
| `EXCLUDED_PUBLISHED_PRIOR` | already in a compact-companion catalogue or discussed in that context |
| `HELD_FAILED_VETTING` | at least one FAIL |
| `HELD_WITH_CAVEATS` | no FAIL, but a WARN, or a core test that could not be run |
| `HELD_SURVIVED_AUTOMATED_VETTING` | nothing found by these checks; still held |

If SIMBAD or a catalogue cannot be reached, the literature test is NA and the candidate cannot reach the top tier. A failed archive call is never replaced by an old answer.

## First full run

`runs/survey-dr3-20261112/` holds the first run and [review notes](../runs/survey-dr3-20261112/REVIEW.md). Of 350,756 solutions scanned, 1,547 were shortlisted; 270 were excluded as already published, 1,001 failed vetting, 276 are held with caveats and none survived every test. The find stage takes about 10 s on four CPU cores, and vetting 1,547 candidates takes about two minutes live or 15 s replayed.

`bench` on 2,000 real rows at 4,096 draws each: sealed per-row code 3.0 s; vectorized NumPy 1.3 s while also computing the companion mass, AMRF and predicted RV amplitude per draw; PyTorch on CPU 2.8 s. Most of the end-to-end gain comes from bulk acquisition and the coarse-then-refine Monte Carlo, not from the kernel.

## Sanity check on published positives

`controls_check.json` reports how the tune-split controls and the policy black holes fare. It never reads the test split, so that split stays unspent, and its result must not be used to change `criteria.py`.

## Limits

- The vetting battery uses catalogue summary data only. It cannot refit an orbit. DR4 epoch astrometry is the real test.
- The main-sequence limits use an approximate mass-luminosity table. They are triage, and they do not apply to evolved primaries.
- The literature check is a finite list. `data/survey/prior_catalogues.json` names what was verified and, under `known_gaps`, the relevant papers that are not on VizieR.
- SB1 correlations are not propagated.
- GPU timings have not been measured in this repository. The PyTorch path is tested on CPU only and gives the same numbers as NumPy.
- The survey modules are new code. Until a maintainer reviews them and runs `scripts/seal_release.py`, every run manifest reports `survey_code_sealed: false`.
