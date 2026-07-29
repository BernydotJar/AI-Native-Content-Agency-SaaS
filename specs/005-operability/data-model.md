# Data Model

## SLO catalog

- `id`: stable objective identifier.
- `kind`: `availability`, `latency` or `freshness`.
- target fields: exact objective and 30-day error-budget or threshold.
- `indicator`: human-readable measurement definition.
- `owner`: accountable workstream.

## Alert catalog

- stable alert name, PromQL expression and `for` duration;
- bounded `severity`, `owner` and `slo` labels;
- summary and repository runbook anchor;
- deterministic exercise condition used only by the repository validator.

## Backup metric textfile

- backend label: `sqlite` or `postgresql` only;
- validated artifact bytes;
- UTC last-success epoch timestamp;
- success marker;
- no path, URL, tenant, credential, request or filename.
