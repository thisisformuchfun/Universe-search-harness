# Zhou and Gu Table 2: bounded transport only

Hypothesis: the explicit machine-readable Table 2 link in the independently
inspected, saved publisher page returns the complete 17-row Type II/III
candidate table. The page itself exposed four Gaia-ID preview cells; the
remaining 13 table members have not been compared with the original 14.

One GET, no redirects or retries, to the publisher-linked public HTTPS URL
`https://content.cld.iop.org/journals/0004-637X/1010/2/216/revision1/apjaeaa3at2_mrt.txt`.
The saved article and inspection hashes are pinned. No cookies, credentials,
uploads, model, GPU or holdout use. The reviewed transport limits curl to at
most 45 seconds, owned process to 48 seconds, body to 2,000,000 bytes, headers
to 65,536 bytes, stdout to 4,096 bytes and stderr to 262,144 bytes; polling
overshoot is possible and any overage terminates the request. Proxy, CA and
`SSLKEYLOGFILE` environment overrides cause an early stop. The local curl
executable hash and version are pinned.

The response is stored as inert, unparsed data with request, UTC, TLS/status,
process lifecycle and hashes. Native headers/diagnostics remain local. HTTP
success does not establish article/table identity, expected schema, version,
17-row completeness or presence of all four preview IDs. A separately
reviewed offline comparison must establish all these conditions and use exact
integer strings. A match indicates prior publication; even a valid nonmatch
does not establish novelty or a black hole. Any denial, redirect, failure or
unexpected content is terminal; no access restriction is bypassed. No source
disposition, scientific criteria or holdout changes here.

`STOP_UNPARSED_CONTENT` exits 1 even for successful HTTP/TLS transport; this
is the deliberate stop before parsing. If either owned process exit is
unconfirmed or result evidence is missing, retain the claim and follow the
recorded recovery instructions.
