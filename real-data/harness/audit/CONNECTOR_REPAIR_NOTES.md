# Connector repair proposal

Modified only `harness2/universe/connectors/public_archives.py` and `tests/test_connectors.py`; this note is an audit artifact. No scientific filter, covariance layout, parameter ordering, known-object list, release policy, endpoint allowlist, guard manifest, or holdout evaluator changed. No reseal performed.

## Resulting behavior

- HTTP response bytes are saved before VOTable interpretation. HTTP error bodies and network errors have immutable per-attempt query/status/time metadata. Capped or incomplete bodies are explicitly marked and cannot become valid cache entries.
- Each retrieval event receives a unique immutable JSON record under `cache/attempts`. Content-addressed bodies are not overwritten. The first successful `request-key.content-hash.json` metadata remains unchanged; the latest request-key index remains an explicit pointer to the newest successful retrieval. Existing offline content-hash checks still apply.
- TAP errors, overflow, malformed XML, duplicate composite identities and ignored row limits fail closed while retaining raw evidence. Failed acquisitions never fall back to old bytes.
- Acquisition configuration version 2 includes `max_pages`. Resume with a changed cap or older unbound version fails. An interrupted same-config run can resume, including an interruption before its first page. Multiple solutions for a source remain separate.
- Valid server `Retry-After` values above the 30-second per-retry wait budget defer visibly without an early retry; seconds and HTTP-date formats are supported.

## Verification

Executed from `proposed-integration` on native Windows with the parent isolated environment:

```powershell
..\.venv-astra\Scripts\python.exe -m unittest discover -s tests -p test_connectors.py -v
```

18 connector tests passed in 0.375 seconds on 2026-10-31. New regressions cover failure-body provenance, HTTP and network attempts, identical response retrieval history, capped/truncated bodies, long Retry-After, changed resume caps, interrupted same-cap acquisition, and interruption before page one. All response fixtures are synthetic protocol fixtures, not scientific observations. Live execution is owned by the parent session.

## Limits

Caches remain session-private; these changes do not introduce a shared-cache lock. Partial bytes received inside a failing socket call may not be exposed by Python; saved partial bytes and error state are reported without claiming a complete response. Version-1 acquisition manifests are deliberately not silently migrated because they did not bind the original page cap.
