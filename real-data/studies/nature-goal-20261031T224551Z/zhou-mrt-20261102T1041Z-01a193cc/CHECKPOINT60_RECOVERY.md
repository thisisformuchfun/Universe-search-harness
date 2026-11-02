# Checkpoint 60 recovery

Report and coordination replacement are two distinct operations. If
`CHECKPOINT60_INSTALL_PENDING.json` exists without `CHECKPOINT60_INSTALL.json`,
do not repeat the installer or overwrite anything. Acquire the mutation lock,
verify custody and all live leases, and compare the actual root report and
coordination hashes with the pending event's before/after values. The original
report is preserved in `RUN_REPORT.before_checkpoint60.md`; the draft and
ledger remain separately hash-pinned. Reconcile any partial state only after
independent review, without deleting or recreating the scientific holdout.

After a committed install, the separate activation verifies the committed
event and all report, ledger and custody hashes before updating current
checkpoint pointers. If activation ends without `CHECKPOINT60_ACTIVATION.json`,
inspect the actual coordination hash and committed install event under a new
mutation lock before deciding whether any reconciliation is needed.
