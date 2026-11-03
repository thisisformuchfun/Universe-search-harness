# Control chain before the original-14 query

- Public TAP schema response: SHA256 `86def01aba2baa9ef9263b7477c9c7efed6cec611ad164caf29b066052903b23`; 18 rows, OK, independently reviewed fixed-fixture reader. `id1` = `specobjid`, `id2` = Gaia `source_id`, both BIGINT; blank unit cells remain unspecified.
- Published non-held positive: SHA256 `4a2ca013b79bbe7bd1d57286f7504554f640139034c8f1e2dce35183a7f809f5`; exact Gaia `1607896637338835712` and SDSS `(7028,56449,220)` recovered, with one row and independently checked finite geometry. The [paper](https://wrap.warwick.ac.uk/id/eprint/170929/1/WRAP-The-miniJPAS-survey-white-dwarf-science-with-56-optical-filters-Tremblay-2022.pdf) identifies this published white dwarf; it is not a discovery.
- Forced-empty serialization control: SHA256 `8a389807a54877647888c99308b49c539e134a9a4a1e68921d9a270e5d1b9d3e`; OK, zero explicit TABLEDATA rows, identical field attributes. Its contradictory predicate may bypass the join, so it proves neither join execution nor source coverage.

The source query is separately frozen; all IDs are exact strings derived from two saved original-14 records. `TOP 201`/`MAXREC 201` means 201 returned rows is cap-saturated/unknown. The nearest-neighbor and clean-view predicates cannot establish full SDSS coverage, independent RV epochs, source attribution, a black hole or novelty.

Additional V2 shape control: a separate query with 13 non-held sentinels and the published positive used exactly the target projection/join/TOP201/MAXREC201/order. Body SHA256 `7c2a79ab93566c877e94d6dc4e674e7bc85c4920cf375cc4d0bbbf0ccf2ddf5f`; it returned the expected positive and no sentinel rows. Both reviewers accepted the fixed control; requests at different times do not prove a shared snapshot or all-member behavior.
