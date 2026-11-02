# Zhou–Gu 2026: complete 19-candidate literature check

On 2026-11-02 UTC, the official publisher-linked [machine-readable Table 2](https://content.cld.iop.org/journals/0004-637X/1010/2/216/revision1/apjaeaa3at2_mrt.txt)
was retrieved in one HTTPS GET: HTTP 200, TLS verification result 0, no
redirects, 7,874 bytes, SHA-256
`94f41f32f8c0d34798fc223d4af10fd19a16fc63bc9e30069a6d2ff4ead90267`.
The exact request, transfer and process lifecycle are in `capture-v9/`; native
headers and diagnostics remain local. The body itself names the authors and
Table 2 but does not carry the article DOI. Its association with [Zhou and Gu](https://doi.org/10.3847/1538-4357/aeaa3a)
rests on the saved publisher page, its independently checked Table 2 links,
the verified HTTPS capture and consistent internal descriptors.

The table declares 17 records of 197 ASCII bytes and `GaiaDR3` in bytes 1–19.
The reviewed comparator verified 17 unique exact decimal ID strings, the
fixed-width ID and Type fields, five Type II and twelve Type III records,
and all four article-preview ID/type controls. A separate science reviewer
checked syntax of the other declared fields; the comparator itself does not
validate those values. The two Type I IDs were independently verified in the
publisher page's Table 1 and are not part of Table 2.

**None of the original 14 held Gaia IDs matches these 17 Table 2 IDs or the
two separately listed Type I IDs.** This is an exact-string comparison to one
published 19-system sample. It does not establish novelty in the literature,
exclude other spectra or companions, validate an orbit, or establish a BH.
The two original held sources already listed by [Li et al. 2026](https://arxiv.org/html/2610.34715v1)
remain published-candidate controls; the other 12 retain unresolved novelty.
All 14 remain held.

The [result](COMPARISON_RESULT_V3.json), [frozen input manifest](COMPARE_MANIFEST_V3.json),
and [source-by-source matrix](../held14-rv-recovery-20261102T0622Z-01a193cc/SOURCE_MATRIX.md)
record the comparison and remaining alternatives. Twelve synthetic parser
tests passed; independent science and execution reviewers accepted the pinned
comparison. No scientific criterion, production disposition or holdout changed.

On the originating PC, using the session's Windows Python 3.11 environment:

```powershell
Set-Location -LiteralPath 'C:\gogogo\universe search harness\blackhole search\astra-20261031T2113Z-01a193cc\studies\nature-goal-20261031T224551Z\zhou-mrt-20261102T1041Z-01a193cc'
& 'C:\gogogo\universe search harness\blackhole search\astra-20261031T2113Z-01a193cc\.venv-fits-study\Scripts\python.exe' -B -m unittest -v test_compare_table_v3
```

The observed-data result is immutable. To reproduce the comparison itself,
use a new output directory and preserve the manifest-pinned inputs; do not
overwrite `COMPARISON_RESULT_V3.json` or reset the scientific holdout.
