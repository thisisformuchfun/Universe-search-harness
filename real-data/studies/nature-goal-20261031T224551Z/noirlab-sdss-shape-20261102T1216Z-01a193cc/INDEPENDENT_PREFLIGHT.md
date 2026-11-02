# Independent query-shape preflight

On 2026-11-02 UTC `/root/ps1_science_review` confirmed this non-held control and the original-14 query differ only in the 14 IN-list values; projection, join, TOP201/MAXREC201 and `ORDER BY x.id2,x.id1` match. The sentinels 1–13 and published positive do not overlap held IDs; unexpected sentinel rows must be preserved and reviewed. Recovery only tests this one query shape, not all-member coverage, completeness, an RV or orbit.

`/root/ps1_execution_review` accepted one GET, manifest SHA256 `30abccf1049a25266e2cccdbc84d2297ea99f96d664af666454388f66f501a03`, with all 49 pins, exact URL/query and zero held-ID overlap verified. All 20 synthetic tests passed under socket/process denial. Both capture directories were absent, custody unchanged, coordination idle and no locks present. The response requires independent TAP/type/identity review; no held-source request follows automatically.
