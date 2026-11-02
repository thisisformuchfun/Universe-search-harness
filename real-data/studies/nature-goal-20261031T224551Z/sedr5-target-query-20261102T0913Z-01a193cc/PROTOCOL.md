# SEDR5 existing-fibre query after an offline control correction

Prepared 2026-11-02 UTC for independent preflight. The previous unique run
sent one control request and stopped before the target because its strict
parser expected the unprefixed headers of the official sample. The actual
HTTP-200 control CSV instead uses the exact same 29 field names in the same
order, each prefixed `sexprv_`. Its raw bytes and original failed run remain
immutable. An offline parser may accept only the exact unprefixed sample header
or the exact fully prefixed live header; mixed, reordered, duplicate, missing or
extra fields stop visibly. No values are imputed or interpreted.

Hypothesis: using the corrected wire-format parser, a single separately
bounded target POST may reveal catalogue records for the previously retrieved
fibre observation of held Gaia DR3 `1533365584518328576`. The target request
must not begin unless the saved control's exact request/body/response hashes,
HTTP/TLS/redirect/cleanup metadata and corrected-parser positive tuple pass.
The control matched one known sample tuple and all returned filenames; it does
not establish service completeness or target source attribution. This is a
new run with one target request, not a resume or rewrite of the stopped run.

The fixed public endpoint, filename predicate, 29-column projection and
multipart body are identical to the previous run's planned target body.
Perform at most one HTTPS POST to
`https://nadc.china-vo.org/data/data/general/sedr5/sexprv/build.csvs`, no
redirects, credentials, sent cookies or retry. The previous response contained
cookie fields; their values and all native headers remain local and are never
included in a portable archive or log. Limit the response body to 524,288
bytes and curl transfer to 45 s; use a 55 s batch deadline and a separate
exclusive acquisition lease. Preserve exact request/body/response and hashes.
Headers and diagnostics have monitored limits with 20 ms polling and possible
overshoot. No shared cache or GPU. Stop on a failed prerequisite, transport,
parser, cap, lock or cleanup check.

Record raw response and identity strings only. Matching filename strings do
not validate observation identity or Gaia association; an empty, foreign,
truncated or ambiguous response does not prove absence. Provider limits and
completeness are unknown. No RV interpretation, fitting, ranking, scientific
criteria, release decision or holdout evaluation is part of this protocol.
