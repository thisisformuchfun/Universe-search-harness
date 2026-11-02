# Checkpoint integrity verifier correction

An independent execution reviewer found that `verify_checkpoint.py` checked
only the previous ledger prefix and could falsely pass a modified suffix. It
is preserved in the frozen original manifest as a historical artifact; do not
rely on it to validate the appended entries.

Use `verify_checkpoint_v2.py` (SHA256
`fbf8fda43ce492a8e66c1cf7edd4f46cf694e403725b63922bcac501d2633317`)
for the local checkpoint. It pins the full provenance and ledger hashes and
checks both suffix event links, request/byte accounting, protocol/result
hashes, custody and approved integration guard. The independent reviewer
confirmed the real data pass and two in-memory corruptions fail. This check
requires the complete local native records and external coordination custody
file; it is not a self-contained verifier for the sanitized portable ZIP.
Hashes detect changes; they are not a security sandbox.

The original immutable provenance and ledger remain unchanged. The separate
versioned scientific write-ups supersede the earlier wording: they distinguish
qualified analysis of this single stack from independent source confirmation,
pin the reviewed arXiv versions, and describe multi-phase RVs as a key
independent orbit test rather than the only possible test.
