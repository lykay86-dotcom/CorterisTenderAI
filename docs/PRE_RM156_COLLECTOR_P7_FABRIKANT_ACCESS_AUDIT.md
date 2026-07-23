# PRE-RM-156 Collector P7 — Фабрикант access audit

Дата: 23 июля 2026 года.

Статус: `LOCALLY VALIDATED / BLOCKED_EXTERNAL / PUBLISHED_API_SCOPE_MISMATCH`; publication и exact
merge-SHA Quality Gate ожидаются. Application implementation запрещена Definition of Ready.

## 1. Entry gate

- Baseline: accepted order merge `dfe1f95f194f494b9beb33dc5c6127d31f428ce4`.
- PR #146 head `6fa6e3f93a188e39a71c9e9042cf3b41e770364a`; PR-head run `29981527538`
  успешен: jobs `89124142766` (3.12), `89124142791` (3.13).
- Exact run `29981883362` успешен: jobs `89125248024` (3.12), `89125248048` (3.13),
  включая dependency audit.
- Scope — official read-only access/legal/contract audit. Adapter, fixture, endpoint settings,
  dependency, migration и live claim не добавляются.

## 2. Existing owners

`TenderSource.FABRIKANT`, canonical ID `fabrikant`, official homepage, settings schema 7, disabled
commercial placeholder и credential descriptor уже существуют. Native sync/async adapter
отсутствует; placeholder честно остаётся `NOT_CONFIGURED`/`is_working=False`. Generic network
metadata не является audited contract. Settings, environment и keyring values не читались и не
менялись; future implementation обязана переиспользовать existing runtime, catalog/factory,
page/checkpoint/artifact, repository, settings и secret owners.

## 3. Official evidence

- <https://www.fabrikant.ru/integration-api/> официально публикует API для работы SRM-систем с
  процедурами Фабриканта и exact section matrix для 223-ФЗ, 223-ФЗ СМСП, 44-ФЗ и коммерческих
  закупок.
- Matrix включает создание/публикацию черновиков извещений и протоколов, получение предложений
  участников и запросов разъяснений. Настройка требует запросить DEMO account, реализовать
  integration по схемам и затем заменить demo credentials на production credentials.
- Та же page публично отдаёт четыре section-specific specification PDF. Спецификация 223-ФЗ не
  СМСП описывает SOAP/XML, login/password authorization, test address
  `http://demo-api.fabrikant.ru/multi-integration/common/`, production address
  `http://api.fabrikant.ru/multi-integration/common/`, schemas/examples и методы.
- Документ прямо определяет caller как внешнюю систему **заказчика** (1C, SAP и подобные). Methods
  создают собственные notices/protocols/files, получают participant proposals, status/file либо
  результат ранее отправленного request. Даже `getProcedureInfo` относится к procedure workflow
  клиента; source-wide public tender enumeration/search, change feed и complete discovery cursor
  не заявлены.
- Public human registries/cards существуют, но official page не публикует их как machine feed и не
  устанавливает automation/reuse, completeness, pagination/rate/retry или retention contract.

Использовались только official search discovery и обычные read-only `GET` official pages/PDF.
DEMO form не отправлялась; login, registration, credentials, document downloads from procedures,
bulk collection, CAPTCHA/anti-bot bypass и guessed paths не использовались. Procurement payload
или document не сохранялся как fixture.

Published organizer API является реальным и документированным, но отличается от требуемого
Collector discovery protocol. Его endpoints/auth/schema нельзя присвоить provider search adapter:
это изменило бы approved scope и могло бы работать только с процедурами конкретного заказчика.
Кроме того, для discovery отсутствуют permission, exact section coverage, enumeration/pagination/
completeness, update ordering, rate/retry, timezone/exact-money semantics, retention/reuse и
approved fixtures.

## 4. Definition of Ready verdict

| Requirement | Result |
|---|---|
| Identity | PASS — canonical Фабрикант identity подтверждена |
| Official organizer/SRM API | PASS — documented SOAP/XML contract существует |
| Organizer API endpoints/auth/schema | PASS для опубликованного scope, не для discovery |
| Collector-wide discovery/search API or feed | BLOCKED — scope mismatch |
| Permitted automated discovery/reuse | BLOCKED |
| Exact discovery section/record coverage | BLOCKED |
| Discovery pagination/date windows/completeness | BLOCKED |
| Discovery rate/retry/`Retry-After` | BLOCKED |
| Discovery timezone/currency/exact money mapping | BLOCKED |
| Approved discovery fixtures | BLOCKED; intentionally not captured |
| Raw response/document retention and reuse | BLOCKED |
| Disable/rollback | PASS — existing disabled placeholder/settings owner |

Итог: `BLOCKED_EXTERNAL / PUBLISHED_API_SCOPE_MISMATCH`. Organizer API не реализуется как tender
discovery adapter; human registry scraping и guessed enumeration запрещены. `fabrikant` остаётся
disabled/not configured.

## 5. Unblock and rollback

АО «ЭТС» должно опубликовать либо письменно подтвердить для Collector:

1. permitted source-wide discovery/search API/feed и exact covered sections/records;
2. endpoint/method/auth/schema/version lifecycle и stable field/status/document mapping;
3. pagination/date-window, ordering, update, snapshot and completeness rules;
4. rate, concurrency, retry/backoff and `Retry-After` behavior;
5. timezone, currency and exact monetary-value semantics;
6. automation, data reuse, raw response/document retention rights and limits;
7. approved redacted positive/empty/page/error/auth/rate/schema-drift fixtures.

После unblock новый package начинает с amendment этого audit и fixture governance до tests/code.
Codex форму DEMO access не отправлял и с Оператором не связывался. Rollback — revert docs-only
commit; identity/settings/credentials/DB/history и RM-107 decision неизменны.

## 6. Sequential boundary

`otc`, commercial sections, P8/P9 и production RM-156 не начинаются параллельно. Следующий package
может только принять blocker и назначить `otc` следующим P7 audit target после merge/exact.

## 7. Локальная валидация

- Focused Collector/provider contour: `34 passed in 12.19s`.
- Full baseline: `2467 passed, 2 warnings in 251.08s`; обе warnings — прежние
  `openpyxl`-предупреждения, новых warnings или зависимостей нет.
- `python -m ruff check .`, `python -m ruff format . --check` (`804 files already formatted`),
  `python -m mypy` (`20 source files`), `python scripts/check_repository_secrets.py` и
  `git diff --check` успешны.
- Pytest выполнялся с workflow-compatible `QT_QPA_PLATFORM=offscreen` и отдельным
  command-scoped `--basetemp`.

## 8. Publication acceptance

Ожидаются PR-head и exact merge-SHA Windows Quality Gate.
