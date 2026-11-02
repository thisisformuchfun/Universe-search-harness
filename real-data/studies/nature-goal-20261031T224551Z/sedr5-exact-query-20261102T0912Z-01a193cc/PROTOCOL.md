# SEDR5 exact-filename query: control then held source

Revision 2, prepared 2026-11-02 UTC and subject to independent preflight review.
The directory's `0912Z` is an allocated identifier, not its creation time.
Revision 1 was not executed: independent review found stale process identity
could be retained between stages and requested more conservative target labels.
Revision 2 resets ownership for every stage, records PID separately, and labels
filename-matching target rows as identity-unvalidated. Hypothesis:
the public SEDR5 `sexprv` search may provide per-exposure catalogue records
for the fibre observation already retrieved for held Gaia DR3
`1533365584518328576`. A positive record would be a same-observation
measurement lead, not an independent orbit or proof of source attribution.

The public [SEDR5 release](https://dr5.lamost.org/sedr5/) links the
[catalogue form](https://nadc.china-vo.org/data/data/general/sedr5/sexprv/f).
On 2026-11-02 its form declared a multipart POST; its CSV selector changed the
action to `https://nadc.china-vo.org/data/data/general/sedr5/sexprv/build.csvs`.
The target predicate is the form's `sexprv.filename.char`, with no positional
constraint and all 29 observed columns requested. The exact two multipart
bodies and their hashes are fixed before execution and saved locally. Their
empty file field contains no uploaded file or local data. No credentials,
account, cookies, redirects or retries are used.

1. First query the sample's public filename
   `20150309/HD110643N151055B02/20150309_HD110643N151055B02_15_142.fit`.
   Continue only if the CSV has the expected 29-column structure, every
   returned filename equals that literal value, and exactly one returned row
   has the sample tuple `specid=20150309HD110643N151055B0215142`, `iexp=0`,
   `mjm=82211011`, `obsid=331215142`. This controls the form predicate and
   response projection for one known sample record, not database completeness.
2. Only then query
   `20150108/HD122456N425117B01/20150108_HD122456N425117B01_01_037.fit`.
   Record raw response and identity strings only; matching filenames do not
   validate observation identity or Gaia association. A nonmatching, empty,
   truncated, unavailable or otherwise ambiguous result cannot prove absence.
   This predicate does not establish completeness, even if the control passes.

At most two serial requests, each at most 524,288 response bytes and 45 s curl
transfer, batch deadline 110 s, with at least one second between a passing
control and target request; no redirects or retries. The pause is a local
conservative choice, not a claim about the provider's rate limit. Header and diagnostic
streams have separate monitored limits; 20 ms polling can overshoot those
limits. Stop on a transport, TLS, parser, cap, identity, lease or cleanup
failure and preserve the raw failure. An existing acquisition lease is never
overwritten. Use CPU only and no shared acquisition cache.

No RV interpretation, fit, ranking, policy change, new source selection or
holdout evaluation is authorized by this protocol. If records are obtained,
their units, nulls, calibrations, quality, correlated exposures and association
must be investigated separately before any inference. Reobserved-source
selection rules must not be assumed to define the whole `sexprv` catalogue.
Headers and diagnostic streams stay local pending full privacy review.
