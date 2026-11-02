# Independent capture audit

Root transcription of `/root/ps1_execution_review` on 2026-11-02 UTC. The
reviewer accepted the V9 capture for transport and prefix scope. All four
fixed requests, command and URL bindings, request/native/body/header/stream
hashes and lifecycle records matched. Each returned HTTP 200, TLS verification
0, zero redirects and the expected effective URL. The three indexes each
contained the required literal next link.

Body sizes were 92,063, 1,299, 312,833 and 550,080 bytes, for 956,275 bytes
total; recorded overages were zero. The product SHA256 was
`7a33d6a4ff8594c33b43181309bc5ad4e0739e6245943e06ba099172d04742de`.
At this audit the product had passed only the FITS-prefix transport check;
its structure and observation association needed separate review.

UTC differences from one request's finish to the next request record were
1.023151, 1.033550 and 1.032926 seconds. The records share one monotonic
deadline; UTC labels alone do not independently prove monotonic spacing. All
four owned Popen records contained observed handle creation FILETIMEs and
confirmed exits. The dedicated lease was absent after capture.

A limited header scan found no cookie/auth/token-named fields or credential-
like value patterns. It was not a complete privacy audit: retain native
headers and diagnostic streams locally until separately reviewed. The
reviewer did not use the network, change files, inspect spectral values, or
evaluate the holdout.
