# Independent post-capture reviews

Accepted 2026-11-02 UTC as an unresolved target response. The execution
reviewer verified exactly two fixed POSTs, the frozen bodies and control gate,
all source/test/native hashes and two distinct owned children with observed
creation identities and confirmed exits. Both returned HTTP 200, TLS verify 0,
no redirects and curl return code 0. No cap overages occurred; the lease is
absent. The target-request start followed the control-finish UTC timestamp by
1.009844 s; the shared monotonic deadline was recorded, but UTC timestamps
do not independently prove the monotonic gap.

The control returned 1,359 bytes, SHA-256
`c87ea085110605f3ecd2023caa3ea321a4ad3c580a431df0f460ad2368f25759`,
with the exact 29-field prefixed header and three records satisfying the
sample identity gate. The target returned zero bytes, SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
The strict parser's `ValueError` and `STOP_EXCEPTION` are correct. Results
SHA-256: `6f706b3eada66f80ce5645ca5b838fc1949f102e3fd09cca1b588e9b7d906a16`.

The science reviewer confirmed the identity-only control and recommends
stopping repeated same-route target queries: two distinct predicates have
returned uninformative empty bodies despite positive controls. Neither empty
body is an explicit zero-row CSV or proof of a nonmatch. Identical control
bytes may reflect caching. Service empty-result behavior, catalogue membership,
source attribution and any RV remain unknown. Both native response headers
contain potentially session-bearing cookies; retain them locally and never
print, reuse or package their names or values. Diagnostics remain local.
