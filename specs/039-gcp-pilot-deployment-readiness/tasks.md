# INC-039 Tasks — GCP Pilot Deployment Readiness

1. Register and approve the bounded Graph Harness node.
2. Add fail-closed cost, schema-receipt, Cloud SQL and secret variables.
3. Implement zonal PostgreSQL 15 Cloud SQL with backups, PITR and bounded storage.
4. Attach Cloud Run through the Cloud SQL Unix socket and least-privilege IAM.
5. Reduce the required secret set to the effects-off runtime minimum.
6. Add Terraform positive/negative tests and repository contract verification.
7. Update operator documentation, cost evidence and exact continuation conditions.
8. Run Producer, Critic/Red Team, Fixer, Independent Verifier and Release Gate phases.
9. Publish exact-head CI evidence and merge only after all required checks pass.
10. Leave actual staging execution, secrets, image publication and cloud apply blocked if the hard cap remains unsatisfied.
