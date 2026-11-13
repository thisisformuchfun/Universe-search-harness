# Survey run 2026-11-12: review notes

> No new black hole or neutron star is claimed. Every source below is a held anomaly or an exclusion.

Input: all 443,205 Gaia DR3 `nss_two_body_orbit` solutions from ESA's bulk file (MD5 matches ESA's published checksum), plus `gaia_source` context for all 437,275 sources and the 195,315-row `binary_masses` table. Vetting evidence was fetched live on 2026-11-12/13; a replay from the recorded responses in `evidence/` gives identical tiers for all 1,547 candidates.

## Outcome

| | Astrometric | Spectroscopic (SB1) | Total |
| --- | ---: | ---: | ---: |
| Solutions scanned | 169,227 | 181,529 | 350,756 |
| Shortlisted (5th-percentile dark-companion mass at least 1.25 Msun) | 779 | 768 | 1,547 |
| `EXCLUDED_PUBLISHED_PRIOR` | 75 | 195 | 270 |
| `HELD_FAILED_VETTING` | 431 | 570 | 1,001 |
| `HELD_WITH_CAVEATS` | 273 | 3 | 276 |
| `HELD_SURVIVED_AUTOMATED_VETTING` | 0 | 0 | 0 |

Nothing survived every test. The most common failures: a hidden main-sequence pair can supply the SB1 mass (698), the published Shahaf et al. (2023) classification prefers a luminous companion (207), low orbit significance (205), a hierarchical triple reproduces the photocentre orbit (177), Gaia classifies the source as eclipsing (72).

## Sanity check on published positives

Of 31 tune-split controls and policy black holes, 23 passed the mass cut and all 23 were excluded as already published. Gaia BH1 and BH2 were recovered with 5th to 95th percentile dark-companion masses of 9.7 to 18.4 and 7.6 to 10.2 Msun. Where sources overlap, this engine's median minimum masses agree with the values published by Shahaf et al. (2023) to within about 2% (four sources checked by hand). The test split was not read.

## Closest to surviving

Six astrometric sources are held with exactly one warning and no failure. None has a Gaia radial-velocity amplitude, so the astrometric orbit could not be cross-checked. Masses are 5th / 50th / 95th percentiles of the companion mass required **if** the companion is dark and the catalogue orbit and primary mass are right.

| Gaia DR3 source | Solution | m2 if dark (Msun) | m1 | P (d) | e | G | The one warning |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `5843766042361427840` | Orbital | 1.64 / 1.81 / 2.03 | 1.52 | 873 | 0.26 | 13.1 | `primary_cmd_position`: primary is redder than the main sequence at its luminosity: evolved primary or uncorrected reddening (no extinction estimate) |
| `1334956997595864960` | OrbitalAlternative | 1.46 / 1.79 / 2.99 | 0.96 | 753 | 0.21 | 15.6 | `solution_type`: alternative or targeted-search solution, processed outside the main orbit pipeline |
| `1121443762310292096` | OrbitalAlternative | 1.44 / 1.71 / 2.11 | 1.08 | 530 | 0.36 | 15.5 | `solution_type`: alternative or targeted-search solution, processed outside the main orbit pipeline |
| `5351774995980250880` | Orbital | 1.42 / 1.60 / 1.90 | 1.57 | 678 | 0.29 | 13.9 | `ms_triple_excluded`: above the close main-sequence pair limit only within the uncertainty of the approximate mass-luminosity relation |
| `4600723410759259264` | Orbital | 1.31 / 1.40 / 1.49 | 1.03 | 1485 | 0.79 | 12.8 | `period_coverage`: period longer than the DR3 time baseline: orbit not fully covered |
| `2930237795567903104` | Orbital | 1.28 / 1.50 / 2.36 | 1.31 | 685 | 0.12 | 14.1 | `ms_triple_excluded`: above the close main-sequence pair limit only within the uncertainty of the approximate mass-luminosity relation |

`5843766042361427840` is the strongest: Shahaf et al. give it a 99.9% class-III probability, yet it is absent from their 177-source candidate table. It sits 0.3 mag redder than the main sequence at b = -8 deg with no extinction estimate, so the primary may be evolved, in which case the mass argument does not hold. A web search for the source ID returned nothing, which is not evidence of novelty.

## What the manual review changed

The first automated pass put 69 sources in the top tier. Reviewing them by hand found five ways the battery was too lenient. Each became a test or a guard, and the criteria version went from 1 to 2 before any result was reported:

1. About 20 "survivors" had median masses in the thousands of solar masses. Near-circular orbits are published with Thiele-Innes errors far larger than the values, held together by correlations of +-0.999999 in single precision. Sampling that covariance invents huge orbits. Such blocks are now refused and the orbit-size error is taken from the published significance.
2. Most remaining survivors had near-zero class-III probability in Shahaf et al. (2023), whose triple limit is 10 to 15% stricter than the approximation here. Their published probabilities are now a test, and the local limit carries a 15% margin.
3. Both SB1 survivors needed only 1.3 to 1.5 Msun, which two K dwarfs supply while adding under 15% of the light. A hidden-pair test now fails such cases.
4. The colour-magnitude position of the primary is now checked against the main sequence.
5. Short-period alternative solutions implying hundreds of solar masses now fail a plausibility bound.

Checking arXiv papers that have no VizieR table then showed that 30 held sources, including both former SB1 survivors, are printed in a 2026 spectroscopic follow-up paper (arXiv:2608.06453). The ID lists of six such papers are now bundled in `data/survey/literature_supplement.json` and used for exclusion.

## Not done

- No orbit refit. Summary data cannot validate an orbit; DR4 epoch astrometry can.
- No ADS full-text search (needs a token).
- The follow-up agent was not run on `agent_run/`: its live tools are pinned to the CDS hosts, which were unreachable from this environment, and no model key was available.
- The survey code is unsealed and has not had human review.
