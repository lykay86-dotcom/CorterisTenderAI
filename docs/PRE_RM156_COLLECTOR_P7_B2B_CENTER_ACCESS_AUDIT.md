# PRE-RM-156 Collector P7 — B2B-Center access audit

Дата: 23 июля 2026 года.

Статус: `ACCEPTED / BLOCKED_EXTERNAL / CONTRACT_AND_PERMISSION_GATED`. Application implementation
запрещена Definition of Ready.

## 1. Entry gate

- Baseline: accepted P6/P7 boundary merge `e54fd46d6525e378cd90795f35ae144f00fffe31`.
- PR #144 head `ddd3d37a7f13a10d45b29a1c3c5496f38ff9e1e8`; PR-head Quality Gate
  `29979195455` успешен: jobs `89118148283` (3.12), `89118148873` (3.13).
- Exact merge-SHA run `29979715877` успешен fresh run: jobs `89118819142` (3.12),
  `89118819085` (3.13), включая dependency audit.
- Scope — official read-only access/legal/contract audit. Adapter, fixture, endpoint settings,
  dependency, migration и live claim не добавляются.

## 2. Existing owners

`TenderSource.B2B_CENTER` и canonical ID `b2b_center` уже существуют. Commercial catalog хранит
official homepage `https://www.b2b-center.ru/`, priority 110, settings schema 7, disabled readiness
placeholder и `CONTRACT_AND_API` access requirement. Non-secret settings используют существующие
`CORTERIS_B2B_ENABLED`, `CORTERIS_B2B_ACCESS_CONFIRMED` и `CORTERIS_B2B_API_BASE_URL`; secret owner —
`collector.b2b_center.api_key` / `CORTERIS_B2B_API_KEY`. Значения settings, environment и keyring не
читались и не менялись.

Default sync registry и optional async commercial catalog сохраняют inert placeholders. Native
sync/async B2B-Center adapter отсутствует; операции честно завершаются `NOT_CONFIGURED`, а
`is_working=False`. Generic network metadata разрешает только `b2b-center.ru` и
`www.b2b-center.ru`, но не является audited endpoint/protocol contract. Future implementation
обязана переиспользовать shared runtime, page/checkpoint/artifact, repository, settings и secret
owners без второго catalog/factory.

## 3. Official evidence

- <https://www.b2b-center.ru/news/?id=520> подтверждает существование web service/API для
  взаимодействия клиентских ИТ-систем с площадкой и модулями B2B-Center. Официальное обновление от
  29 июля 2025 года говорит о методах, сгруппированных по module/class/function, карточках методов,
  тарифе каждого метода, downloadable consolidated documentation и XML examples.
- Та же official page направляет за методами, документацией и XML examples в Личный кабинет.
  Прямая official ссылка ведёт на
  <https://www.b2b-center.ru/market/remote_doc.html?action=docs>, где ordinary unauthenticated GET
  показывает только login form. Public method list, endpoint/method/auth contract, schema или
  example payload не раскрываются.
- <https://www.b2b-center.ru/plus/> описывает API transfer на любом этапе закупки, готовый web
  service, interactive documentation и implementation support как отдельную integration service.
  Это подтверждает machine-access product, но не его coverage или Collector-ready contract.
- <https://www.b2b-center.ru/news/?id=464> связывает API с определёнными платными тарифами.
  Актуальный официальный Регламент на
  <https://www.b2b-center.ru/help/Регламент_Системы_B2B-Center/> дополнительно устанавливает, что
  права на секции и сервисы определяются отдельными договорами и тарифами.
- Раздел 5.4 того же Регламента запрещает пользователю, действующему от имени участника, без
  письменного согласия Оператора применять robots/programs/algorithms для автоматизированного
  сбора страниц, таблиц, database content и файлов или автоматизации действий. Отдельно указан
  ceiling 60 HTTP requests/minute с одного IP и право блокировки automated clients.
- Public human search <https://www.b2b-center.ru/market/> показывает актуальные и архивные procedure
  cards, но сам по себе не предоставляет разрешённый machine contract, source-wide completeness
  или reuse/retention rights. Его HTML не используется как replacement для gated API.

Использовались только official search discovery и обычные read-only `GET`. Login, registration,
forms, credentials, JavaScript/cookie replay, document download, bulk collection, CAPTCHA/anti-bot
bypass, guessed API paths и private methods не использовались. Procurement payload или document
не сохранялся как fixture.

Official evidence существенно лучше generic placeholder: B2B-Center действительно предоставляет
договорный API. Но repository не содержит подтверждённого договора/тарифа/письменного consent,
экспортированной документации из Личного кабинета или разрешённого response. Поэтому невозможно
аудировать точные endpoints/methods/auth, covered sections and records, schema/version lifecycle,
pagination/date-window/completeness, API-specific rate/retry behavior, timezone/currency/exact-money
semantics, stable status/document mapping, retention/reuse limits и fixtures.

## 4. Definition of Ready verdict

| Requirement | Result |
|---|---|
| Identity | PASS — canonical B2B-Center identity подтверждена |
| Official machine API product | PASS — web service/API официально существует |
| Public human search/cards | PASS, но не machine contract |
| Contract/tariff and written automation permission | BLOCKED |
| API documentation and XML examples | BLOCKED — доступны после login в Личном кабинете |
| Exact endpoint/method/auth and section coverage | BLOCKED |
| Request/response schema and version lifecycle | BLOCKED |
| Pagination/date windows/snapshot completeness | BLOCKED |
| API rate/retry/`Retry-After` | BLOCKED; public ceiling не заменяет method contract |
| Timezone/currency/exact money semantics | BLOCKED |
| Stable identity/status/document mapping | BLOCKED |
| Approved real fixtures | BLOCKED; intentionally not captured |
| Raw response/document retention and reuse | BLOCKED |
| Disable/rollback | PASS — existing disabled placeholder/settings owner |

Итог: `BLOCKED_EXTERNAL / CONTRACT_AND_PERMISSION_GATED`. Parser/client, expected-red adapter
tests, fixture capture и live verification не начинаются через human HTML, login automation или
guessed API. `b2b_center` остаётся disabled/not configured.

## 5. Unblock and rollback

Владелец должен предоставить auditable B2B-Center entitlement без помещения secrets в repository:

1. действующий договор/тариф и письменное consent либо contract clause, разрешающие требуемую API
   automation, collection, reuse и retention;
2. exported official API documentation/XML examples из Личного кабинета с version/date;
3. exact endpoints, methods, covered sections/records и authentication model;
4. schema/version lifecycle, field/status/document mapping и compatibility policy;
5. pagination/date-window, ordering, update, snapshot and completeness rules;
6. API-specific rate, concurrency, retry/backoff and `Retry-After` behavior;
7. timezone, currency and exact monetary-value semantics;
8. raw response/document retention/redaction limits и approved redacted positive/empty/page/error/
   auth/rate/schema-drift fixtures.

После unblock новый B2B-Center package начинается с amendment этого audit и fixture governance до
tests/code. Codex не регистрировался, не входил и не связывался с Оператором.

Этот docs-only audit откатывается revert-коммитом; identity, settings, credential descriptor, DB и
historical data не меняются. RM-107 score/recommendation/critical stop-factor priority неизменны.

## 6. Sequential boundary

`fabrikant`, `otc`, commercial sections, P8/P9 и production RM-156 не начинаются параллельно.
Следующий package может только принять этот B2B-Center blocker и назначить `fabrikant` следующим
P7 access-audit target; отдельный Фабрикант audit разрешён лишь после merge и успешного exact
merge-SHA Quality Gate этого package.

## 7. Локальная валидация

- focused identity/factory/catalog contour: `34 passed in 13.30s`;
- full suite: `2467 passed, 2 warnings in 249.03s`;
- Ruff: `All checks passed`; format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan и `git diff --check`: passed.

Pytest использовал workflow `QT_QPA_PLATFORM=offscreen` и fresh command-scoped `--basetemp`.
Warnings — неизменные `openpyxl` notices; dependencies/tests/thresholds не менялись.

## 8. Publication acceptance

- PR #145 head `d4c0f2fb41fe77c5df642884d29016af0cd0442c`;
- PR-head Quality Gate `29980582710`: jobs `89121318689` (Python 3.12) и `89121318642`
  (Python 3.13) успешны;
- merge commit `f7b20a4a5c5d0ee260b04721347c66b8ee2dad2a`;
- exact merge-SHA Quality Gate `29980836778`: jobs `89122049907` (Python 3.12) и
  `89122049924` (Python 3.13) успешно прошли fresh run, включая dependency audit.

Только после exact success создан отдельный docs-only worktree перехода к `fabrikant`.
