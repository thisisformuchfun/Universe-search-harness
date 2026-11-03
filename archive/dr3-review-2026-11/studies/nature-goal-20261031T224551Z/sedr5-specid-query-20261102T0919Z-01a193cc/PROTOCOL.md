# SEDR5 observation-ID control and target query

Prepared 2026-11-02 UTC for independent review. A previous exact-filename
query for the held fibre observation returned HTTP 200 with a zero-byte body;
the result is ambiguous. Hypothesis: a record might be present under the
survey's observation identifier while its filename is different or its
filename predicate fails to select it. A control-first search on the distinct
`sexprv.specid.char` field can test that specific possibility. A second empty
response would still not prove catalogue absence or scientific novelty.

The [official SEDR5 documentation](https://dr5.lamost.org/sedr5/) defines
`specid` by concatenating observation date, plan ID, spectrograph and fibre
ID. The known sample control is `20150309HD110643N151055B0215142`. The
target literal, derived from the existing public product path and padded
spectrograph/fibre numbers, is `20150108HD122456N425117B0101037`. This
derivation is a query hypothesis, not independent validation of source light.

Use the official public catalogue's fixed CSV POST endpoint, 29-column
projection and `pos.type=none`. The exact multipart bodies are pinned before
execution; their empty file part contains no local file, and no cookies or
credentials are sent. First request the known sample identifier; continue
only if the exact previously observed `sexprv_` projection returns the known
unique sample tuple and all rows have its exact control specid and filename. At least one
second later request the target identifier. Save raw outputs and all identity
strings; an exact identifier remains identity-unvalidated and may carry a
different filename. Never select an alternate target from response text.

At most two serial POSTs, each limited to 524,288 response bytes and 45 s
curl transfer, with a 110 s batch deadline; no redirects or retries. The
one-second gap is a conservative local choice, not a claimed provider limit.
Header and diagnostic caps are monitored at 20 ms intervals and can overshoot.
Use a separate exclusive acquisition lease; stop on any control, transport,
parser, cap, lock or cleanup failure. Native headers may contain session
cookies and stay local without printing or portable inclusion. CPU only.

No RV interpretation or fit, ranking, new source selection, scientific
criteria, release policy or holdout evaluation is part of this acquisition.
Null, duplicate, truncated and mismatched records remain unresolved; an
independent orbit and Gaia source attribution are not established.
