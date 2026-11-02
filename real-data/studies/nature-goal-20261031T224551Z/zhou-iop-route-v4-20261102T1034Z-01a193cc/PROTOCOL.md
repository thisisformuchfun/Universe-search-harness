# Publisher route: bounded transport only

Hypothesis: the publisher's public article page at the fixed URL below may
contain an explicit machine-readable table link for Zhou and Gu (2026),
https://doi.org/10.3847/1538-4357/aeaa3a. The saved arXiv version shows six
of the paper's 19 identifiers; 13 members of the 17-object Type II/III table
remain unexamined. A later exact-string comparison needs separate identity,
schema, row-count and four displayed-row positive controls.

One fixed GET to `https://iopscience.iop.org/article/10.3847/1538-4357/aeaa3a`.
Use the previously reviewed capture engine and native transport, no redirects,
retries, credentials, cookies, file uploads, model, GPU, or holdout use.
The transport limits curl to at most 45 seconds, the owned process to 48 seconds,
body to 2,000,000 bytes, headers to 65,536 bytes, stdout to 4,096 bytes and
stderr to 262,144 bytes. Polling may overshoot before process termination; any
overage is a terminal failure. Inherited proxy or TLS certificate override
environment variables, including `SSLKEYLOGFILE`, cause an early stop without
printing their values. The reviewed local curl executable's hash is pinned;
its recorded version is 8.22.0. The validator does not spawn a version check.

The sole response is saved as inert data with native headers, request command,
UTC times, transfer status, cleanup status, and hashes. Headers and curl
diagnostics stay local. Even valid HTTP/TLS transport is marked unparsed; a
separate, reviewed offline step must verify the article and an explicit table
link. No returned link is followed automatically. An HTTP denial, network
failure, redirect, oversized response, unexpected page or missing explicit
link ends this attempt; none is a catalogue nonmatch, novelty evidence, or
permission to bypass restrictions. A table retrieval requires its own bounded
protocol. No source disposition or scientific criterion changes here.

The capture result `STOP_UNPARSED_CONTENT` has process exit code 1 even after
successful HTTP/TLS transport; it is an intentional stop before content
validation. If process cleanup is unconfirmed, the acquisition lease and
coordination claim remain for manual recovery. A claim interrupted between
its pending record and committed record must never be cleared automatically.
