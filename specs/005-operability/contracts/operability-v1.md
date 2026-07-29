# `operability.v1`

Artifacts:

- `ops/slo-catalog.json`
- `ops/alert-catalog.json`
- `ops/alert-exercises.json`
- `infra/monitoring/prometheus-rules.yaml`

The validator requires unique identifiers, exact alert/rule parity, valid SLO targets, mathematically correct availability error budgets, existing runbook anchors and deterministic exercise outcomes. A PASS is repository evidence only; it does not mean alerts were loaded by a production monitoring system or delivered to a human.
