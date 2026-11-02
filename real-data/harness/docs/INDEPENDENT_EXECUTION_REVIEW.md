# Independent execution/security review — 2026-10-31

## Decision
Source approved as a **bounded real-data Gaia NSS triage repair**, not a validated black-hole discovery engine or repair of all four original production domains. Independently extracted ZIP passes all 28 tests, guard/data verification, a fresh production snapshot run and budget1 heldout evaluation. ZIP paths are safe and exclude venv, bytecode, git metadata and environment files. This uses the available Python environment; a clean network dependency install and native Windows run were not performed.

## Independently executed
- `python -m unittest discover -s tests -v`: 28 tests PASS, including six independent security test methods added in `tests/test_security.py`.
- `python -m harness2.cli.universe verify`: PASS; guard SHA256 `9d03ad1ef0d2421cd04c67237925c4afb4ed71266bb378719129fcd8c4d81439`.
- Full production snapshot CLI: 500 measured rows, 17 anomalies, 14 held, 2 known BH exclusions and 1 refuted exclusion, zero releasable candidates.
- Frozen review-budget regression reproduced before repair; fixed evaluation now uses the recorded budget. Cross-dataset overlapping test sources are rejected.
- Proposal validation rejects extra scientific-policy fields, nonfinite values, boolean/string weights, out-of-range and all-zero weights. Nonloopback/credential-bearing proposer URLs and remote providers rejected. Local timeout does not synthesize a fallback.
- Guard tampering/symlinks and incompatible/injected memory rejected.
- Existing connector tests exercise response schema/overflow/truncation, exact source IDs, cache tampering/version preservation, keyset resume and allowlists.

## Defects identified and repaired
- VizieR second catalog had wrong `GaiaDR3` column: uses `Source AS source_id` now.
- Heldout evaluator silently used default budget20 instead of requested budget: frozen budget persisted and reused.
- Zero/negative/excess review budgets rejected.
- Dataset hash now canonically sorts source/solution records.
- Holdout ledger blocks overlapping consumed test sources, not only exact dataset hashes.
- Snapshot manifest included in protected release manifest; manifest paths checked.
- Source-tree-only install limitation now explicit in README/AGENTS.

## Deliberate limitations / no claim beyond evidence
- Live archive GET/POST probes recorded ESA timeout and CDS503. No successful fresh end-to-end acquisition was observed. No synthetic or stale fallback is used in live mode.
- Included actual snapshot lacks full covariance. Correlation propagation tests use explicitly labeled unit fixtures; real served covariance-array format still requires local verification.
- RTX4090/CUDA and local LLM server not executed here. Optional GPU arithmetic is implemented, not benchmarked.
- Three bounded ranking weights optimize a quality heuristic, not scientific precision/recall or discovery yield. Test source isolation and a single persistent ledger are workflow requirements; filesystem owner can defeat them. Hashes are not an OS sandbox.
- Other original promised transit/GW/anomalous-star domains disabled explicitly rather than faked.
- Editable full source-tree installation supported, standalone wheel unsupported.
