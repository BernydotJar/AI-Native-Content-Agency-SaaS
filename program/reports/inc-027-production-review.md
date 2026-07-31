# INC-027 Production Review

## Acceptance mapping

| Criterion | Evidence | Result |
|---|---|---|
| N requests pass; N+1 returns 429 | API and PostgreSQL tests | PASS |
| No denial-audit row on quota rejection | exact audit count 10 after 11 requests | PASS |
| bearer/session share principal quota | API test | PASS |
| tenant quota spans principals | API test | PASS |
| no raw identity persisted or labeled | SQLite/PostgreSQL row inspection and metric contract | PASS |
| atomic multi-bucket behavior | SQLite and PostgreSQL tests | PASS |
| schema v8 and replica authority | PostgreSQL full verifier | PASS |
| migration and backup/restore | PostgreSQL verifier | PASS |
| local/Helm/Terraform parity | runner, package and K3s apply/destroy gates | PASS |
| exact-head remote evidence | not yet run | PENDING |

## Release gate

`DENY_RELEASE` remains mandatory. This increment is production-relevant code with complete deterministic local evidence, but no production rollout, human release approval or exact-head remote artifact exists yet.

## Revision 4 supply-chain repair

A refreshed vulnerability database classified `CVE-2026-11940` and `CVE-2026-11972` as fixable because Python 3.15.0b4 appeared. The product remains on stable Python 3.13.14: 3.15.0b4 is a pre-release outside the supported runtime line. Both findings require attacker-controlled tar processing, while the runtime imports no `tarfile`, accepts no tar archive and exposes no extraction path. Exact baseline exceptions expire on 2026-08-21 and a source-level test fails if any tarfile import or extraction call is introduced. A stable compatible image or any new tar surface requires immediate reevaluation.
