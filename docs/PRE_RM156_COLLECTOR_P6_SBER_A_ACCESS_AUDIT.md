# PRE-RM-156 Collector P6 — Сбербанк-АСТ access audit

Дата: 23 июля 2026 года.

Статус: `LOCALLY AUDITED / BLOCKED_EXTERNAL`; publication и exact merge-SHA Quality Gate
ожидаются. Application implementation запрещена Definition of Ready.

## 1. Entry gate

- Baseline: docs-only order merge `7d1e728a99c384acd72d3b7b13ab274378fe7d47`.
- PR #138 head `1ddc2d726a6279ffb94023c89d6d90fc82e2347d`; PR-head Quality Gate
  `29972908601` успешен: jobs `89098549848` (3.12), `89098549930` (3.13).
- Exact merge-SHA run `29973164497` успешен: jobs `89099325527` (3.12), `89099325555`
  (3.13), включая dependency audit.
- Scope — official read-only access/legal/contract audit. Adapter, fixture, endpoint settings,
  dependency, migration и live claim не добавляются.

## 2. Existing owners

`TenderSource.SBER_A`, canonical ID `sber_a`, legacy alias `sber_commercial`, settings schema 7,
network catalog and credential compatibility already exist. The commercial catalog stores the
official homepage and credential compatibility metadata; default sync registry still creates an
honest `PlaceholderTenderProvider`. No native sync/async Сбербанк-АСТ adapter exists.

Current generic network metadata allows only `sberbank-ast.ru` and `www.sberbank-ast.ru`; it is
not an audited access contract and must not be treated as one. Existing keyring account name
`collector.sber_commercial.api_key` and environment variable
`CORTERIS_SBER_COMMERCIAL_API_KEY` were not read or changed. Future implementation must reuse
shared runtime, page/checkpoint/artifact, repository, settings and secret owners without a second
catalog/factory.

## 3. Official evidence

- <https://www.sberbank-ast.ru/> identifies АО «Сбербанк — Автоматизированная система торгов» as
  the operator and links separate official procurement contours.
- <https://www.sberbank-ast.ru/purchaseList.aspx> is the public human-facing 44-ФЗ procedure
  registry. It is a stateful ASP.NET page, not published API/feed documentation.
- <https://utp.sberbank-ast.ru/Trade/> is the official public 223-ФЗ/UТП landing page. It links
  procedure/lot and SME registries, regulations and authenticated participant workflows.
- <https://www.sberbank-ast.ru/Page.aspx?cid=2742> publishes operator regulations and identifies
  the 44-ФЗ registry. The currently listed documents describe platform/procedure operation; the
  page does not publish a Collector API/feed schema, authentication contract, pagination or rate
  policy.
- <https://www.sberbank-ast.ru/robots.txt> permits ordinary indexing by default but explicitly
  disallows `/Download.aspx?fid`, `/ViewDocument.aspx?id`, `/Download2.aspx?fid` and
  `/WebResource.axd`. Robots guidance is not permission for automated collection, data reuse or
  raw document retention.

Official pages were inspected with ordinary read-only `GET` requests. Login, registration,
postback search forms, private paths, credentials, CAPTCHA/anti-bot bypass, document download,
bulk collection and guessed API endpoints were not exercised. No procurement payload or document
was retained as a fixture.

The official site proves public human access to search/registry pages. The inspected official
materials do not publish a machine-readable procurement API/feed contract, permission for
automated collection and reuse, exact host/section coverage, stable request/response schema or
version lifecycle. They also do not define pagination/date-window completeness, request-rate and
retry behavior, timezone/currency/exact-money rules, document mapping, or raw response/document
retention limits. Public HTML and internal form/XML variable names are not promoted to an audited
machine contract.

## 4. Definition of Ready verdict

| Requirement | Result |
|---|---|
| Identity | PASS |
| Public human search/registry | PASS — official 44-ФЗ and 223-ФЗ pages exist |
| Permitted automated access and reuse | BLOCKED |
| Official API/feed and exact host/section coverage | BLOCKED |
| Request/response schema and version lifecycle | BLOCKED |
| Pagination/date windows/completeness | BLOCKED |
| Rate/retry/`Retry-After` | BLOCKED |
| Timezone/currency/exact money semantics | BLOCKED |
| Stable identity/status/document mapping | BLOCKED |
| Approved real fixtures | BLOCKED; intentionally not captured |
| Raw response/document retention and reuse | BLOCKED |
| Disable/rollback | PASS — existing disabled placeholder/settings owner |

Итог: `BLOCKED_EXTERNAL`. Public registry pages do not satisfy the mandatory machine-contract,
permission and fixture gates. Parser/client, expected-red adapter tests, fixture capture and live
verification must not start by replaying ASP.NET postbacks, scraping HTML or guessing endpoints.
`sber_a` remains disabled/not configured.

## 5. Unblock and rollback

АО «Сбербанк-АСТ» должно опубликовать либо письменно подтвердить для Collector:

1. permitted API/feed or stable machine-access method and exact 44-ФЗ/223-ФЗ section coverage;
2. automation, data reuse, raw response and document retention rights and limits;
3. authentication, request/response schema, version/change-notification and field mapping;
4. pagination/date-window, ordering, snapshot and source-wide completeness rules;
5. rate ceilings, concurrency, retry/backoff and `Retry-After` behavior;
6. timezone, currency, exact monetary-value and document semantics;
7. approved redacted positive/empty/page/error/auth/rate/schema-drift fixtures.

После unblock новый Сбербанк-АСТ package начинается с amendment этого audit и approved redaction
до tests/code. Официальные контакты, опубликованные оператором: `info@sberbank-ast.ru` и
`company@sberbank-ast.ru`; Codex сообщений не отправлял.

Этот docs-only audit откатывается revert-коммитом; identity, aliases, credentials, settings, DB and
historical data не меняются. RM-107 score/recommendation/critical stop-factor priority неизменны.

## 6. Локальная валидация

- focused identity/factory/catalog contour: `33 passed in 13.33s`;
- full suite: `2467 passed, 2 warnings in 272.93s`;
- Ruff: `All checks passed`; format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan и `git diff --check`: passed.

Pytest used the active workflow's `QT_QPA_PLATFORM=offscreen` and fresh command-scoped
`--basetemp`; repository files/tests/thresholds were not changed. Warnings — неизменные `openpyxl`
notices; dependencies не менялись. PR-head и exact merge-SHA Windows Quality Gate обязательны до
принятия audit package.
