# Scientific scope, exclusions and limitations

We derive an observed photocentre semimajor axis from the four Thiele-Innes coefficients, then `f_phot=(a0/parallax)^3/(period/365.25)^2`. Units are solar masses, but **this is not a companion mass**, black-hole probability, calibrated significance or an unconditional mass lower bound. With secondary light it is `(M1+M2)|M2/(M1+M2)-F2/(F1+F2)|^3`; assuming a dark secondary would need independent justification.

A value above 3 is an exploratory review threshold only. Astrometric orbit failures, photocentre/light assumptions, blends and multiple systems can mimic large values. OrbitalAlternative/Targeted solutions are explicitly held. The snapshot contains no full covariance, so uncertainty is unavailable, not independent-error fake precision.

For full Orbital bit_index8191 or AstroSpectroSB1 bit_index65535, the implementation reconstructs the documented upper-triangle column-major correlations, validates finite errors/correlation bounds/positive-semidefinite covariance, and propagates joint Gaussian catalog errors. Reduced bitmasks, alternative solution layouts, unknown/padded correlation formats are unavailable rather than guessed. Only exactly66/105 active correlation entries are currently accepted; the official schema's nominal231 storage may require a documented parser extension after retrieving actual live rows. Quantiles are conditional Gaussian propagation, **not a posterior or independent orbital validation**. Invalid physical/nonfinite draws are reported, never silently clipped to valid periods/parallaxes.

Published Gaia astrometric significance has a pre-correction covariance caveat. The pipeline does not reinterpret it as a calibrated FAP or apply covariance rescaling twice.

Known Gaia BH1/BH2/BH3 and one refuted claim have explicit source-linked exclusions; two additional published candidate catalogs conservatively exclude already studied objects. These lists are **not complete literature coverage**. No SIMBAD/catalog match is never evidence of novelty. Release is disabled: new anomalies remain HOLD_QUALITY_AND_NOVELTY until independent orbit/covariance/light/blend/triple checks and a current documented literature review support a reviewed scientific protocol. The loop cannot switch release on.

## Primary sources / data attribution
- Gaia DR3 NSS schema and parameter layouts: https://gea.esac.esa.int/archive/documentation/GDR3/Gaia_archive/chap_datamodel/sec_dm_non--single_stars_tables/ssec_dm_nss_two_body_orbit.html
- NSS caveats: https://gea.esac.esa.int/archive/documentation/GDR3/Data_analysis/chap_cu4nss/sec_cu4nss_combined/sec_cu4nss_combined_caveat.html
- Gaia archive: https://gea.esac.esa.int/archive/ ; Gaia credit guidance: https://www.cosmos.esa.int/web/gaia/credits
- Shahaf et al. catalog: https://vizier.cds.unistra.fr/viz-bin/VizieR?-source=J/MNRAS/518/2991/table2
- Jayasinghe et al. catalog: https://vizier.cds.unistra.fr/viz-bin/VizieR?-source=J/MNRAS/521/5927/table
- Gaia BH3 discovery: https://www.eso.org/public/archives/releases/sciencepapers/eso2408/eso2408a-panuzzo-et-al.pdf
- CDS SIMBAD: https://simbad.cds.unistra.fr/simbad/

Included small catalog snapshots preserve original provenance and literature references. Gaia/ESA/DPAC and CDS/catalog author attribution applies to their data; the repository software LICENSE does not relicense upstream data. Cite the original catalogs in research publications. The package makes no rights claim over upstream services or papers.
