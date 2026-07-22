# PRE-RM-156 Collector P6 — Rad access audit

Дата: 23 июля 2026 года.

Статус: `ACCEPTED / BLOCKED_EXTERNAL`; application implementation запрещена Definition of Ready.

## 1. Entry gate

- Baseline: docs-only order merge `4e5adfec20d7ad95ac2fe4decd005b0041e60909`.
- PR #131 head `c4df48df5bfbc4fc1d2dc55a8fedd5fd6ff66803`; PR-head run `29963756719`
  успешен: jobs `89070568520` (3.12), `89070568448` (3.13).
- Exact merge-SHA run `29964235838` успешен: jobs `89072056995` (3.12), `89072057051`
  (3.13), включая dependency audit.
- Scope — official read-only access/legal/contract audit. Adapter, fixture, endpoint, dependency,
  migration и live claim не добавляются.

## 2. Existing owners

`TenderSource.RAD`, canonical ID `rad`, settings schema 7, network catalog and generic credential
compatibility already exist. The commercial catalog stores only homepage metadata and the honest
`commercial_access_pending` placeholder; `create_default_async_providers` contains no native Rad
provider. Existing keyring account name is `collector.rad.api_key`; its value was not read or
changed. Future implementation must reuse shared runtime, page/checkpoint/artifact, repository,
settings and secret owners without a second catalog/factory.

## 3. Official evidence

- <https://auction-house.ru/about/> identifies АО «Российский аукционный дом» as the operator of
  the federal Lot-online platform and links the procurement sections.
- <https://gz.lot-online.ru/documentation> publishes 44-ФЗ/615 regulations, user agreement and
  user manuals; <https://tender.lot-online.ru/> publishes the 223-ФЗ section and public cards.
- The operator's [user agreement approved 26 August 2025](https://catalog.lot-online.ru/images/docs/%D0%9F%D0%BE%D0%BB%D1%8C%D0%B7%D0%BE%D0%B2%D0%B0%D1%82%D0%B5%D0%BB%D1%8C%D1%81%D0%BA%D0%BE%D0%B5%20%D1%81%D0%BE%D0%B3%D0%BB%D0%B0%D1%88%D0%B5%D0%BD%D0%B8%D0%B5%20%D0%BE%D1%82%2026.08.2025.pdf)
  applies to `https://lot-online.ru` and covers procurement information. It prohibits automatic
  programs used to access the site for extracting, collecting, processing, copying or
  distributing site/database information.
- The same agreement separately requires written operator permission before scripts may access,
  collect information from, or interact with the site and its services.
- The public 223-ФЗ footer also states that any use of site materials requires written consent.
- No public procurement collection API/feed, machine schema/versioning, rate contract or written
  Collector permission was found. The hostname `api1.lot-online.ru` serves human website content
  and is not evidence of an API contract.

Multiple official contours exist (`gz`, `tender`, `catalog` and other section subdomains). Public
indexing and public tender cards do not override the explicit automation restriction. Login,
forms, private paths, hidden endpoints, credentials, CAPTCHA/anti-bot bypass and bulk collection
were not exercised.

## 4. Definition of Ready verdict

| Requirement | Result |
|---|---|
| Identity | PASS |
| Permitted procurement automation/data use | BLOCKED — written permission required |
| API/feed or explicitly permitted stable HTML contract | BLOCKED |
| Section hosts/schema/version | BLOCKED |
| Pagination/rate/timezone/currency | BLOCKED |
| Approved real fixtures | BLOCKED; intentionally not captured |
| Mapping/stable identity/documents | BLOCKED |
| Raw retention permission | BLOCKED |
| Disable/rollback | PASS — existing disabled settings owner |

Итог: `BLOCKED_EXTERNAL`. The explicit no-automation-without-written-permission condition is a
critical stop-line. Parser/client, expected-red adapter tests, fixture capture and live
verification must not start.

## 5. Unblock and rollback

Владелец должен получить отдельное письменное разрешение АО «РАД» либо официальный procurement
API/feed contract, который явно разрешает automation, collection and raw retention and closes all
remaining DoR fields. Затем новый Rad package начинается с audit amendment и approved redaction
до tests/code. Этот docs-only audit откатывается revert-коммитом; identity, credentials, settings,
DB и historical data не меняются.

## 6. Локальная валидация

- focused identity/factory/catalog contour: `15 passed in 8.58s`;
- full suite: `2467 passed, 2 warnings in 322.08s`;
- Ruff: `All checks passed`; format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan и `git diff --check`: passed.

Tests used fresh command-scoped `--basetemp` paths because the host's old global pytest temp root
has a previously diagnosed ACL defect; repository files and test thresholds were not changed.
Warnings — неизменные `openpyxl` notices; dependencies не менялись. PR-head и exact merge-SHA
Windows Quality Gate обязательны до принятия audit package.

## 7. Publication acceptance

- PR #132 head `6ca84f2f523dce6f853cfb919420d6e36caca06e`;
- PR-head Quality Gate `29965371309`: jobs `89075592391` (Python 3.12) и `89075592367`
  (Python 3.13) успешны;
- merge commit `38fe2d75f80beb544e9b5a7a2d18462963c4f232`;
- exact merge-SHA Quality Gate `29965734080`: jobs `89076696779` (Python 3.12) и
  `89076696809` (Python 3.13) успешны, включая dependency audit.

Только после exact success создан отдельный docs-only worktree решения о следующем P6
access-audit target. `BLOCKED_EXTERNAL` и written-permission requirement сохраняются без
ослабления.
