# PRE-RM-156 Collector prerequisite — canonical closeout

Дата: 23 июля 2026 года.

Статус: `ACCEPTED`.

## 1. Decision

Collector prerequisite принимается как технически завершённый. External access blockers
принимаются как документированные blockers и не блокируют возврат к production RM-156.

Указание владельца продолжать без дополнительных подтверждений трактуется только как принятие
этой blocker policy. Оно не является утверждением, что внешние площадки работают, не разрешает
scraping/registration/login и не создаёт API/data-use entitlement.

Honest final matrix:

- built-ins: `13`;
- `WORKING`: `0`;
- `BLOCKED_EXTERNAL`: `13`;
- `DISABLED`: runtime user choice, не readiness masking;
- discovery aggregator TenderGuru:
  `BLOCKED_EXTERNAL / ENTITLEMENT_AND_LICENSE_REQUIRED`, не built-in и не authoritative.

## 2. Definition of Done audit

| Requirement | Evidence | Result |
|---|---|---|
| P0/P1 audit, contract, plan, rollback before application changes | PR #121/#122 and exact gates | PASS |
| Expected-red before implementation | P2 plus P4/P5/P8/P9 test-first packages | PASS |
| No duplicate engine/catalog/factory/settings/credential/health/checkpoint owner | P1 inventory; P3–P9 reuse accepted owners | PASS |
| Required correctness fixes | P3 shared foundation and accepted P4 references | PASS |
| EIS and Mos Supplier common adapter contract | P4 validations, fixtures, artifacts/checkpoints | PASS (`IMPLEMENTED_OFFLINE`) |
| Exact 13 unique built-ins | P5 identity/schema-16 acceptance and P9 diagnostic | PASS |
| Every unavailable provider honest | P6/P7 audits and 13 provider docs | PASS (`BLOCKED_EXTERNAL`) |
| Every `WORKING` provider has live evidence | no provider claims `WORKING` | PASS / no false claim |
| Bounded pagination/cancellation/checkpoint/provenance | accepted P3/P4 contracts and P9 rerun | PASS |
| Aggregator discovery-only | P8 isolation/queue hardening | PASS |
| Migration/backup/restore | schema 15→16 verified backup/explicit restore and P9 drill | PASS |
| Secrets/access restrictions | negative tests, secret scan, fixed health error, no guessed endpoints | PASS |
| Performance/resources | exact 10k/5k, 25 cycles, cancellation budget | PASS |
| Operations/support/provider/rollback docs | `COLLECTOR_OPERATIONS.md`, 13 `docs/providers` files | PASS |
| Focused/full/static/build/frozen/dependency/Windows gates | local P9 evidence, PR #155 and exact run | PASS |
| RM-107 deterministic decision unchanged | no score/recommendation/critical stop-factor change | PASS |

## 3. Final P9 evidence

- Feature commits:
  - tests `c15ab0f`;
  - implementation `cdca6de`;
  - documentation `f9d7785`.
- PR #155 head `f9d77857102588750432264186df4b0b268f2788`.
- PR-head run `30001707776` successful:
  - Python 3.12 job `89188165195`;
  - Python 3.13 job `89188165230`;
  - dependency audit successful in both.
- Merge `7101396f24885144807f0f60c72b798e48c7861a`.
- Fresh exact run `30002186102`:
  - attempt 1 Python 3.12 job `89189715981` ended in a native Windows
    `access violation` at 37% of full pytest without a Python assertion/test failure;
  - the same attempt's Python 3.13 job succeeded;
  - unchanged-SHA failed-job rerun attempt 2 completed successfully;
  - final jobs `89191332161` (3.12) and `89191333148` (3.13) both succeeded, including dependency
    audit.

The native crash is preserved as environment/timing evidence. No test, threshold or application
code was changed to hide it.

Closeout-local validation: canonical P9/prerequisite/identity contour
`30 passed in 13.07s`; repository secret scan и `git diff --check` successful.

## 4. Canonical transition

After merge of this closeout and its fresh exact merge-SHA Quality Gate:

- Collector prerequisite becomes `DONE`;
- RM-156 remains the only canonical `IN PROGRESS` stage;
- production work for RM-156 contractor model resumes;
- the next package must be RM-156 audit-first, not RM-157/RM-158;
- RM-157–RM-200 remain `PLANNED`;
- external provider blockers remain visible and can be unblocked only by new lawful access
  evidence in separate packages.

## 5. Rollback

Closeout rollback is docs-only. Reverting it pauses production RM-156 again but does not revert
accepted Collector features, downgrade schema, delete backups/artifacts/checkpoints/tenders,
change credentials/settings or alter RM-107 decisions. Feature packages retain their independent
rollback boundaries.

## 6. Publication evidence

- Closeout commit `e105b20`.
- PR #156 head `e105b202b342da975c61fc430d713f385f180be8`.
- PR-head run `30003448590` successful:
  - Python 3.12 job `89193776310`;
  - Python 3.13 job `89193776412`.
- Merge `e2eeac22497ec90b108fc02765089a92c6fdfc55`.
- Fresh exact merge-SHA run `30004268816` successful:
  - Python 3.12 job `89196436206`;
  - Python 3.13 job `89196436327`;
  - dependency audit successful в обеих jobs.

Collector prerequisite завершён. Следующий отдельный package — RM-156 audit-first.
