# Data model

## Third-party inventory

- exact repository license path/hash;
- evidence file path/hash pairs;
- direct npm/Python name, exact version, scope and license;
- OCI image/digest pairs;
- Action/revision/workflow triples;
- external candidates with exact repository/commit/license/status;
- active provider list, required to remain empty;
- transitive evidence pointers.

## Privacy decision register

- operating entity, jurisdiction and controller/processor role;
- risk classification and release recommendation;
- policy scopes with class, status, retention, deletion and legal hold;
- provider decisions with data categories and contract/region/training/retention/
  deletion states;
- reviewers and exact resume conditions.

Current UNKNOWN/unapproved state requires null retention and false destructive
implementation.

## Public claims policy

- exact scanned surfaces;
- prohibited regex IDs/patterns;
- required path/text disclosures;
- allowed release label `sandbox_candidate`.

## Release decision

- deny/allow booleans for release, cloud apply, effects and destructive action;
- legal/privacy and independent approval flags;
- unresolved finding IDs and reason codes;
- source documents.

The current model has no state transition to allow release. A future approved
state requires a separately reviewed schema/version and accountable evidence.
