# PRE-RM-156 Collector P7 — OTC access audit

Дата: 23 июля 2026 года.

Статус: `LOCALLY VALIDATED / BLOCKED_EXTERNAL / PUBLIC_HTML_WITHOUT_MACHINE_CONTRACT`;
publication и exact merge-SHA Quality Gate ожидаются. Application implementation запрещена
Definition of Ready.

## 1. Entry gate

- Baseline: accepted order merge `5c087726e2cb32c88c6b9760d8b43b887da4234f`.
- PR #148 head `3ba012506e147a4a8392e8a1dea75e153307e016`; PR-head run `29986076319`
  успешен: jobs `89138089157` (3.12), `89138089106` (3.13).
- Exact run `29986457553` успешен: jobs `89139297913` (3.12), `89139297894` (3.13),
  включая dependency audit.
- Scope — official read-only access/legal/contract audit. Adapter, fixture, endpoint settings,
  dependency, migration и live claim не добавляются.

## 2. Existing owners

`TenderSource.OTC`, canonical ID `otc`, official homepage, settings schema 7, disabled commercial
placeholder и credential descriptor уже существуют. Native sync/async adapter отсутствует;
placeholder честно остаётся `NOT_CONFIGURED`/`is_working=False`. Generic allowlist
`otc.ru`/`www.otc.ru` не является audited contract. Settings, environment и keyring values не
читались и не менялись.

АО «ОТС» входит в общую группу с РТС-тендер и B2B-Center, но existing canonical identities
отдельны. Common ownership не доказывает общий endpoint, schema, permission или adapter. Future
implementation обязана переиспользовать existing runtime, catalog/factory, page/checkpoint/
artifact, repository, settings и secret owners без alias или второго provider owner.

## 3. Official evidence

- <https://otc.ru/buy/etp/41-otc/> публикует human-facing страницу «Закупки и тендеры по OTC» с
  фильтрами 44-ФЗ, 223-ФЗ, 615-ПП РФ, малых и коммерческих закупок, status, region, customer,
  ОКПД2 и price. Result cards показывают EIS/platform numbers, amounts и сроки в МСК.
- Human detail pages вида <https://otc.ru/tender/83512136> показывают предмет, позиции, заказчика,
  цену, правила и электронную площадку. Это доказывает публичную web presentation, но не
  machine-readable contract.
- Официальный
  <https://samara.otc.ru/Portals/0/Files/Content/pdf/01.09.2023_reglament-raboty-ehlektronnoj-ploshchadki-otc-tender.pdf>
  определяет OTC-TENDER, коммерческую секцию и OTC-Commerce+, а также работу Лицензиатов через
  ЭТП/Личный кабинет. Раздел 19 описывает OTC-CRM 2.0: задачи по опубликованным закупкам
  формируются по настройкам рассылок и истории участия Лицензиата на основе открытых источников.
  Это account UI functionality, а не внешний Collector discovery API/feed.
- Official customer manuals describe authenticated personal-account integration OTC с ЕИС для
  публикации/обмена customer notices, protocols and contracts. Такая organizer-side integration
  не является source-wide external discovery contract.
- Official documentation/search discovery не обнаружили опубликованные procurement API/WSDL/feed,
  endpoint/method/auth contract или machine schema для полного OTC discovery. Public HTML URLs и
  browser filters не превращаются в guessed JSON/XHR endpoints.

Использовались только official search discovery и обычное read-only изучение публичных
pages/PDF. Login, registration, cookies replay, form submission, document download, bulk
collection, browser/XHR reverse engineering, CAPTCHA/anti-bot bypass и guessed paths не
использовались. Procurement payload или document не сохранялся как fixture.

Public HTML не устанавливает permitted automated collection/reuse, exact platform/section/record
coverage, pagination/date-window completeness, stable field/status/document schema, version
lifecycle, update ordering, rate/concurrency/retry, timezone/currency/exact-money semantics или raw
response/document retention limits. EIS-numbered records на OTC search также нельзя повторно
выдавать за OTC-native verified records без explicit provenance and coverage contract.

## 4. Definition of Ready verdict

| Requirement | Result |
|---|---|
| Identity | PASS — canonical OTC identity остаётся отдельной |
| Public human search/detail | PARTIAL PASS — indexed HTML pages существуют |
| Official procurement discovery API/feed | BLOCKED |
| Permitted automated discovery and reuse | BLOCKED |
| Exact OTC/platform/section/record coverage | BLOCKED |
| Auth, request/response schema and version lifecycle | BLOCKED |
| Pagination/date windows/update/completeness | BLOCKED |
| Rate/concurrency/retry/`Retry-After` | BLOCKED |
| Timezone/currency/exact money mapping | BLOCKED |
| Stable identity/status/document mapping | BLOCKED |
| Approved fixtures | BLOCKED; intentionally not captured |
| Raw response/document retention and reuse | BLOCKED |
| Disable/rollback | PASS — existing disabled placeholder/settings owner |

Итог: `BLOCKED_EXTERNAL / PUBLIC_HTML_WITHOUT_MACHINE_CONTRACT`. Human search/card HTML, internal
browser requests, Личный кабинет, OTC-CRM и organizer-side EIS integration не реализуются как
Collector discovery adapter. `otc` остаётся disabled/not configured.

## 5. Unblock and rollback

АО «ОТС» должно опубликовать либо письменно подтвердить для Collector:

1. permitted source-wide procurement discovery API/feed и exact covered products/sections/records;
2. endpoint/method/auth, schema/version lifecycle and stable field/status/document mapping;
3. pagination/date-window, ordering, updates, snapshot and completeness rules;
4. rate, concurrency, retry/backoff and `Retry-After` behavior;
5. timezone, currency and exact monetary-value semantics;
6. automation, data reuse, raw response/document retention rights and limits;
7. relationship between OTC-native and EIS/other-platform records without identity conflation;
8. approved redacted positive/empty/page/error/auth/rate/schema-drift fixtures.

После unblock новый package начинает с amendment этого audit и fixture governance до tests/code.
Codex не входил в Личный кабинет, не отправлял формы и не связывался с Оператором. Rollback —
revert docs-only commit; identity/settings/credentials/DB/history и RM-107 decision неизменны.

## 6. Sequential boundary

Commercial sections федеральных операторов, P8/P9 и production RM-156 не начинаются параллельно.
После merge/exact следующий docs-only package может только принять OTC blocker и определить
auditable section matrix/order внутри existing provider owners. Новая provider identity или
неподтверждённый shared adapter не создаются.

## 7. Локальная валидация

- Focused Collector/provider contour: `34 passed in 14.76s`.
- Full baseline: `2467 passed, 2 warnings in 254.20s`; обе warnings — прежние
  `openpyxl`-предупреждения, новых warnings или зависимостей нет.
- `python -m ruff check .`, `python -m ruff format . --check` (`804 files already formatted`),
  `python -m mypy` (`20 source files`), `python scripts/check_repository_secrets.py` и
  `git diff --check` успешны.
- Pytest выполнялся с workflow-compatible `QT_QPA_PLATFORM=offscreen` и отдельным
  command-scoped `--basetemp`.

## 8. Publication acceptance

Ожидаются PR-head и exact merge-SHA Windows Quality Gate.
