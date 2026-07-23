# PRE-RM-156 Collector P8 — aggregator discovery closeout

Дата: 23 июля 2026 года.

Статус: `LOCALLY VALIDATED / PUBLICATION PENDING`.

## 1. Решение

P8 закрывается честно без `tenderguru_discovery` producer:

- optional producer разрешён ТЗ только при подтверждённом API/data access;
- TenderGuru остаётся
  `BLOCKED_EXTERNAL / ENTITLEMENT_AND_LICENSE_REQUIRED`;
- registration/login/API calls, credentials, fixtures и guessed endpoint implementation не
  выполнялись;
- existing discovery queue и official-verification gate остаются единственными owners;
- aggregator evidence не входит в authoritative normalization, persistence, score,
  recommendation или critical stop-factor path;
- queue/payload/attempt bounds, retry, sanitization и capacity availability приняты отдельным
  hardening package.

`BLOCKED_EXTERNAL` является честной readiness, а не placeholder success. Утверждение, что
TenderGuru или все площадки работают, запрещено.

## 2. Принятые доказательства

### Access audit

- PR #151 head `205d223f67da8ca0fd84732b4b14aeb1c7402662`;
- PR-head run `29992310890`, jobs `89157719548`/`89157719632`;
- merge `29aba93a4cdb24ba526dbbe265f51e859ba9754a`;
- exact run `29992951951`, jobs `89159721376`/`89159721509`.

### Queue hardening

- commits `16829e7`, `864862c`, `df91a4c`;
- PR #152 head `df91a4cdcb5923f31b7be4501e85cd25e7329485`;
- PR-head run `29996521546`, jobs `89171378944` (3.12) и `89171378841` (3.13);
- merge `593ea5c7d3657e881fad985933444a44aa12b0f1`;
- exact run `29996926693`, jobs `89172697592` (3.12) и `89172697637` (3.13).

Обе exact Windows-матрицы завершились успешно, включая full suite и dependency audit. Последняя
локальная hardening validation: focused `51 passed`, full `2474 passed, 2` прежних `openpyxl`
warnings, atomic race `5/5`, Ruff/format/mypy/secret scan/diff check успешны.

Для этого docs-only boundary локально повторно прошёл canonical prerequisite contour:
`23 passed in 5.80s`; repository secret scan и `git diff --check` успешны.

## 3. Boundary

После merge этого docs-only closeout и успешного fresh exact merge-SHA Quality Gate:

- P8 считается завершённым с документированным external blocker;
- единственным следующим Collector package становится P9 stabilization;
- P9 начинает с audit/inventory и expected-red characterization, а не с closeout claim;
- Collector prerequisite остаётся `IN PROGRESS`;
- production RM-156 остаётся приостановлен;
- RM-157 и RM-158 не начинаются;
- возврат к production RM-156 возможен только отдельным canonical Collector closeout после
  выполнения всех P9 acceptance gates.

До merge/exact этого документа P9 не начинается.

## 4. Rollback

Rollback boundary package — revert только документационного commit. Он не изменяет schema,
settings, credentials, fixtures, provider readiness, persisted tenders или deterministic RM-107
decision logic. Hardening package откатывается независимо по его собственному rollback plan.
