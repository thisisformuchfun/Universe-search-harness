# Independent forced-empty preflight

On 2026-11-02 UTC `/root/ps1_science_review` verified the query differs from the accepted positive query only by `AND x.id2=0`; all 14 fields, join, TOP20/MAXREC21 and order match. A valid explicit zero tests empty serialization only because the optimizer may skip the join.

`/root/ps1_execution_review` accepted one non-held GET, manifest SHA256 `6680fdfe90efc49baa36235d8c2a64847b4a04ec276121edeb6fec36e67f2e8f`. All 33 input pins and positive/schema chains matched; 18 isolated synthetic tests passed under network/process denial. Custody, idle state and absence of locks/capture were confirmed. The resulting HTTP response must be independently checked for leading OK, no error/overflow, exact echo, matching types and explicitly empty TABLEDATA before any held-source query.
