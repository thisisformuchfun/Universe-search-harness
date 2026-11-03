# DR3 review packet, October to November 2026 (frozen)

This is the evidence packet from the first review of the 14 held Gaia DR3 sources. It is kept for provenance and is not maintained.

- `START_HERE.md` and `RUN_REPORT.md`: handoff and findings
- `studies/`: dated follow-up studies (LAMOST, SDSS/NOIRLab, Legacy Survey masks, HST, SEDR5)
- `public-review/`: per-source literature checks, captured evidence and an offline verifier (`python -B public-review/verify_public_review.py`)
- `followups/`, `review/`, `evidence/`: earlier follow-up outputs and independent reviews

## Changes since the original export

In November 2026 the repository was restructured. The live harness moved to `/harness`. These files were removed from the tree and remain in git history at commit `ff3fa48`:

- `a.zip` (original first-commit archive, 17 MB) and `baseline/original-v1.zip`
- `RUN_REPORT.before_checkpoint55/56/57.md`, `RUN_REPORT.checkpoint60.md`, `START_HERE.checkpoint60.md`, `PORTABLE_MANIFEST.checkpoint60.json`
- `artifacts/Universe_Search_Harness_Checkpoint53_*.zip.manifest.json`
- `harness/runs/astra-approved-baseline-20261031T2133Z/`

Because of those removals and the move, `PORTABLE_MANIFEST.json`, `EXPORT_MANIFEST.json` and `verify_export.py` describe the original layout and will report the changes. To verify the original export, check out `ff3fa48`. Relative links in historical reports that point to `harness/` or to the removed ZIPs no longer resolve. The harness they describe is at `/harness`, with later changes.

Scripts here keep their original Windows paths and are not portable replay commands.
