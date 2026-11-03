# Original 14: source-by-source evidence matrix

All 14 remain held. **U** means novelty remains unresolved: the specific
literature checks described below did not establish a match, but they cannot
establish that a source is unreported. **P** means already published as a
compact-binary candidate. “No RV recovered” means no independently attributable
epoch was found in the searches performed, not that no spectrum exists.
The common next need is calibrated, source-attributed spectroscopy at multiple
separated phases with line-profile and luminous-companion checks; no new
observations are scheduled by this report.

| Gaia DR3 source | Literature and useful independent measurement | Material risk | Next decisive test or stopping reason |
|---|---|---|---|
| 1533365584518328576 | U. One existing LAMOST 2015 spectrum has pipeline `z=-0.00023659`, error `0.00001158`; its approximate optical `cz` is −70.93 km/s, scaled error 3.47 km/s. No LASP RV row. | g/r S/N 4.4/3.45; velocity frame/calibration unresolved. The LAMOST PS-ID value matches a one-detection PS1 row about 1.52″ from Gaia 2016; source/fibre association remains unresolved. XP class 1 is not a confirmed binary. | Validate this spectrum with suitable low-S/N controls and obtain independent, source-attributed RV epochs; a single uncalibrated redshift cannot test the orbit. |
| 1538284425878995712 | U. No independent RV recovered. A conditional two-epoch Gaia forecast is a measurement-design calculation, not observed velocity. | Most Gaia XP BP/RP transits are blend-flagged; the published class-0 fit does not exclude a luminous secondary. | Deblended, component-sensitive multi-epoch spectra; propagate the Gaia orbital uncertainties when choosing phases. |
| 2245423750054837888 | U. No independent RV recovered; PS1 has separate catalog detections near this source and a 5.465″ neighbor. | The neighbor is 1.32 G mag fainter; PS1 astrometric calibration includes Gaia and its photometry does not measure Gaia-window contamination. | Source-attributed multi-epoch RVs and line profiles, with resolved imaging or aperture/flux checks. |
| 2852726284550996352 | U. No independent RV epoch recovered; Gaia combined-CCF mean is not an epoch series. A published catalogue lists a possible wide pair. | The 6.089″ association is a candidate wide companion, not a confirmed triple; a class-0 XP fit does not exclude inner luminous light. | Measure both resolved sources and obtain component-sensitive RV epochs for the target. |
| 3316050687674598656 | U. No independent RV recovered; published XP class-1 label accompanies a worse two-star chi-square. | Most XP BP/RP transits are blend-flagged; the label and fitted components are not a confirmed binary. | Decontaminated multi-epoch spectra and line-profile checks before interpreting the Gaia orbit or XP model. |
| 4299244434901041024 | U. No independent RV epoch recovered; Gaia combined-CCF mean is not an epoch series. | Gaia period 31.501 d lies in a published scan-angle feature; a 3.893″, ΔG 6.29 neighbor exists. | Calibrated RV variability and phase coverage independent of Gaia; examine scan and contaminating-light alternatives. |
| 5591318172608607232 | U. No independent RV recovered; XP class-0 is a model label only. | A resolved Gaia neighbor 11.26″ away has very different astrometry; unresolved companions remain possible. | Stop the completed archive paths; obtain component-sensitive RV epochs. |
| 5928370816455687808 | U. No independent RV recovered. | Neighbor 1.329″ away; Gaia period 31.587 d lies in the published scan-angle feature; many XP transits are blend-flagged. | Source-attributed RVs and resolved-light constraints independent of Gaia astrometry. |
| 5929746958324419200 | U. No independent RV recovered. | Neighbor 1.959″ away; some XP transits are blend-flagged. The attempted DECaPS catalogue/image controls did not validate that route. | Source-attributed repeated spectra and resolved imaging; do not treat the failed DECaPS control as a non-detection. |
| 5959603097090964992 | U. No independent RV recovered; published XP class-1 is a model label. | Gaia solar-like variability label and possible composite light are alternatives to an orbital interpretation. | Multi-epoch RVs and component-sensitive spectra; compare variability and line profiles. |
| 5991734159714775296 | U. No independent RV recovered. | Gaia neighbor 0.981″ away, shared 2MASS association, and all returned XP BP/RP spectral transits blend-flagged. | Resolved or demonstrably deblended spectroscopy at multiple epochs; an unresolved catalogue match is insufficient. |
| 632497706010874240 | U. No independent RV recovered. | Gaia period 31.387 d lies in the published scan-angle feature; the wide-pair assessment is incomplete. | Calibrated RV variability over independent phases; stop repeating the completed DESI product paths. |
| 4491401821468887552 | P: [Li et al. 2026](https://arxiv.org/html/2610.34715v1). One LAMOST 2018 LASP RV, −5.31 ± 4.36 km/s, is recovered. | Fibre has NEARWHOPPER warning; independence from the paper's effective RV epoch is unknown; 31.309 d alias concern. | Additional calibrated RVs and fibre/line-profile quality review. This is a literature-recovery control, never a discovery. |
| 824344003814438528 | P: [Li et al. 2026](https://arxiv.org/html/2610.34715v1), one effective RV epoch in that study. | 31.499 d scan-angle concern; Gaia variability label is not an orbital test. | Additional calibrated RV epochs and line-profile checks. This is a literature-recovery control, never a discovery. |

The printed target tables examined in [Simon et al. 2026](https://arxiv.org/html/2603.20371v2)
and [Liu et al. 2026](https://arxiv.org/html/2609.39925v1), and the printed
tables of [El-Badry et al. 2026](https://arxiv.org/abs/2608.06453), did not
contain these 14 exact IDs; those are finite table checks, not a complete
literature search. The full Li 2026 supplementary list was unavailable.
The exact-ID web search was stopped when its known-published positive control
failed, so it says nothing about the other twelve. The [XP model study](https://arxiv.org/html/2507.09622)
and [scan-angle analysis](https://arxiv.org/html/2212.11971) motivate the
model and alias cautions. Their presence does not prove or disprove any
individual compact object.

All 14 later fixed-position ESO Gaia-ESO DR5.1 cones returned explicit zero
rows under the recorded predicates; that targeted survey result cannot rule
out other observations or establish novelty. [ESO provenance](../ges-eso-held14-cones-20261102T0550Z-01a193cc/SOURCE_PROVENANCE.json),
[previous source queue](../../../followups/held14-20261031T214650Z/FINAL_REVIEW_QUEUE.md),
[archive identification report](../../../followups/held14-20261031T214650Z/evidence/identifications/IDENTIFICATION_REPORT.md),
[recovered redshift](REDShift_REVIEW.md), and [PS1 identification review](PS1_IDENTITY_REVIEW.md) give the underlying evidence.
