# Published XP fits for the held queue

Eight held sources have exact rows in the [Li et al. XP parent catalogue](https://zenodo.org/records/15166185). Their 28 published scientific fields, validity byte, and repeated exact source ID were retrieved in eight requests totaling 38,928 response bytes. All 240 byte ranges were validated and independently re-decoded. No new model was fitted. The remaining six sources are outside the [published parent selection](https://arxiv.org/html/2507.09622v1#S2.SS2), so their catalogue absence says nothing about companion luminosity.

| Gaia DR3 source ID | Raw published class | Single-model χ² | Binary-model χ² | Published Δχ² | Binary-model M1 / M2, solar units | Published XP mean flux ratio |
|---|---:|---:|---:|---:|---:|---:|
| 3316050687674598656 | 1 | 79.998 | 82.078 | −2.081 | 0.847 / 0.820 | 0.838 |
| 1533365584518328576 | 1 | 38.606 | 35.737 | 2.869 | 0.615 / 0.338 | 0.114 |
| 1538284425878995712 | 0 | 56.532 | 56.134 | 0.398 | 0.705 / 0.115 | 0.00210 |
| 5959603097090964992 | 1 | 76.028 | 66.729 | 9.299 | 0.583 / 0.478 | 0.361 |
| 4491401821468887552 | 0 | 45.228 | 54.198 | −8.970 | 0.603 / 0.540 | 0.532 |
| 824344003814438528 | 0 | 81.538 | 78.602 | 2.936 | 0.771 / 0.239 | 0.00969 |
| 5591318172608607232 | 0 | 130.366 | 128.937 | 1.429 | 0.454 / 0.169 | 0.0569 |
| 2852726284550996352 | 0 | 65.768 | 72.197 | −6.429 | 0.835 / 0.674 | 0.330 |

Masses in this table are conditional photometric-model outputs, not dynamical masses or measurements establishing companions. Full published uncertainties, convergence flags, model parameters, input parallaxes, and transport provenance are retained in `XP_PUBLISHED_FITS_EVIDENCE.json`. The XP flux-ratio summary is not assumed to be the astrometric G-band light ratio, and its reported dispersion is not assumed to be a posterior uncertainty. The catalogue provides no separate uncertainty field for M2.

[Table 2 of the primary paper](https://arxiv.org/html/2507.09622v1#S5.T2) explicitly maps class 1 to the authors' binary classification passing a parameter-dependent χ² threshold. Class 0 is retained here as a raw label; it does not establish a single star or rule out a companion. Neither label is a calibrated binary probability or BH probability. For 3316050687674598656, class 1 coexists with a binary fit that has larger χ². Independent byte, identity, dtype, and validity checks confirm the served values. This is an apparent label/fit tension requiring clarification of the published threshold/model procedure, not a demonstrated catalogue error.

All eight have log10(χ²single/χ²binary) below 0.057, so none meets the paper's necessary 0.2 condition for its stricter sample. This is a description of the external study, not a new harness rejection criterion. Three binary fits are worse in χ²; the other five improve it modestly. Consequently, this evidence resolves the previous *unavailable photometric-fit* gap for eight objects but does not validate a luminous companion, a dark companion, or the NSS orbit. The reported low-flux solutions for some rows cannot exclude fainter stars, unresolved multiples, or model failures.

The published parent selection explains all fourteen membership outcomes. Five excluded sources have Gaia source parallax at most 1 mas; 632497706010874240 fails the study's parallax S/N requirement. `XP_PARENT_SELECTION_COVERAGE.json` contains the exact checks. Its field name `derived_unreddened_absolute_G` is a naming error: the calculated absolute G magnitude has **no extinction correction**. The values and selection comparisons are unchanged; the new evidence sidecar uses `absolute_G_without_extinction_correction`.

The new information supports targeted independent tests, such as multi-epoch RVs at the claimed orbital period, spectra sensitive to a second luminous component, and imaging for unresolved structure. It does not remove the existing orbit or novelty holds. Sources 4491401821468887552 and 824344003814438528 were already present in a [published compact-candidate study](https://arxiv.org/html/2610.34715v1); the other twelve still lack complete prior-study coverage. No new discovery is released.

The successful executed caller remains unchanged and hash-recorded. Its separately versioned v2 wrapper fixes nonzero exit status for failed/missing/malformed results and uses fresh output directories; four process-level regression tests and an independent review passed. The observed malformed multipart MIME exception is restricted to this diagnostic endpoint and was independently reviewed with nine parser tests. Full HDF5 MD5 verification remains unavailable; the complete ID-column hash, exact ranges, unchanged fixed-record metadata, and repeated IDs are retained instead.
