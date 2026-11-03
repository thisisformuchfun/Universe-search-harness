# Universe-search-harness audit and real-data pilot

Inspected commit: 69c2986a84c5cf22180a08fd370b2082a937b32e
Archive Git blob: d722d07ef436cdce27b53fedf284fa4838bbeb6b
Archive SHA-256: b10d953310f2c6c618bab46a3d60e3cee91344fa977575ac965abe62178d73fd
39 entries; 17,037,017 archive bytes; 18,012,410 uncompressed bytes. No traversal or symlinks; no AGENTS.md. Original repository code has not been executed.

## Findings
- Main CLI always calls load_calibrated_benchmark_stream(seed=42). All four signals are synthetic, generated with known injected parameters. Live connectors are not wired into the sweep.
- The dormant-BH detection flag requires period within 3 days of hard-coded 186 days. The GW detection flag requires epoch within 0.06 seconds of injected 2.95 seconds. Other domains similarly use injected answers.
- Claimed physical masses are copied from injected_or_hidden_truth, not inferred from measured observations.
- FAP is an arbitrary exponential of SNR; no noise-calibrated trials correction. Some SNRs receive fixed multiplicative boosts. FAP is not actually required by detection flags.
- mode is logged but does not alter the recursion loop. Stored lessons affect a text field, not detector execution or provider prompts. Lessons are stored without detection/FAP gates.
- PDF advertises harness2/cli/blackholes.py and a six-object output catalog, both absent from the archive. It discusses known targets including Gaia BH1/BH2/BH3, not undiscovered objects.
- No novelty crossmatching, no external validation, no archival observation identifiers/checksums, no physical mass-fitting pipeline.
- No eval/exec, subprocess, pickle, shell execution, or arbitrary self-modifying code found. JSON values choose existing detector modes. Deterministic path needs only installed numpy/scipy, no GPU or API. Remote provider mode sends prompts to configured endpoints and silently falls back on errors, so default provider labels do not prove use of a model.
- Upstream Harness² exists at https://github.com/google-research/harness2 and https://arxiv.org/abs/2610.14224 . Its recursive-harness approach is genuine, but does not validate this astronomy adaptation or its advertised results.

## Independent pilot
The adjacent gaia_pilot.py is newly authored, read-only public-archive analysis. It does not import or execute repository code. Gaia DR3 NSS schema was retrieved from official TAP; the script retrieves NSS orbital solutions (an initial source-level metadata join timed out, so crowding validation remains incomplete), selects a bounded proxy-ranked sample, and computes photocentre-orbit anomaly scores.

For Thiele-Innes A,B,F,G, let u=(A²+B²+F²+G²)/2 and v=AG−BF. Then a0²=u+sqrt(u²−v²). The observable f_phot=(a0/parallax)³/(P/yr)² is expressed in solar-mass units. It is NOT a companion mass or an unconditional lower bound.

In a binary, f_phot=(M1+M2)|M2/(M1+M2)−F2/(F1+F2)|³. Only under the dark-secondary assumption does this reduce to M2³/(M1+M2)². A large point estimate neither demonstrates darkness nor establishes a reliable lower mass bound.

All selected rows are HELD anomalies. No row may be delivered as an undiscovered BH candidate until joint covariance/uncertainty, orbit quality, luminosity/blend/triple alternatives and literature/catalog novelty are reviewed. Published significance itself requires ESA post-rescaling caveat checks. Epoch data or follow-up RVs may be needed.

Prior-study exclusions to implement before any release: Shahaf compact-companion table J/MNRAS/518/2991/table2 (177 objects); SB1 high-mass-function J/MNRAS/521/5927/table (234); Gaia collaboration candidate sample; Müller-Horn catalogs DOI 10.5281/zenodo.17271785; relevant follow-up literature, SIMBAD and ADS. These lists alone are not exhaustive. Excluding whole compact-companion lists over-excludes some non-BH objects and must be disclosed.

Sources: https://www.cosmos.esa.int/web/gaia/dr3-nss-tools ; https://gea.esac.esa.int/archive/documentation/GDR3/Data_analysis/chap_cu4nss/sec_cu4nss_combined/sec_cu4nss_combined_caveat.html ; https://arxiv.org/abs/2209.00828 ; https://academic.oup.com/mnras/article/521/4/5927/7085748 ; https://arxiv.org/abs/2510.05982 .
