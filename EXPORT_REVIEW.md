# Export review — 2026-11-02

This is an additive, reviewable update for `thisisformuchfun/Universe-search-harness`, based on public main commit `69c2986a84c5cf22180a08fd370b2082a937b32e`. The existing repository `a.zip` is deliberately not part of this overlay and should remain unchanged. The initial export was assembled locally before publication.

## Contents

- `real-data/`: the complete 500-member narrow continuation packet, extracted byte-for-byte from archive SHA-256 `18d501a92ba469a5cb180a6d3cda98d5dc20c902416a83d2d6b88f6110c1c09f`. Its original manifest retains every file hash. The bundled approved harness's guard is `558cef0d2d1cab72110c03e2089009ef8cdaf031c63247f8e345bfbbbb81953c`.
- `public-review/`: the later dated literature results, captured source evidence, attribution and an offline exact-ID verifier.
- `dashboard/`: the dashboard-specific 3D explorer and a small independent React/Vite shell. It is static and intentionally contains no local chat feed or monitor; the Data plugin runtime and the original app's product-owned shell are not included. The repository README uses screenshots of the portable explorer.
- `EXPORT_MANIFEST.json`: hashes for this complete additive export; verify with `python -B verify_export.py`.

## Checks performed on this export

- Continuation manifest: 499 files plus the manifest itself verified, with no extras in the extracted packet at the time of verification; original baseline hash verified.
- Approved harness installed in a fresh Python 3.11 virtual environment. Guard verification passed; the unittest suite reported 37 tests, 36 passed and one native-symlink capability test skipped because Windows denied creation. The guard rejection branch was tested separately by the suite.
- A fresh CPU run of the bundled historical snapshot reproduced 500 records, 17 anomalies, 14 held, two known-black-hole exclusions, one refuted exclusion and zero releases. No scientific holdout was evaluated and no policy or guard was resealed.
- The later public-review verifier reproduced 14 identities, two published compact-candidate controls, eight XP parent rows, one wide-pair record, two LAMOST spectra and 14 Gaia/2MASS matches; two verifier safety tests passed.
- The portable dashboard built successfully; its 3D selection, source references and published-source filter were checked in a browser.
- A bounded pattern scan of text-like export members found no matching personal-profile path, bearer credential, GitHub token, OpenAI key, private-key marker or cookie header. It did not inspect large binary files or archives and cannot prove absence of sensitive content. Historical capture/request files include absolute workspace paths.

## Important omissions and review points

This is not a complete history dump. Two large older nested handoffs were omitted from the narrow continuation and are recorded by name and SHA-256 in `real-data/HISTORICAL_ARCHIVE_OMISSIONS.json`; the full prior handoff is a separate local archive. Native HTTP headers and some request diagnostics remain local. The complete 9.86 GB XP dataset is not bundled, and its full-file checksum was not verified. The Li 2026 complete candidate table was unavailable. The general web index failed known-positive controls. None of the other 12 objects is cleared as novel, and none of the 14 is a newly confirmed black hole.

Article sources, survey responses, FITS products and catalogues are third-party material. The software license does not relicense those assets. Review each provider's attribution and redistribution terms and inspect captured request records before making this packet public. SHA-256 manifests detect byte changes; they are not a guarantee of ownership, a security sandbox or evidence of a discovery.
