# PRE-RM-156 Collector P8 — TenderGuru discovery access audit

Дата: 23 июля 2026 года.

Статус: `ACCEPTED / BLOCKED_EXTERNAL / ENTITLEMENT_AND_LICENSE_REQUIRED`. TenderGuru producer
запрещён Definition of Ready.

## 1. Entry gate

- Baseline: accepted P7 matrix merge `b11b17a6481e933259dd4d52054ed93bc334d051`.
- PR #150 head `fcfed01dbe006c5b80401a976cccbf06a66915a4`; PR-head Quality Gate
  `29989342548` успешен: jobs `89148332258` (3.12), `89148332175` (3.13).
- Exact run `29989656986` успешен: jobs `89149333402` (3.12), `89149333355` (3.13),
  включая dependency audit.
- P7 access-audit pass завершён без implementation claim. P7 implementation и Collector
  prerequisite не считаются `DONE`.
- Scope — official read-only access/licensing/contract audit TenderGuru. Registration, login,
  token creation, API requests, fixture capture, dependencies, migration и live claim не входят.

## 2. Existing owners and isolation boundary

В приложении уже существуют единственные owners discovery-контура:

- `AggregatorDiscoveryRepository` и таблицы `collector_aggregator_discoveries`/
  `collector_aggregator_verification_attempts`;
- `AggregatorOfficialVerificationService`;
- explicit `is_aggregator_discovery` gate;
- bounded pending/list processing reads, read-only UI, failure/manual-review state и immutable
  attempt history;
- official identity verification только через official EIS/Mos Supplier lookup.

Existing tests доказывают, что обычная официальная запись не может попасть в discovery queue,
aggregator record не влияет на decision, а его price/title/customer/deadline не становятся
field candidates official record. Shared async engine исключает discovery items до
normalization/deduplication.

Это не доказывает полный P8. Enqueue/storage growth и attempt-history retention сейчас не имеют
принятого bound, а free-form verification note и caught exception text не проходят через общий
secret/error sanitizer. Retry scheduling/backoff также не оформлен отдельным contract. Эти
локальные gaps остаются implementation scope независимо от TenderGuru entitlement; access-audit
package их не скрывает и не меняет application code.

`tenderguru_discovery` отсутствует в canonical 13 built-in provider IDs, factory, settings и
readiness. Это соответствует ТЗ: optional discovery-only producer не является authoritative
provider. Будущий producer обязан выдавать данные исключительно в существующую queue через shared
page/artifact path; второй repository/service/catalog/factory/settings owner запрещён.

## 3. Official evidence

- Официальная общая документация:
  <https://www.tenderguru.ru/api/documentation>.
- Официальная документация тендерного API:
  <https://www.tenderguru.ru/api/documentation/tendery>.
- Официальная account/API page:
  <https://www.tenderguru.ru/api>.

Опубликован реальный API v2.3 с base URL
`https://www.tenderguru.ru/api2.3/export`. Документация описывает XML по умолчанию, JSON/CSV,
списки и карточки тендеров, фильтры, `page` pagination, online/document/product modes и
tariff-dependent fields. Доступ к платным полям/разделам выполняется по `api_code`; refresh code и
API code являются secrets и не должны попадать в repository, URL/log/error/artifact.

Документация разделяет внутренние интеграции организации и внешние/коммерческие приложения:
конкретная нагрузка, ретрансляция данных и лицензия согласуются для клиента и сценария. Полные базы
поставляются по договору; публичная публикация исходной базы, массовых файлов или полного зеркала
требует отдельного согласования. Published tariff ceilings не доказывают entitlement конкретного
аккаунта: фактический остаток/лимит запрашивается с действующим `api_code`.

Для CorterisTenderAI не предоставлены:

- приобретённый тариф или договор, разрешающий этот desktop-product use case;
- письменные условия видимости данных пользователям, локального хранения, retention и reuse;
- безопасно переданный `api_code` и подтверждённые account-specific limits;
- approved redacted responses/fixtures с provenance;
- согласованные completeness/freshness, schema/version lifecycle и change notification;
- точные timezone, currency и exact-money semantics для используемых полей.

Поэтому наличие опубликованного endpoint не является разрешением на implementation. Codex не
регистрировал аккаунт, не входил на сайт, не создавал/обновлял ключ, не вызывал API и не сохранял
TenderGuru payload, документы или персональные/контактные данные.

## 4. Definition of Ready verdict

| Requirement | Result |
|---|---|
| Provider identity and official API | PASS — TenderGuru API v2.3 документирован |
| Discovery-only isolation owner | PASS — existing queue/service/gate переиспользуются |
| Queue/attempt retention, retry and error sanitization | NOT SATISFIED LOCALLY — отдельный P8 package |
| Product-specific entitlement/license | BLOCKED |
| Auth mechanism | PARTIAL PASS — `api_code` документирован; approved credential отсутствует |
| Endpoint, formats and pagination | PARTIAL PASS — documented; exact entitled modes/fields не подтверждены |
| Schema/version lifecycle and change notification | BLOCKED |
| Coverage, ordering, freshness and completeness | BLOCKED |
| Account-specific rate/concurrency/retry limits | BLOCKED |
| Timezone/currency/exact money mapping | BLOCKED |
| Data visibility, redistribution, retention and reuse | BLOCKED |
| Approved redacted positive/empty/page/error/auth/rate/drift fixtures | BLOCKED |
| Disable/rollback | PASS — producer отсутствует, built-in readiness не меняется |

Итог: `BLOCKED_EXTERNAL / ENTITLEMENT_AND_LICENSE_REQUIRED`. `tenderguru_discovery` producer,
credentials, fixtures, host allowlist и live diagnostics не создаются. Aggregator data не
проходит в normalization, deduplication, persistence, score, recommendation или critical
stop-factor path.

## 5. Unblock requirements

До tests/code владелец должен получить от TenderGuru и безопасно предоставить:

1. договор/тариф и письменное разрешение для CorterisTenderAI desktop deployment, включая число
   пользователей и internal/external distribution boundary;
2. разрешённые endpoints/modes/fields и source/section coverage;
3. secure credential delivery через существующий environment/keyring owner без сохранения secret;
4. account-specific quotas, concurrency, retry/backoff, `Retry-After` и suspension rules;
5. pagination, ordering, update, deletion, freshness, snapshot and completeness semantics;
6. schema/version lifecycle, drift/change notification и stable identity/status/document mapping;
7. timezone, currency and exact monetary-value semantics;
8. raw response/document retention, local cache, audit artifact, display and redistribution rights;
9. approved redacted positive/empty/page/error/auth/rate/schema-drift fixtures с provenance.

После unblock отдельный amendment package сначала фиксирует fixture governance и expected-red
contracts. Минимальная реализация создаёт только discovery producer, использует shared
page/artifact contract и enqueue в existing repository; official re-fetch выполняется только
official provider. Readiness остаётся отдельной от 13 built-ins.

## 6. Sequential boundary and rollback

P9 stabilization, Collector closeout и production RM-156 не начинаются до merge и успешного fresh
exact merge-SHA Quality Gate этого audit. Следующий отдельный docs-only boundary package может
принять blocker и определить, какие P8 обязанности уже доказаны existing foundation, а какие
остаются local hardening или entitlement-conditional producer scope. Наличие external blocker не
разрешает пропустить локальные bounds/sanitization/negative-test требования P8.

Rollback — revert docs-only commit. Queue/history/settings/credentials/DB/schema/dependencies,
official providers и RM-107 deterministic decision не меняются.

## 7. Локальная валидация

- Focused discovery/isolation/catalog contour:
  `33 passed in 15.12s`.
- Full baseline:
  `2467 passed, 2 warnings in 284.59s`; обе warnings — прежние `openpyxl` notices.
- `python -m ruff check .`, `python -m ruff format . --check`
  (`804 files already formatted`), `python -m mypy` (`20 source files`),
  `python scripts/check_repository_secrets.py` и `git diff --check` успешны.
- Pytest использовал workflow-compatible `QT_QPA_PLATFORM=offscreen` и отдельные короткие unique
  command-scoped `--basetemp`. Один предварительный shell invocation был остановлен локальным
  двухсекундным tool timeout до результата; полный тестовый прогон выполнен заново на fresh
  basetemp и завершился успешно.

## 8. Publication acceptance

- PR #151 head `205d223f67da8ca0fd84732b4b14aeb1c7402662`;
- PR-head Quality Gate `29992310890`: jobs `89157719548` (Python 3.12) и `89157719632`
  (Python 3.13) успешны, включая dependency audit;
- merge commit `29aba93a4cdb24ba526dbbe265f51e859ba9754a`;
- fresh exact merge-SHA Quality Gate `29992951951`: jobs `89159721376` (Python 3.12) и
  `89159721509` (Python 3.13) успешны, включая dependency audit.

GitHub incident `Latency issues across a number of services` временно пометил Actions как
`partial outage`, а Webhooks/Pull Requests как degraded. PR dispatch потребовал reopen того же
неизменного head SHA; exact run API кратко отставал от уже завершённых job steps. После
eventual consistency run и обе job projections подтверждены `completed/success`.

Только после exact success создан отдельный P8 queue/retry/sanitization hardening worktree.
