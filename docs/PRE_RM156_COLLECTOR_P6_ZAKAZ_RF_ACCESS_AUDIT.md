# PRE-RM-156 Collector P6 — ZakazRF access audit

Дата: 22 июля 2026 года.

Статус: `BLOCKED_EXTERNAL`; application implementation не разрешена Definition of Ready.

## 1. Entry gate и scope

- Exact baseline: P5 merge `e9a522fc750e0893b46b0c6028c4a61cdbb9b26f`.
- P5 PR #127 head `70ce28001b0be0bfcd19937ba042ac1555919386`; PR-head run
  `29951810601` успешен на Python 3.12/3.13 (jobs `89031089368`/`89031089332`).
- Exact P5 merge-SHA run `29952451892` успешен на Python 3.12/3.13 (jobs
  `89033211301`/`89033211251`), включая dependency audit.
- Этот первый P6 provider package ограничен read-only access/legal/contract audit и документацией.
  Он не добавляет adapter, endpoint, fixture, live diagnostic, dependency, migration или readiness
  claim.

## 2. Reused owners и исходное состояние

| Boundary | Existing owner | P6 ZakazRF decision |
|---|---|---|
| Identity/source | `TenderSource.ZAKAZ_RF` + canonical provider definitions | сохранить canonical `zakaz_rf` |
| Factory | `create_default_async_providers()` | не регистрировать native adapter без DoR |
| Placeholder/readiness | commercial catalog/access adapter | оставить disabled + `NOT_CONFIGURED` |
| HTTP/rate/health | `CollectorNetworkRuntime` + `AsyncHttpClient` + shared policies | не делать сеть из production composition |
| Page/checkpoint/artifact | P3 shared contracts and `CollectorStateRepository` | будущий adapter обязан переиспользовать |
| Settings/secrets | `CollectorProviderManager`, schema 7, `app.security.secrets` | не создавать новый owner/secret |
| Decision | RM-107 deterministic owners | не затронуто |

Чистый baseline contour: `18 passed in 4.81s`. Первый запуск без scoped `--basetemp` дал пять
setup errors `WinError 5` из недоступного user temp; это не product failure. Повтор с
`.pytest_tmp/p6-baseline` прошёл полностью.

## 3. Official public evidence

Проверены только официальные ресурсы оператора:

1. <https://www.agzrt.ru/> идентифицирует АО «АГЗРТ» и ZakazRF как федеральную площадку,
   публикует официальный контакт.
2. <https://zakazrf.ru/> отвечает публичной HTML-страницей; homepage ведёт на
   `/NotificationEx`.
3. <https://zakazrf.ru/NotificationEx> отвечает `200`, `text/html; charset=utf-8`, title
   «Сводный реестр извещений» и содержит ссылки на public notice detail pages.
4. <https://zakazrf.ru/robots.txt> отвечает `200` и запрещает `/Services/`, `/QueryForms/`,
   `/Account/`, `/Document/`, `/File/` и другие закрытые/служебные contours.
5. <https://zakazrf.ru/sitemap.xml> отвечает `404`.
6. Поиск на официальных domains и bounded inspection homepage/public registry не обнаружили
   опубликованную API/feed specification, schema/version contract, data-use license, pagination,
   rate limits или raw retention permission.

Наличие public HTML не трактуется как разрешение на automation. Не выполнялись account access,
формы поиска, service paths, private endpoint discovery, CAPTCHA/anti-bot bypass или массовый
сбор. Никакие session cookies/response bodies не записаны в Git.

## 4. Definition of Ready verdict

| Requirement | Result |
|---|---|
| Confirmed identity | PASS |
| Permitted access method | BLOCKED — не опубликован/не предоставлен |
| Safe contract documentation | BLOCKED |
| Adapter hostname allowlist | BLOCKED — catalog baseline не является contract |
| Auth/rate/pagination/timezone/currency | BLOCKED |
| Positive real redacted fixture | BLOCKED; intentionally not captured |
| Empty/page/error/auth/rate/schema-drift fixtures | BLOCKED |
| Field mapping and stable external ID | BLOCKED |
| Raw retention permission | BLOCKED |
| Rollback/disable plan | PASS — existing manager, disabled/not configured |

Итог: readiness `BLOCKED_EXTERNAL`. Согласно разделам 7, 21 и 23 ТЗ expected-red adapter tests,
parser/client/adapter files и live verification начинать нельзя. Existing inert catalog identity
остаётся честным результатом, а публичный HTML не выдаётся за machine-readable contract.

## 5. Unblock и следующий пакет

Внешняя координация владельца должна получить официальный public contract или письменное
разрешение, покрывающее access/data use, concrete endpoint/page contract, limits, schema/mapping и
fixture/raw retention. После этого создаётся новый отдельный ZakazRF implementation package от
актуального exact baseline: audit amendment → approved fixture/redaction → expected-red tests →
implementation → explicit live verification → PR-head/exact Quality Gate.

Пока blocker не снят, последовательность P6 может перейти к `roseltorg` только отдельным
docs-only решением по фактической доступности official contract, как прямо разрешает ТЗ. Этот
документ сам по себе порядок не меняет.

## 6. Rollback

Application code, schema, dependencies, settings, credentials, DB, fixtures и network composition
не меняются. Rollback — revert этого docs-only package. Исторические P5 identities/aliases и exact
acceptance evidence сохраняются.

## 7. Локальная валидация

Точный docs-only working tree проверен на Python 3.12:

- focused identity/factory/catalog contour: `18 passed in 4.81s`;
- full suite: `2467 passed, 2 warnings in 275.50s`;
- Ruff: `All checks passed`;
- format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan: passed;
- `git diff --check`: passed.

Warnings — неизменные `openpyxl` extension/conditional-formatting notices в
`test_rm132_legacy_credentials_handoff`; новых warnings нет. Dependency inventory не менялся.
PR-head и exact merge-SHA Windows Quality Gate остаются обязательными до принятия этого audit
package.
