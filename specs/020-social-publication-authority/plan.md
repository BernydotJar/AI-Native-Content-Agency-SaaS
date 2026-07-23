# Plan

1. Reuse the durable outbound intent/fence/receipt architecture from INC-015.
2. Add channel-specific publication descriptors and exact artifact/media binding.
3. Implement X create-post and Instagram media-container/publish adapters.
4. Add SQLite/PostgreSQL race, replay, unknown-outcome and revocation tests.
5. Expose an admin/operator confirmation that names account, channel and exact output.
6. Keep real provider calls disabled until all mock/package gates pass.
7. Perform explicitly authorized sandbox posts and reconcile their receipts.
