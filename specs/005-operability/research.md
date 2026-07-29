# Research

The runtime already emitted bounded counters, structured request logs and health/readiness endpoints, but the duration signal was a sum/count pair and could not support percentile alerts. A cumulative Prometheus histogram is the smallest compatible extension and preserves bounded method/route labels.

The repository has no Prometheus Operator dependency. Rendering `PrometheusRule` only when explicitly enabled keeps the chart valid in clusters without the CRD and prevents a manifest from being mistaken for installed monitoring.

Backup integrity is established before a freshness signal is written. A node-exporter-compatible textfile is a portable local contract, but collection, alert delivery, scheduling, encrypted off-host storage and KMS remain target-environment responsibilities.

Agentless K3s can prove Helm revision mechanics and Terraform lifecycle but cannot prove workload scheduling, traffic recovery, telemetry collection or human incident response. Those evidence levels remain separate.
