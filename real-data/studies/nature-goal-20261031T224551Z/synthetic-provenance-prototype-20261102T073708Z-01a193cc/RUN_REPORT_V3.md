# Synthetic observation-provenance prototype

**Status: unadopted research preparation.** No real RV200 observation rows,
source identifiers or radial velocities were read by this prototype. It did
not select or rank sources, evaluate an orbit or holdout, change the production
harness or release a candidate. The original 14 anomalies remain held; two
are published compact-binary candidates and novelty of the other 12 remains
unresolved.

The isolated [toy graph](toy_graph_v4.py) retains synthetic rows and declared
product/contributor links. Its fixed examples show that B/R products or a
coadd and its inputs can share a declared exposure, and that two measurements
can share an intermediate product even if exposure ancestry is unknown.
Unknown and partial lineage remain incomplete; absence of declared overlap
does not establish disjointness. The graph does **not** infer
retained pixels, shared photons, source attribution, calibrated noise or
independent RV epochs. Its public interface exposes only four internally
constructed toy fixtures; the private test helper and diagnostic hooks are
not security or authorization boundaries. Twenty-one offline graph tests
passed.

A separate [draft field contract](FIELD_CONTRACT_DRAFT_V3.json) maps the 42
LAMOST and 27 GALAH descriptors in the saved query-schema projection, not the
complete catalogues. Thirty entries have partial, source-linked annotations;
39 remain wire-only and uninterpreted. The projection records no unit
attributes, which does not prove physical units do not exist. The draft says
64-bit IDs must be preserved exactly, warns against treating LAMOST categorical RV flags as
bitmasks, and records LAMOST documentation-versus-wire representation
differences. GALAH's [flags](https://www.galah-survey.org/dr4/flags/) are
survey labels/warnings, not independently confirmed companions.

The [LAMOST MRS documentation](https://lamost.org/dr11/v2.0/doc/mr-data-production-description)
describes B/R spectra and coadds, while [GALAH's catalogue documentation](https://www.galah-survey.org/dr4/the_catalogues/)
distinguishes per-star and per-observation products. These facts motivate the
bookkeeping; they do not validate the toy graph against real data. A
hypothetical float32 value near MJD 60000 has 337.5-second representable
spacing. This is not an observation uncertainty or a verified rounding model.
Seven offline schema-contract tests passed.

Before any real-data use, a separately reviewed protocol must establish
product/constituent identities, timing and frame conventions, source/fibre
attribution, error/correlation treatment, and appropriate controls. The
user's 200-source authorization covered acquisition only; a new scientific
inference or selection method requires independent review and explicit user
approval before adoption. The already-exposed 200 sources are not a fresh
holdout. No new archive acquisition was made; public documentation was
consulted through web browsing.

[Change log](CHANGELOG_V2.md), [reproduction](REPRODUCIBILITY_V2.md), [proposed
research diff](PROPOSED_RESEARCH_V3.diff), [science review](INDEPENDENT_SCIENCE_REVIEW.md)
and [execution review](INDEPENDENT_EXECUTION_REVIEW_V2.md) document the work.
The diff is for a fresh research directory, not the production checkout.
