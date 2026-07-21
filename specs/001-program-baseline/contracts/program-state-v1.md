# `program-state.v1`

The validator treats `task-ledger.yaml` and `task-graph.yaml` as JSON-compatible YAML. This deliberately avoids a runtime PyYAML dependency while preserving `.yaml` interoperability.

Allowed audit classifications:

`proven | contradicted | incomplete | weak_evidence | missing | not_applicable_with_justification`

Allowed task states:

`pending | spec_ready | approved | in_progress | review | done | blocked | superseded`

Allowed finding severities:

`CRITICAL | HIGH | MEDIUM | LOW | INFO`
