# INC-028 Selection and Reconstruction Record

Date: 2026-07-31

`INC-028` is the next security/data-integrity node after the ordered merges of repository governance and authenticated-request quota. PR #37 was originally stacked on the pre-repair quota head, so its application code was reconstructed by a deterministic three-way merge:

- historical base: `702b5f58cafb5516f5491d760a384e95a355c513`;
- merged `main` with quota revision 5: `e73823de4556955d8db00dfbc10ba83db82f00fa`;
- audit implementation source: `fd232f5254adae26cdbbb2c419ad03486444c56c`.

The merge preserved session quota consumption and 429-log privacy while adding audit chaining. Historical Graph Harness projections were not copied; `INC-028` was recreated as a new node on the current event chain. Immutable off-host custody, KMS/HSM and legal non-repudiation remain external gates and are not claimed.
