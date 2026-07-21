# Release Rollback Runbook

Status: local control-plane drill implemented; production rollback remains human-gated.

## Preconditions

- Identify environment, release name, namespace, current revision and target revision.
- Confirm the target revision used a schema compatible with the currently persisted data.
- Preserve logs, metrics, image digest and current Helm values before mutation.
- Obtain approval for production traffic or persistent environment changes.

## Helm rollback

```bash
helm history ai-native-content-agency \
  --namespace ai-native-content-agency

helm rollback ai-native-content-agency <previous-revision> \
  --namespace ai-native-content-agency \
  --wait --timeout 5m
```

Verify:

1. Helm reports the rollback revision as deployed.
2. The rendered configuration matches the reviewed previous value set.
3. `/healthz` and `/readyz` pass from the authorized workload network.
4. Error rate and p95 latency recover.
5. No schema downgrade or destructive data operation occurred.

## Database boundary

Application rollback is not schema rollback. Do not downgrade PostgreSQL or restore a backup merely to match an older image. Use expand/contract migrations and verify compatibility first. Persistent restore requires a declared recovery point, write freeze, checksum verification and accountable approval.

## Repository drill

`./scripts/verify-local-infrastructure.sh` performs an agentless disposable Helm upgrade and rollback, then proves the original bounded configuration was restored. This demonstrates Helm control-plane mechanics only; it does not demonstrate pod scheduling, traffic switching or production recovery time.

## Failure handling

If rollback fails, freeze further release changes, preserve the failed revision and classify whether the failure is chart, Kubernetes API, Secret/configuration, image or database compatibility. Do not use `--force` or delete persistent resources as an unreviewed shortcut.
