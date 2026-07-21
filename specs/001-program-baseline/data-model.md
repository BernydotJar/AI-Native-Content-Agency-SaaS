# Program Data Model

## Requirement row

- `requirement_id`: globally unique stable identifier
- `domain`: product, engineering, data, security, UX, operations, delivery, testing, legal, integrations, supply_chain, governance
- `requirement`: human-readable obligation
- `classification`: proven, contradicted, incomplete, weak_evidence, missing, not_applicable_with_justification
- `authoritative_evidence`: exact evidence pointer or explicit absence
- `next_action`: closure action
- `owner`: workstream

## Task graph node

- `id`
- `status`
- `depends_on[]`

## Finding

- `id`
- `severity`
- `status`
- `description`
- `evidence`
- `owner`

## Evidence record

- gate, scope, command/artifact, environment, observed, result, limitations, commit, timestamp
