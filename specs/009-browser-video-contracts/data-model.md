# Data model

## `IntegrationReviewManifest`

Immutable package resource describing one reviewed external candidate:

- schema and integration ID;
- display name, repository, commit, review timestamp and license;
- review/activation/execution/effect state;
- exact file SHA-256 map;
- capabilities, required/optional binaries and external services;
- findings and activation requirements.

The loader rejects unknown/missing fields, malformed commit/digests, duplicate
normalized paths, empty finding sets and any true effect flag.

## `IntegrationInvocationPlan`

Review-only description of a possible future action:

- tenant/campaign/workspace scope;
- operation, idempotency key, Greenlight and fence;
- virtual input/output paths;
- exact secret references and egress hosts;
- exact untrusted-input classes;
- byte, duration, attempt and cost bounds;
- `execution_permitted=false`.

It is not persisted and cannot be executed.

## `IntegrationExecutionReceipt`

Future immutable receipt shape binding scope, approval/fence, command digest,
input/output digests, provider request, cost and completion time. The current
registry cannot create one because no execution is authorized.

## API envelope

List/detail responses add only the authenticated principal's `tenant_id` to the
same immutable review data. No tenant data is stored in the manifest and no
caller may submit a tenant ID.
