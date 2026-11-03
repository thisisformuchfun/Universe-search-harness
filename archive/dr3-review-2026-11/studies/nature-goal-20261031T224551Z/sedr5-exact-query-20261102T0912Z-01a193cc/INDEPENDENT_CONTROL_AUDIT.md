# Independent control audit

The one control POST returned HTTP 200, TLS verification result 0, zero
redirects and curl return code 0. Its 1,359-byte body has SHA-256
`c87ea085110605f3ecd2023caa3ea321a4ad3c580a431df0f460ad2368f25759`.
No cap overages occurred; the started child exited and the lease was released.
The target request was never made. The run's result SHA-256 is
`b9e7ee624d2aa9b5c7a79759e722f6ce46508440ab4b48a761d37a7200ecd861`.

Both independent reviewers found a real wire-schema difference: the query
response has the same 29 ordered fields as the sample but prefixes each with
`sexprv_`. The old parser stopped rather than guess. All three response rows
have the expected control filename and their identity tuples agree with the
three matching sample rows; the frozen unique control tuple occurs once. No
RV values were interpreted, and this does not establish catalogue completeness.

**Privacy:** the native response headers contain two nonempty Set-Cookie fields,
including one potentially session-bearing cookie. Their names and values must
not be printed, logged, copied to an archive or sent elsewhere;
keep the entire native header local. A limited scan found no auth/token-named
fields or obvious credential-like diagnostic markers. Diagnostics remain local
pending full privacy review. No access restriction was bypassed.
