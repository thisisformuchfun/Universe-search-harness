# Local real-data run report — checkpoint 55

All 14 original Gaia anomalies remain held. Two are previously published
compact-binary candidates; novelty of the other 12 is unresolved. No new
independently validated inner orbit or black hole was established.

An offline follow-up of the saved PS1 stack found that eight of its 30 input
names share the four-digit truncated-date suffix of the single-detection
catalogue epoch. This is possible overlap only; the exact exposure and its
pixel contribution remain unverified. Two interior image peaks are not
validated PSF controls and a brighter potential reference is clipped at the
edge. The survey documents its upstream `.wt` product as a variance map,
but this cutout's scaling and covariance remain unvalidated. See the
[feasibility report](studies/nature-goal-20261031T224551Z/held1533-offline-feasibility-20261102T072412Z-01a193cc/REPORT_V2.md),
[pixel-value clarification](studies/nature-goal-20261031T224551Z/held1533-offline-feasibility-20261102T072412Z-01a193cc/PIXEL_VALUE_CLARIFICATION.md),
and [provenance](studies/nature-goal-20261031T224551Z/held1533-offline-feasibility-20261102T072412Z-01a193cc/PROVENANCE.json).
Independent reviewers caught an out-of-image slicing bug and a missing
ICRS-to-FK5 conversion in the initial exploratory script; the corrected
version passed five regression tests. The original output is preserved.
No new native archive request, source disposition or holdout evaluation
resulted from this offline follow-up.

A new controlled PS1 i-band image acquisition for Gaia DR3
1533365584518328576 returned usable field context. The one-detection PS1
position lies on a bright image feature's wing without a distinct local peak
in the inspected box. Seeing, sensitivity, absolute astrometry and exposure
independence remain unverified, so this is neither a calibrated non-detection
nor a confirmed neighbour. It does not identify the light in the existing
low-S/N LAMOST spectrum. The descriptive acquisition is complete; qualified
future image analysis and independent phase-resolved measurements remain
possible, subject to an appropriate reviewed protocol.

See the [current image report](studies/nature-goal-20261031T224551Z/held1533-ps1-image-20261102T0648Z-01a193cc/RUN_REPORT_V3.md),
[14-source matrix](studies/nature-goal-20261031T224551Z/held14-rv-recovery-20261102T0622Z-01a193cc/SOURCE_MATRIX.md),
[review queue](studies/nature-goal-20261031T224551Z/held1533-ps1-image-20261102T0648Z-01a193cc/REVIEW_QUEUE_V3.md),
[provenance](studies/nature-goal-20261031T224551Z/held1533-ps1-image-20261102T0648Z-01a193cc/PROVENANCE.json),
[reviewed correction addendum](studies/nature-goal-20261031T224551Z/held1533-ps1-image-20261102T0648Z-01a193cc/PROVENANCE_ADDENDUM.json),
[experiment ledger](studies/nature-goal-20261031T224551Z/experiment_ledger_checkpoint59.jsonl), and
[next action](studies/nature-goal-20261031T224551Z/held1533-offline-feasibility-20261102T072412Z-01a193cc/NEXT_ACTION.md).
Seven native image requests returned HTTP 200; two saved controls passed.
Twenty-five offline capture tests passed. An independent reviewer found a
ledger-suffix weakness in the first local verifier; the separately reviewed
[V2 verifier](studies/nature-goal-20261031T224551Z/held1533-ps1-image-20261102T0648Z-01a193cc/VERIFIER_CORRECTION_V2.md)
checks the full ledger hash and new entries, and detected the demonstrated corruption.

The prior 500-row reference snapshot is preserved: 17 anomalies, 14 held,
two known black holes and one refuted case excluded, zero released. It was
quality selected and is not a representative sky census. The approved
integration guard verified as `558cef0d2d1cab72110c03e2089009ef8cdaf031c63247f8e345bfbbbb81953c`.
The original baseline ZIP and approved patch/diff remain separate. No
scientific criterion, ranking, release policy or holdout changed.

The [portable checkpoint 53 ZIP](artifacts/Universe_Search_Harness_Checkpoint53_20261102_01a193cc.zip)
(SHA256 `bff3862e1f6e42e31c94795f0ec547c7c7d0b6c07c6c8905f0c03405a2669d20`)
predates this image work; its [manifest](artifacts/Universe_Search_Harness_Checkpoint53_20261102_01a193cc.zip.manifest.json)
records its scope. The latest evidence and its native records remain local.
No new archive was built solely to repeat an unresolved conclusion.

At 2026-11-02 07:11 UTC the Windows 11 host reported about 63.1 GiB visible
RAM and an RTX 4090 with 24,564 MiB total and 0 MiB used at that instant;
this is not peak usage. This acquisition used CPU. The other session's model
server was not touched. The historical evaluated holdout remains quarantined;
no work is scheduled. The checkpoint 54 root report is preserved byte-for-byte in
[RUN_REPORT.before_checkpoint55.md](RUN_REPORT.before_checkpoint55.md).
