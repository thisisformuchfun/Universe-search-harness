# Independent execution/security review — local session

Date: 2026-10-31. Reviewer: execution_review agent, separate from implementation.
Reviewed baseline: `C:\gogogo\universe search harness\universe-real-harness`.
Working session: `astra-20261031T2113Z-01a193cc`.

## Scope and status

Read the CLI, public archive connector, guards, ranking engine, memory, local-model router, scientific regression tests, security/connector tests, packaging and resealing scripts. Source inspection was read-only. Two narrowly scoped reproductions used explicitly fabricated protocol response bytes in temporary directories; these were not observations or candidate results. No real holdout evaluation, network request, GPU allocation, production mutation, or resealing was performed by this reviewer.

The parent reports that native verification passes, 27 of 28 baseline tests pass (the remaining test cannot create a Windows symlink, WinError 1314), and the CPU snapshot reproduces 500 records, 17 anomalies, 14 holds, two known BH exclusions, one refuted exclusion, and zero released candidates. The parent also reports that the original ZIP matches the supplied hash and extracted files match it. These are parent-executed results, not independent executions by this reviewer.

The initial baseline findings below are retained as an audit trail. The proposed integration was subsequently reviewed as recorded at the end of this document. The protected production baseline must remain sealed and unchanged until deliberate maintainer review and approval.

## Findings

1. **P1: Failed archive responses lose diagnostic evidence.** In baseline `harness2/universe/connectors/public_archives.py`, `tap()` parses at line 281 before saving raw bytes. `_request()` also drops HTTP error response bodies and headers. Independent reproduction: a fabricated HTTP 200 response with TAP `QUERY_STATUS=ERROR` raised `ArchiveError` and left **zero evidence files**. Preserve bounded response bytes, exact query, endpoint, status, retrieval time, and hash before interpretation, including ERROR/OVERFLOW/malformed bodies and HTTP errors. Record timeout/no-response attempts explicitly without inventing response bytes.

2. **P1: Resume changes acquisition bounds.** Baseline line 324 excludes `max_pages` from the acquisition configuration. Its existing connector regression explicitly resumes with a larger cap. This contradicts the current README and user protocol. Include the bound in a versioned configuration; reject changed caps. Test actual interrupted resumption with the same cap, changed-cap rejection, and completed/bounded acquisition handling.

3. **P1: A regression spends the real snapshot holdout using disposable ledgers.** `tests/test_science.py:test_frozen_budget_and_overlap_gate` calls the production snapshot runner and evaluates its holdout under a newly created temporary ledger. The historical independent execution review already states that this snapshot was evaluated. Treat its holdout as historically consumed. Replace this regression's real-data inputs with explicitly fabricated protocol records/frozen outputs while retaining budget and overlap assertions. Do not modify the heldout evaluator, partitions, or ledger to obtain a new scientific holdout.

4. **P1: Packaging can overwrite the original ZIP and include session caches.** `scripts/package_release.py` hardcodes `Universe_Search_Harness_Real_Data_v1.zip` in the source parent and excludes only the exact `data/cache` directory. A differently named acquisition cache is included. Do not use this script unchanged for the final deliverable. Use a unique patched-package name and explicit inclusion allowlist with a separate diff/hash manifest; exclude environments, credentials, model weights, and unrelated files.

5. **P2: Local-model transport inherits proxy routing.** `harness2/providers/router.py` validates the URL as loopback but constructs a default urllib opener. With a configured proxy and absent bypass, prompt JSON can be routed through a remote proxy. Explicitly disable proxy handling for local model requests with `urllib.request.ProxyHandler({})`; retain redirect rejection. Test against a synthetic proxy configuration and fake transport. Do not inspect, log, or transmit actual proxy credentials.

6. **P2: Supposedly immutable retrieval metadata is overwritten.** Baseline connector line 291 replaces `key.digest.json` when the same query returns identical bytes again. Independent reproduction confirmed that a second identical response changes the existing metadata bytes (retrieval timestamp). Keep retrieval events separately immutable; content-addressed raw bytes can be shared within a session, but each retrieval must remain attributable.

7. **P2: Retry-After can be shortened.** `_request()` caps server-provided delays at 30 seconds, then retries even if a longer delay was required. If the delay exceeds the permitted local wait budget, fail/defer visibly instead of retrying early. Test numeric and HTTP-date forms and error-body preservation for rate-limit failures.

8. **P2: Concurrent ledger and cache mutations lack exclusion.** Atomic replacement prevents partial files but does not make read/check/write transactions exclusive. Two evaluations can pass the overlap check concurrently and overwrite ledger updates; shared cache temporary names can also collide. The user-required exclusive ownership/lock around shared mutation mitigates this operationally without changing heldout methodology. Never use a communication-only coordination file as the lock.

9. **P2: Native Windows symlink regression requires privileges.** The baseline test unconditionally calls `Path.symlink_to`. The parent reproduced WinError 1314. Preserve changed-content coverage independently; represent denied symlink creation as an explicit skipped capability test or use a narrow mocked path-property test plus a real capability test. Do not enable Developer Mode, elevate system policy, or weaken production guard checks merely to pass a test.

10. **P2: Run provenance does not explicitly bind the schema request.** The CLI calls `gaia_schema()` and discards its result. Cache storage may retain the raw schema response, but the run does not explicitly identify it. A future reviewed integration should bind the exact schema request/response hash and retrieval event into run provenance.

11. **P2: Future Windows resealing would produce nonportable manifest paths.** `scripts/seal_release.py` uses `str(p.relative_to(root))`; on Windows this serializes backslashes, which POSIX `Path` treats as literal filename characters. A future approved maintainer reseal should serialize `.as_posix()` keys and explicit UTF-8. The existing baseline was sealed with portable keys. This is not permission to reseal it during this session.

## Required review evidence for an integration

- An explicit diff against the hash-verified baseline, with scientific policy, detector, partitions, and heldout evaluator unchanged unless separately authorized.
- Regressions reproducing the actual failures above, including failure-evidence retention and immutable retrieval events.
- All baseline and new tests, with native capability skips reported honestly.
- Explicit verification that guarded production code still rejects unsealed modifications. Do not reseal to make tests pass; run isolated unit regressions and document any integration-only guard binding mechanism for review.
- A portable final package with unique name, input/output manifests, and no claim that its hash is the original ZIP hash.

## Decision

The baseline is a bounded real-data triage implementation with reproducible snapshot behavior, subject to the findings above. It is not evidence of fresh live acquisition, CUDA benchmarking, local model operation, or new black-hole discoveries.

## Proposed integration review — completed 2026-10-31 21:19 UTC

**Decision: accepted as a review-ready engineering patch, pending user/maintainer approval and deliberate resealing.** This is not production adoption or scientific release approval. No additional blocking defect was found in the reviewed changes. Hash-bound scope is recorded in `INDEPENDENT_EXECUTION_REVIEW_HASHES.json`; it contains baseline and proposed SHA256 values for all nine changed/new files.

Independently inspected the complete baseline-to-proposal diff for `harness2`, `tests`, and `scripts`, excluding generated bytecode. Confirmed byte-for-byte equality for scientific detector, ranking/partition module, scientific policies and guard manifest, and AST equality for the heldout evaluator. The CLI change binds schema provenance only. No release flag, scientific threshold, covariance order, source partition, novelty exclusion, or holdout methodology changed.

Independently executed from `proposed-integration` using the parent's isolated environment:

```powershell
..\.venv-astra\Scripts\python.exe -B -m unittest discover -s tests -v
```

Result: **37 tests run in 0.709 seconds; 36 passed, one explicitly skipped, zero failures/errors.** The sole skip is actual native Windows symlink creation denied with WinError 1314; the guard's symlink rejection branch is also exercised in a separate passing test. The heldout test now uses only synthetic protocol records and a temporary fixture guard. It does not evaluate actual astronomical sources.

Also independently executed the unsealed proposal's `python -B -m harness2.cli.universe verify`. It returned nonzero with `FAILED CLOSED: Protected scientific code changed: harness2/cli/universe.py`. This is the expected guard behavior, not a failure to conceal or repair by automatic resealing. The original guard manifest remains unchanged.

The reviewed proposal addresses findings 1–7 and 9–11: immutable response/attempt evidence before interpretation; fixed resume bounds; synthetic heldout regression; separately named allowlisted exclusive-create packaging; proxy-disabled loopback model transport; preserved first retrieval metadata; no early retry against a longer Retry-After; explicit Windows capability skip; schema binding; and portable future seal paths. The seal script was inspected but never executed.

Finding 8 remains an **operational constraint**: caches and ranking memory must remain session-private, and shared ledger/GPU mutation requires the user-specified exclusive lock and single owner. The patch does not claim to provide a shared-cache transaction lock or a tamper-proof guard. Failed socket calls can expose only partial or no response bytes; evidence marks that state rather than inventing data.

No fresh end-to-end live pipeline, actual covariance-array support, CUDA arithmetic, local-model proposal, or new candidate inference is certified by these unit tests. Those claims require their own recorded execution evidence. Approval of this engineering diff does not remove any scientific hold.

## Approved adoption verification — completed 2026-10-31 21:35 UTC

**Decision: approved engineering adoption independently verified.** The user approval record states “Approve this patch and reseal” for the exact nine-file reviewed engineering patch. Its recorded time, 21:31:12.738 UTC, precedes the successful deliberate maintainer seal at 21:31:28.697–28.791 UTC. Recorded verification, tests and snapshot execution follow in order and return exit code 0. Their stored stdout/stderr hashes were independently rechecked. The test log records 36 passes and the same single native-symlink capability skip. The sealed snapshot still gives 500 records, 17 anomalies, 14 holds, two known BH exclusions, one refuted exclusion, and zero released candidates.

All nine approved file hashes still exactly match the independent pre-adoption review; only the expected guard manifest changed. Its SHA256 is `558cef0d2d1cab72110c03e2089009ef8cdaf031c63247f8e345bfbbbb81953c`, all listed files match, and its paths use portable separators. Both preserved baseline source copies match the original baseline inventory. The original delivered ZIP still has SHA256 `c7bcf827bf4ddbdfec7fde5734594c879d18f21a0fb0d0562e17ba0c9ba950c1`.

The subsequent short primary-service probe failed for all three endpoints. Each exact query is linked to a preserved network-error attempt with no HTTP status/body invented. This verifies real failure logging; it does not certify those services as reachable. Detailed hash/chronology checks are recorded in `INDEPENDENT_ADOPTION_VERIFICATION.json`. This reviewer made no new production edits, ran no holdout evaluation, and performed no GPU work during adoption review.
