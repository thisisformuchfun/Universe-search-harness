# Local real-data run report — checkpoint 60

The complete published Zhou–Gu 19-system candidate list was compared to the original 14. None matched its 17 Table 2 or two Table 1 IDs; this finite literature check does not establish novelty. All 14 remain held; two are previously published candidate controls in Li et al., and the other 12 retain unresolved novelty. See the [comparison report](studies/nature-goal-20261031T224551Z/zhou-mrt-20261102T1041Z-01a193cc/COMPARISON_REPORT.md), [latest review queue](studies/nature-goal-20261031T224551Z/zhou-mrt-20261102T1041Z-01a193cc/REVIEW_QUEUE_V5.md), [independent review](studies/nature-goal-20261031T224551Z/zhou-mrt-20261102T1041Z-01a193cc/INDEPENDENT_COMPARISON_REVIEW.md), and [experiment ledger](studies/nature-goal-20261031T224551Z/experiment_ledger_checkpoint63.jsonl). The ledger is not the scientific holdout ledger. No policy, release or holdout evaluation changed.

The previous checkpoint follows.

# Local real-data run report — checkpoint 59



A separately retrieved [SEDR5 reference product](studies/nature-goal-20261031T224551Z/sedr5-reference-control-20261102T0941Z-01a193cc/RUN_REPORT.md)
matched the public sample's plate, spectrograph, fibre and catalogue coordinates,
and one nominal minute label. All three blue grids ascend and all three red
grids descend numerically, with no pixel-quality mask applied, matching the
held product. These are two different observations
from the same instrument and pipeline; they do not establish universal storage
order, physical alignment, calibration, source attribution or an orbit. The
reference's DATE-OBS and local DATE-BEG differ by 1,501.12 s under a fixed
UTC+08 uniform-day interpretation; their meaning remains unresolved. Both
independent reviewers accepted the limited comparison. The updated
[experiment ledger](studies/nature-goal-20261031T224551Z/experiment_ledger_checkpoint61.jsonl)
adds two reference-control entries and is not the holdout ledger. The
[current held review queue](studies/nature-goal-20261031T224551Z/sedr5-reference-control-20261102T0941Z-01a193cc/REVIEW_QUEUE_V4.md)
links the source-by-source matrix and the new evidence without changing any
disposition. The
[next safe action](studies/nature-goal-20261031T224551Z/sedr5-reference-control-20261102T0941Z-01a193cc/NEXT_ACTION.md)
contains an exact offline test command.

The public SEDR5 catalogue returned three known sample control records. Two
separate held-fibre lookups, by filename and `specid`, each returned
HTTP 200 with a zero-byte body; both remain unresolved, not catalogue
nonmatches. Those two held-fibre lookups recovered no RV; no new independently
validated orbit was established. See the
[filename query](studies/nature-goal-20261031T224551Z/sedr5-target-query-20261102T0913Z-01a193cc/RUN_REPORT.md)
and [specid diagnostic](studies/nature-goal-20261031T224551Z/sedr5-specid-query-20261102T0919Z-01a193cc/RUN_REPORT.md).
Its preserved report uses a broader label; the [identifier clarification](studies/nature-goal-20261031T224551Z/sedr5-specid-query-20261102T0919Z-01a193cc/IDENTIFIER_CLARIFICATION.md)
distinguishes `specid` from the separate `obsid` field.
Native catalogue headers contain potentially session-bearing cookies and
remain local; they are excluded from portable artifacts.

A separately reviewed [offline pixel inventory](studies/nature-goal-20261031T224551Z/sedr5-pixel-feasibility-v2-20261102T0928Z-01a193cc/RUN_REPORT.md)
found three ascending blue and three descending red wavelength grids in the
same observing sequence. An unadopted [paired-orientation prototype](studies/nature-goal-20261031T224551Z/sedr5-pixel-orientation-v2-20261102T0935Z-01a193cc/RUN_REPORT.md)
applied a common reversible permutation to six pixel vectors in each frame,
preserving their existing index relationships; 36 field/frame byte roundtrips
and eight synthetic tests passed independent
review. Physical alignment, source attribution and wavelength/RV calibration
are not established. No scientific criterion, ranking, release or holdout
changed. The per-study [experiment ledger](studies/nature-goal-20261031T224551Z/experiment_ledger_checkpoint60.jsonl)
extends the previous ledger; it is not the scientific holdout ledger.

At 2026-11-02 09:39 UTC Windows reported 66,212,484 KiB visible RAM and
46,071,624 KiB free; the RTX 4090 reported 24,564 MiB total and 0 MiB used.
The [resource sample](studies/nature-goal-20261031T224551Z/sedr5-pixel-orientation-v2-20261102T0935Z-01a193cc/RESOURCE_SAMPLE.json)
is a root transcription of approximate point-in-time readings, not peaks or
an independently replayable historical measurement. This work used CPU; the
user-managed model server was not changed. No science process is scheduled.
The holdout owner remains `astra-20261031T2113Z-01a193cc` with status
`DO_NOT_EVALUATE`. The [next safe action](studies/nature-goal-20261031T224551Z/sedr5-pixel-orientation-v2-20261102T0935Z-01a193cc/NEXT_ACTION.md)
includes an exact offline regression command.

All 14 original Gaia anomalies remain held. Two are previously published
compact-binary candidates; novelty of the other 12 is unresolved. No new
independently validated inner orbit or black hole was established.

A source-specific [SEDR5 follow-up](studies/nature-goal-20261031T224551Z/held1533-sedr5-20261102T081926Z-01a193cc/RUN_REPORT_V2.md)
retrieved a 550,080-byte public FITS product whose plate, fibre, catalogue
coordinates and observing interval match the saved DR6 record for Gaia DR3
1533365584518328576. It records three blue and three red frames with three
shared nominal same-night minute labels; these do not establish independently
calibrated, source-attributed RV epochs or an orbit.
The DR6 header reports three blue and one red exposure. Retained contributors,
source attribution and calibration are unresolved. The product's DATE-OBS
label differs by 1,500.8 seconds from local DATE-BEG converted under a fixed
UTC+08 assumption; its local-MJD label also conflicts with the local calendar
day. Neither was corrected. See the [metadata](studies/nature-goal-20261031T224551Z/held1533-sedr5-20261102T081926Z-01a193cc/metadata-v2/METADATA.json),
[local evidence manifest](studies/nature-goal-20261031T224551Z/held1533-sedr5-20261102T081926Z-01a193cc/PROVENANCE.json),
and [report addendum](studies/nature-goal-20261031T224551Z/held1533-sedr5-20261102T081926Z-01a193cc/PROVENANCE_ADDENDUM_V2.json).
Independent science and execution reviewers accepted the capture and metadata
description. At that stage no flux or RV values were analyzed and no release criterion or holdout changed.

A separately reviewed, **unadopted** synthetic provenance prototype records
declared product ancestry without claiming photon, noise or RV-epoch
independence. Its 21 graph tests passed on Windows Python 3.11.4. A draft
contract describes the saved schema projection's 42 LAMOST and 27 GALAH
fields; seven tests passed. It does not read the RV200 observations or approve
a real-data inference method. See the [research report](studies/nature-goal-20261031T224551Z/synthetic-provenance-prototype-20261102T073708Z-01a193cc/RUN_REPORT_V3.md),
[reviewed literature note](studies/nature-goal-20261031T224551Z/synthetic-provenance-prototype-20261102T073708Z-01a193cc/LITERATURE_AND_14_OBJECT_FOLLOWUP_20261102.md),
[local experiment journal](studies/nature-goal-20261031T224551Z/synthetic-provenance-prototype-20261102T073708Z-01a193cc/EXPERIMENT_JOURNAL.jsonl), and
[provenance](studies/nature-goal-20261031T224551Z/synthetic-provenance-prototype-20261102T073708Z-01a193cc/PROVENANCE_V2.json).

A [portable research supplement](artifacts/Universe_Research_Prototype_Supplement_v2_20261102T0810Z_01a193cc.zip)
(SHA256 `9de5daac3e80f54820341c523857f9b0a9f5f03f69280c363ab24ffb0b6d1952`)
contains the prototype and schema descriptors, not the full harness or
image evidence. Its suffix is an allocated identifier, not its creation
time; the manifest records the latter. Independent reviewers verified its
19 members and repeated the tests. The [proof qualification](studies/nature-goal-20261031T224551Z/synthetic-provenance-prototype-20261102T073708Z-01a193cc/PORTABLE_PROOF_QUALIFICATION_V2.md)
explains that zero network and holdout counters are uninstrumented assertions.

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
The newer research supplement is a separate, limited artifact.

At 2026-11-02 07:11 UTC the Windows 11 host reported about 63.1 GiB visible
RAM and an RTX 4090 with 24,564 MiB total and 0 MiB used at that instant;
this is not peak usage. This acquisition used CPU. The other session's model
server was not touched. The historical evaluated holdout remains quarantined;
no work is scheduled. The checkpoint 54 root report is preserved byte-for-byte in
[RUN_REPORT.before_checkpoint55.md](RUN_REPORT.before_checkpoint55.md).

At 2026-11-02 08:10 UTC, the host reported 63.1 GiB visible RAM, 44.5 GiB free,
and an RTX 4090 with 24,564 MiB total and 0 MiB used at that instant; this is
not peak usage. No new CUDA work or model-server changes were made. The
checkpoint 55 report is preserved in [RUN_REPORT.before_checkpoint56.md](RUN_REPORT.before_checkpoint56.md).

The checkpoint 56 report is preserved in [RUN_REPORT.before_checkpoint57.md](RUN_REPORT.before_checkpoint57.md).
The latest SEDR5 evidence remains local; the earlier portable archives predate it.
