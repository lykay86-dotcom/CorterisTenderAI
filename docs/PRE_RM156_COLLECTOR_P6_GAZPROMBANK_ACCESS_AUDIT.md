# PRE-RM-156 Collector P6 — ЭТП ГПБ access audit

Дата: 23 июля 2026 года.

Статус: `ACCEPTED / BLOCKED_EXTERNAL / PUBLISHED_FEED_UNAVAILABLE`. Application implementation
запрещена Definition of Ready.

## 1. Entry gate

- Baseline: docs-only order merge `cb94e62df7cc7a815693e586b559184868d52e5a`.
- PR #142 head `8ad58579c5d9a54aec076741f891f95d06579c41`; PR-head Quality Gate
  `29976999580` успешен: jobs `89110806182` (3.12), `89110806185` (3.13).
- Exact merge-SHA run `29977374982` успешен: jobs `89111932002` (3.12), `89111932016`
  (3.13), включая dependency audit.
- Scope — official read-only access/legal/contract audit. Adapter, fixture, endpoint settings,
  dependency, migration и live claim не добавляются.

## 2. Existing owners

`TenderSource.GAZPROMBANK` и canonical ID `gazprombank` уже существуют. Commercial catalog хранит
официальную homepage `https://etpgpb.ru/`, settings schema 7, disabled readiness placeholder и
credential descriptor `collector.gazprombank.api_key` / `CORTERIS_GPB_API_KEY`. Default sync
registry также содержит inert canonical placeholder; native sync/async ЭТП ГПБ adapter отсутствует.

Generic network metadata разрешает только `etpgpb.ru` и `www.etpgpb.ru`. Оно не является
аудированным access contract; текущий официальный информационный сайт использует также
`new.etpgpb.ru`. Allowlist, credential value и keyring не читались и не менялись. Future
implementation обязана переиспользовать shared runtime, page/checkpoint/artifact, repository,
settings и secret owners без второго catalog/factory.

## 3. Official evidence

- <https://new.etpgpb.ru/about/> определяет ЭТП ГПБ как единую технологическую платформу для
  коммерческих, 223-ФЗ, 44-ФЗ и закрытых закупок и перечисляет отдельные продуктовые секции.
- <https://new.etpgpb.ru/procedures/> предоставляет public human search и procedure cards, но
  прямо предупреждает, что не все процедуры отображаются из-за предусмотренных законом
  ограничений раскрытия. Human search не заменяет machine contract.
- <https://new.etpgpb.ru/procedures/api/> прямо разрешает размещение списков торгов в сторонних
  сервисах и ПО, отдельно называет разработчиков и публикует RSS method. Инструкция предлагает
  добавлять `.rss` к адресу `procedures`, использовать filters и приводит точный адрес
  `https://etpgpb.ru/procedures.rss` для всех актуальных торгов.
- Ordinary read-only `GET` 23 июля 2026 года показал: выведенный из инструкции текущий адрес
  `https://new.etpgpb.ru/procedures.rss` отвечает `301` на опубликованный адрес, а
  `https://etpgpb.ru/procedures.rss` отвечает final `404` JSON `Page not found`.
- Current `robots.txt` с `Last-Modified: 22 Jul 2026` доступен, но для generic user-agent запрещает
  любой query URL (`/*?`), `/procedures/page` и document file types. RSS path не запрещён явно,
  однако опубликованный endpoint фактически недоступен; query/page scraping не используется как
  замена.
- <https://new.etpgpb.ru/products/market/portal/api/> описывает другой authenticated business API:
  заказчики управляют собственными ценовыми запросами/заказами, поставщики — своими catalog
  positions. Это не public procurement discovery/feed contract и не подменяет недоступный RSS.
- <https://new.etpgpb.ru/help/docs/> публикует регламенты и user manuals по секциям, но не
  Collector-ready feed schema/version/rate/completeness/retention contract.

Использовались только official search discovery и обычные read-only `GET`. Login, registration,
forms, credentials, CAPTCHA/anti-bot bypass, private paths, document download, bulk collection и
guessed endpoints не использовались. Procurement payload или document не сохранялись как fixture.

Положительное permission intent существенно: оператор явно адресует RSS стороннему ПО. Но
неработающий exact endpoint не даёт получить или проверить payload. Также не опубликованы feed
schema/version lifecycle, pagination/date-window/snapshot completeness, limits/retry behavior,
timezone/currency/exact-money semantics, stable status/identity/document mapping, raw payload and
document retention limits или approved fixtures.

## 4. Definition of Ready verdict

| Requirement | Result |
|---|---|
| Identity | PASS — canonical ЭТП ГПБ identity подтверждена |
| Public human search/cards | PASS, с явно ограниченной disclosure coverage |
| Permission for third-party software/RSS use | PARTIAL PASS — explicit intent опубликован |
| Current machine access | BLOCKED — published RSS redirects to final `404` |
| Exact section/host coverage | BLOCKED |
| Request/response schema and version lifecycle | BLOCKED |
| Pagination/date windows/snapshot completeness | BLOCKED |
| Rate/retry/`Retry-After` | BLOCKED |
| Timezone/currency/exact money semantics | BLOCKED |
| Stable identity/status/document mapping | BLOCKED |
| Approved real fixtures | BLOCKED; intentionally not captured |
| Raw response/document retention limits | BLOCKED |
| Disable/rollback | PASS — existing disabled placeholder/settings owner |

Итог: `BLOCKED_EXTERNAL / PUBLISHED_FEED_UNAVAILABLE`. Parser/client, expected-red adapter tests,
fixture capture и live verification не начинаются на `404`, human HTML, query/page scraping или
Trading Portal account API. `gazprombank` остаётся disabled/not configured.

## 5. Unblock and rollback

ООО ЭТП ГПБ должно восстановить опубликованный RSS либо опубликовать replacement contract и
подтвердить для Collector:

1. current machine endpoint, exact host and covered sections, включая disclosure exclusions;
2. response content type, schema, version lifecycle and stable field mapping;
3. pagination/date-window, ordering, update, snapshot and completeness rules;
4. rate ceilings, concurrency, retry/backoff and `Retry-After` behavior;
5. timezone, currency, exact monetary-value, status and document semantics;
6. raw response/document retention and reuse rights/limits;
7. approved redacted positive/empty/page/error/auth/rate/schema-drift fixtures.

После unblock новый ЭТП ГПБ package начинается с amendment этого audit и approved redaction до
tests/code. Официальный `tech@etpgpb.ru` опубликован для RSS configuration questions; Codex
сообщений не отправлял.

Этот docs-only audit откатывается revert-коммитом; identity, credential descriptor, settings, DB
и historical data не меняются. RM-107 score/recommendation/critical stop-factor priority
неизменны.

## 6. Phase boundary

Это последний source P6 в каноническом ТЗ. Audit package не открывает P7. Перед следующим source
нужно отдельное docs-only reconciliation/ordering decision от принятого exact baseline: canonical
ТЗ относит `gazprombank` к P6, тогда как старый implementation plan перечисляет его первым в P7.
До решения нельзя повторять ЭТП ГПБ, начинать `b2b_center` или объявлять P6/prerequisite closed.

## 7. Локальная валидация

- focused identity/factory/catalog contour: `34 passed in 17.26s`;
- full suite: `2467 passed, 2 warnings in 236.17s`;
- Ruff: `All checks passed`; format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan и `git diff --check`: passed.

Pytest использовал active workflow `QT_QPA_PLATFORM=offscreen` и fresh command-scoped
`--basetemp`; repository files/tests/thresholds не менялись. Warnings — неизменные `openpyxl`
notices; dependencies не менялись.

## 8. Publication acceptance

- PR #143 head `8dcfbf6469747fc3e8644761693cc85a076d1b39`;
- PR-head Quality Gate `29978156861`: jobs `89114212457` (Python 3.12) и `89114212487`
  (Python 3.13) успешны;
- merge commit `102aff662f3cd068c13c095cb6470912cc0bfc60`;
- exact merge-SHA Quality Gate `29978439856`: jobs `89115056696` (Python 3.12) и
  `89115056687` (Python 3.13) успешны, включая dependency audit.

Только после exact success создан отдельный docs-only P6/P7 boundary worktree.
