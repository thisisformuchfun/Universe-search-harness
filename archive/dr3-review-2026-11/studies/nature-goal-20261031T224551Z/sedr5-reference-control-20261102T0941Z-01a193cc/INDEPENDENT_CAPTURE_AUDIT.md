# Independent reference capture audit

Accepted 2026-11-02 UTC for transport and FITS prefix only. The reviewer
checked the frozen manifest and source pins, historical root gate, sample
identity, fixed day→plan→product GETs, literal child links and native hashes.
Each request returned HTTP 200, TLS verify 0, no redirects, no cap overage,
and a distinct owned child with observed creation time and confirmed exit;
the lease was absent. The body sizes were 817, 320,126 and 550,080 bytes.
The product SHA-256 is
`0e1c7ac03810cd41ad1df477f0977d82e92ba1bad71e442912ca282b339fb439`;
capture results SHA-256 is
`f5e6881fbe18a3444f53464f1e053bc2f6e41c70c02e5b97142f15b92a7c4899`.

UTC completion-to-next-request gaps were 1.038083 and 1.039997 s; a common
deadline was recorded, while UTC alone does not independently prove a
monotonic gap. The product's observation identity was still pending separate
metadata review. A limited scan found no cookie/auth/token-named fields or
obvious diagnostic markers; native headers and streams nevertheless remain
local pending full privacy review. No network, edits, GPU or holdout were used
in the independent audit.
