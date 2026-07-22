# PRE-RM-156 Collector P6 — Roseltorg access audit

Дата: 23 июля 2026 года.

Статус: `BLOCKED_EXTERNAL`; application implementation запрещена Definition of Ready.

## 1. Entry gate

- Baseline: docs-only order merge `862dac27b38968f235f831402139980e17cc90f3`.
- PR #129 head `6df486b31d0953ae140be2c03939bab848b757b3`; PR-head run `29959486498`
  успешен: jobs `89056801850` (3.12), `89056801718` (3.13).
- Exact merge-SHA run `29959911671` успешен: jobs `89058199578` (3.12), `89058199554`
  (3.13), включая dependency audit.
- Scope — official read-only access/legal/contract audit. Adapter, fixture, endpoint, dependency,
  migration и live claim не добавляются.

## 2. Existing owners

`TenderSource.ROSELTORG`, canonical ID `roseltorg`, legacy alias `roseltorg_commercial`, settings
schema 7, network catalog and credential compatibility already exist. `create_default_async_providers`
contains no native Roseltorg provider; optional commercial access adapter remains honest
`NOT_CONFIGURED`. Future implementation must reuse shared runtime, page/checkpoint/artifact,
repository, settings and secret owners without a second catalog/factory.

## 3. Official evidence

- <https://www.roseltorg.ru/> identifies АО «ЕЭТП» as the operator.
- <https://www.roseltorg.ru/procedures/search> and `?page=1` return public UTF-8 HTML search pages.
- Public `/procedure/<id>` pages expose tender detail HTML and section/timezone labels.
- <https://www.roseltorg.ru/robots.txt> returns 200 and explicitly allows
  `/procedures/search?page=`; sitemap is published.
- The official documents page publishes section regulations and user manuals, but no procurement
  collection API/feed/schema/data-use contract was found.
- An API described for the separate electronic-document-management product is tariff-bound and
  concerns document operations, not procurement notice collection; it is out of scope.

Robots permission for indexing is not inferred as permission for systematic storage/reuse. No
forms, login, section-private paths, hidden endpoints or bulk collection were exercised.

## 4. Definition of Ready verdict

| Requirement | Result |
|---|---|
| Identity | PASS |
| Permitted procurement access/data use | BLOCKED |
| API/feed or explicitly permitted stable HTML contract | BLOCKED |
| Section hosts/schema/version | BLOCKED |
| Pagination/rate/timezone/currency | BLOCKED |
| Approved real fixtures | BLOCKED; intentionally not captured |
| Mapping/stable identity/documents | BLOCKED |
| Raw retention | BLOCKED |
| Disable/rollback | PASS — existing disabled settings owner |

Итог: `BLOCKED_EXTERNAL`. Public HTML and robots rules do not satisfy the full DoR. Parser/client,
expected-red adapter tests, fixture capture and live verification must not start.

## 5. Unblock and rollback

Владелец должен получить официальный contract или письменное разрешение оператора, закрывающее
отсутствующие DoR fields. Затем новый Roseltorg package начинается с audit amendment и approved
redaction до tests/code. Этот docs-only audit откатывается revert-коммитом; identities, aliases,
credentials, settings, DB и historical data не меняются.

## 6. Локальная валидация

- focused identity/factory/catalog contour: `18 passed in 13.24s`;
- full suite: `2467 passed, 2 warnings in 261.98s`;
- Ruff: `All checks passed`; format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan и `git diff --check`: passed.

Warnings — неизменные `openpyxl` notices; dependencies не менялись. PR-head и exact merge-SHA
Windows Quality Gate обязательны до принятия audit package.
