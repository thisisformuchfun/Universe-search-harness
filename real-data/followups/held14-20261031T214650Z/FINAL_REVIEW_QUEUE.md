# Final review queue: all fourteen held objects

Two are already published compact-binary candidates. Twelve retain unresolved novelty. No independent orbital confirmation or new black-hole discovery was obtained. Production dispositions are unchanged.

| Gaia DR3 source | Period (days) | Published XP result | Source-specific finding / next decisive evidence |
|---|---:|---|---|
| 5991734159714775296 | 15.739 | Outside published selection; no inference | Neighbor at 0.981 arcsec; shared 2MASS counterpart. No independent RV orbit. Deblending and RV epochs are needed. |
| 3316050687674598656 | 6.287 | Class 1; chi-square gain -2.08 | Published XP binary label, but the single-star fit has lower chi-square. Check component/stellar assumptions and independent RVs. |
| 5928370816455687808 | 31.587 | Outside published selection; no inference | Neighbor at 1.329 arcsec and 31.587-day alias concern. Test contamination and obtain an independent RV orbit. |
| 632497706010874240 | 31.387 | Outside published selection; no inference | 31.387-day alias concern; wide-component check incomplete. Independent RVs and association tests are needed. |
| 1533365584518328576 | 15.692 | Class 1; chi-square gain +2.87 | One low-SNR LAMOST spectrum; published XP binary label with modest fit improvement. Obtain better repeated spectra. |
| 1538284425878995712 | 14.471 | Class 0; chi-square gain +0.40 | No independent RV orbit or strong composite-spectrum evidence. A sub-resolution luminous companion remains possible. |
| 4491401821468887552 | 31.309 | Class 0; chi-square gain -8.97 | Already a published compact-binary candidate. One retrieved RV has a fibre-quality warning; additional independent epochs are needed. |
| 5959603097090964992 | 25.227 | Class 1; chi-square gain +9.30 | Published XP binary label and Gaia solar-like variability label. Modest two-star fit improvement; test spectral multiplicity and RV period. |
| 824344003814438528 | 31.499 | Class 0; chi-square gain +2.94 | Already a published compact-binary candidate, with one effective RV epoch and a 31.499-day alias concern. No independent orbit confirmed. |
| 5929746958324419200 | 53.999 | Outside published selection; no inference | Neighbor at 1.959 arcsec. No independent RV orbit; inspect blending and obtain repeated spectra. |
| 2852726284550996352 | 19.896 | Class 0; chi-square gain -6.43 | Similarly bright neighbor at 6.089 arcsec is a possible wide-component lead. Gaia combined-CCF mean is not an orbital amplitude; test both components. |
| 5591318172608607232 | 24.946 | Class 0; chi-square gain +1.43 | No independent RV orbit; small XP two-star fit gain does not establish a companion. Repeated spectra are needed. |
| 4299244434901041024 | 31.501 | Outside published selection; no inference | 31.501-day alias concern and Gaia combined-CCF mean only. Independent RV and image/scan checks are needed. |
| 2245423750054837888 | 91.099 | Outside published selection; no inference | 91.099-day orbit remains unvalidated. A 5.465-arcsec neighbor has different astrometry; independent RVs and flux constraints are needed. |

XP values are **published stellar-model fits**, not new observations, dynamical masses or probabilities. Class 1 is the paper's binary label, not a confirmed binary; class 0 does not prove a single star. A positive gain means the reported two-star chi-square is lower. Three fits have negative gains. All eight fail one of the paper's stricter golden-sample conditions, `log10(chi2_single/chi2_binary) > 0.2`; this comparison is not a new harness cut.

For source 3316050687674598656, the binary label coexists with a worse two-star chi-square. Independent byte, identity, null-bit and datatype checks verified that this combination exists in the served catalogue. Its parameter-dependent classification needs clarification; this is not a demonstrated catalogue error.

Five parent-catalogue nonmatches fail its Gaia-source parallax >1 mas cut. Source 632497706010874240 fails parallax signal-to-noise >10. These selection exclusions do not test for luminous companions. Selection absolute magnitudes are computed without extinction correction.

The possible wide component around 2852726284550996352 is not a confirmed bound companion or triple. Resolved neighbors cannot establish the cause of a photocentre signal, and missing neighbors cannot exclude unresolved structure.

Primary sources: [Li2026 prior candidates](https://arxiv.org/html/2610.34715v1), [Li2025 XP models and classification](https://arxiv.org/html/2507.09622), [Holl scan-angle aliases](https://arxiv.org/html/2212.11971), [Müller-Horn luminous/triple alternatives](https://arxiv.org/html/2510.05982v2).

Full values and provenance: [final machine-readable findings](FINAL_HELD_OBJECTS.json), [run report](RUN_REPORT.md), [archive spectra](evidence/identifications/IDENTIFICATION_REPORT.md), [XP lookup](research/XP_PARENT_LOOKUP_RESULT.md), [independent matched-field verification](research/execution_review/XP_MATCHED_FIELDS_RESULT_REVIEW.json).

Conditional nominal dark-companion RV amplitudes and formal covariance results are retained in the machine-readable findings. They assume a real Gaia photocentre orbit and negligible secondary light; they do not lift any orbit, quality or novelty hold.
