# Repair map / honest verification status

Original repository: thisisformuchfun/Universe-search-harness, commit69c2986a84c5cf22180a08fd370b2082a937b32e, source a.zip SHA256 b10d953310f2c6c618bab46a3d60e3cee91344fa977575ac965abe62178d73fd.
This is a source-tree repair/replacement of its harness2 architecture and production CLI, not an unchanged repository plus a detached screening notebook. Original source remains outside this deliverable; no GitHub push performed.

|Original defect|Repair|
|---|---|
|CLI loads seeded synthetic stream|CLI reads hashed real Gaia snapshot or explicit live TAP acquisition|
|Injected period/epoch detector checks|Actual Thiele-Innes photocentre observable; no injected targets|
|Mass copied from hidden truth|No truth fields or inferred companion mass in production|
|Arbitrary exponential FAP/SNR claims|Removed; observable and heuristic ranking labeled honestly|
|mode only logged|Different parent/adoption flow, parallel probes versus sequential updates|
|memory/lessons don't affect execution|Strict adopted weight configuration applied on next run|
|Unvalidated improvements persist|Validation-gated adoption, guarded code, grouped train/val/test and consumed-source ledger|
|No provenance/novelty|Exact IDs, raw hashes/query/time, catalogs, exclusions and fail-closed holds|
|Missing advertised blackhole files|Implemented connected NSS detector/uncertainty/novelty/CLI with tests|
|Misleading multi-domain discovery claims|Unsupported production domains explicit; no synthetic success|

## Status
- Verified locally: actual snapshot ingestion, end-to-end metrics, source IDs, bounded proposals, unchanged release gate, connector parser/cache/pagination fixture tests.
- Unit fixtures are synthetic protocol/numerical examples **only in tests**; never discovery outputs.
- Blocked here: live ESA times out and CDS returns503. Probes are retained. No fresh real-data end-to-end success claimed.
- Not performed: physical RTX4090 benchmark, local model inference, new scientific orbit validation or discovery confirmation.
- Security: JSON-only proposals cannot edit files through the engine. Hash checks + frozen outputs + ledger provide auditability. This is **not an OS sandbox** for an independently empowered local Codex. Use restricted filesystem/network permissions and human diff review for code changes.
- Science: real anomalies still require human scientific investigation. Returning zero released candidates is the correct outcome when evidence is insufficient, not an engine error to optimize away.
