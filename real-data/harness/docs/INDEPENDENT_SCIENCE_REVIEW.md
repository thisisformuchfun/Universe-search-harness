# Independent scientific review — repaired Universe harness

## Decision
**Accepted as a bounded real-Gaia catalog triage and review-ranking harness**, after concrete fixes and independent regression tests. This is not acceptance as a validated black-hole discovery pipeline, an orbital-refitting pipeline, a calibrated detector, or evidence of previously undiscovered objects.

## What changed meaningfully
The production path no longer uses synthetic injected timing/masses, arbitrary FAP or known-answer detection. It ingests real archived measurements, retains raw bytes/provenance, computes the photocentre observable, excludes known/prior-studied objects and leaves unknowns held. A constrained proposal loop changes ranking weights, not scientific release rules. The ranking objective is an explicit measurement-quality heuristic; an improvement is not detection accuracy or discovery yield.

## Independently executed tests
`tests/test_science.py` added at implementer's request;10tests passed2026-10-31~20:52UTC:
1.500real snapshot rows,17above threshold,14holds/2knownBH/1refuted exclusion; all17observables match audited original to1e-12.
2.Orbital and AstroSpectroSB1 full-mask covariance ordering and column-major offdiagonal mapping (synthetic UNITfixtures, not real sky covariance).
3.Fractional/reduced bit masks rejected; unsupported alternative parameterizations unavailable.
4.Invalid correlation lengths, missing/nonfinite entries, impossible coefficients and indefinite matrix rejected.
5.Adjacent IDs above2^53 preserved; Unicode/numeric/scientific-notation IDs rejected.
6.Invalid physical inputs/uncertainties rejected.
7.Covariance propagation deterministic and clearly not a mass posterior/BH probability.
8.Derived MonteCarlo overflow fails closed.
9.No catalog match remains unknown; GaiaBH3 explicitly excluded.
10.End-to-end frozen reviewbudget used and overlapping testsourceIDs rejected even after changed dataset hash.

## Six concrete defects closed
- int() silently accepted fractional bit_index8191.9: now exactinteger required.
- MC derivedoverflow could emit nonfinite quantiles: now filtered/reported or rejected.
- Unicode decimal IDs passed detector then failed ASCIIpartition: ASCII-only now.
- Known-object list omitted GaiaBH3: explicit sourced exclusion added.
- Holdoutledger dataset-hash-only allowed overlap afterrefresh: consumedtestsourceIDs now tracked.
- Heldoutmetric defaultedbudget20 despitecustomrunbudget: frozenrunbudget now used.

## Evidence and limits
ESA parameter schema:
https://gea.esac.esa.int/archive/documentation/GDR3/Gaia_archive/chap_datamodel/sec_dm_non--single_stars_tables/ssec_dm_nss_two_body_orbit.html
ESA quality caveats:
https://gea.esac.esa.int/archive/documentation/GDR3/Data_analysis/chap_cu4nss/sec_cu4nss_combined/sec_cu4nss_combined_caveat.html
GaiaBH3 discovery paper/sourceID:
https://www.eso.org/public/archives/releases/sciencepapers/eso2408/eso2408a-panuzzo-et-al.pdf

The original snapshot has no full correlation vectors. A live ESA single-source vectorformat check timedout in this review; actual live fullcovariance path is not empirically verified by these tests. Strict unsupportedformat→unavailable avoids invented errors. Even correctly propagated catalogcovariance is only a Gaussian approximation, not independently validated orbit/light assumptions. Knownlist+twofinitecatalogs are explicitly incomplete; conservative studyexclusion can exclude nonBH objects. No automatic release or novelty proof is claimed. No GPU, RTX4090 throughput, local-model quality, or freshdatasetrun is certified by this science review. Other execution/security reviewers own packaging/network/CLI operational coverage.

Published Glurbsor website stays the October19bounded historicalsnapshot; this repair does not silently update it or publish new candidateclaims.
