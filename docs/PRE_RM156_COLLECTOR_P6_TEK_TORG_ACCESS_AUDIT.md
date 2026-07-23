# PRE-RM-156 Collector P6 — TekTorg access audit

Дата: 23 июля 2026 года.

Статус: `LOCALLY AUDITED / BLOCKED_EXTERNAL`; publication и exact merge-SHA Quality Gate
ожидаются. Application implementation запрещена Definition of Ready.

## 1. Entry gate

- Baseline: docs-only order merge `22f5a530f6ca32ead5b76f102576fa36b559dac5`.
- PR #133 head `4dbd9b1cdfe3a233c97bab2d9f2c58171b3ee10d`; PR-head Quality Gate
  `29966420486` успешен: jobs `89078811152` (3.12), `89078810946` (3.13).
- Exact merge-SHA run `29966853365` успешен: jobs `89080134032` (3.12), `89080134075`
  (3.13), включая dependency audit.
- Scope — official read-only access/legal/contract audit. Adapter, fixture, endpoint settings,
  dependency, migration и live claim не добавляются.

## 2. Existing owners

`TenderSource.TEK_TORG`, canonical ID `tek_torg`, settings schema 7, network catalog and generic
credential compatibility already exist. The commercial catalog stores only homepage metadata and
the honest `commercial_access_pending` placeholder; `create_default_async_providers` contains no
native TekTorg provider. Existing keyring account name is `collector.tek_torg.api_key`; its value
was not read or changed. Future implementation must reuse shared runtime, page/checkpoint/artifact,
repository, settings and secret owners without a second catalog/factory.

## 3. Official evidence

- <https://www.tektorg.ru/> identifies АО «ТЭК-Торг» as the federal electronic trading platform
  and publishes public procedure pages for its sections.
- <https://api.tektorg.ru/> is an official unauthenticated JSON discovery document. It explicitly
  calls `/procedures` the public procedure-export section and `/lists` the public reference-data
  section; CORS is published for `GET`, `POST` and `OPTIONS`.
- <https://api.tektorg.ru/procedures> documents a SOAP export, publication/update date windows,
  section/procedure/organizer/customer filters, `limitPage`, `page` and sorting. Its advertised
  <https://api.tektorg.ru/procedures/wsdl> defines one `procedures` operation at
  `https://api.tektorg.ru/procedures/soap`, response totals/current page/total pages/page size, and
  procedure, lot, customer, classification and document fields.
- <https://api.tektorg.ru/lists/sections> and <https://api.tektorg.ru/lists/types> publish section
  and procedure-type dictionaries. They were inspected only as contract metadata; no tender
  payload was retained.
- The operator separately publishes a
  [SOAP integration regulation for external systems](https://www.tektorg.ru/storage/files/shares/%D0%94%D0%BE%D0%BA%D1%83%D0%BC%D0%B5%D0%BD%D1%82%D1%8B/223-%D0%A4%D0%97%20%D0%B8%20%D0%9A%D0%BE%D0%BC%D0%BC%D0%B5%D1%80%D1%87%D0%B5%D1%81%D0%BA%D0%B8%D0%B5%20%D0%B7%D0%B0%D0%BA%D1%83%D0%BF%D0%BA%D0%B8/SOAP.%20%D0%A0%D0%B5%D0%B3%D0%BB%D0%B0%D0%BC%D0%B5%D0%BD%D1%82%20%D0%B8%D0%BD%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D1%86%D0%B8%D0%BE%D0%BD%D0%BD%D0%BE%D0%B3%D0%BE%20%D0%B2%D0%B7%D0%B0%D0%B8%D0%BC%D0%BE%D0%B4%D0%B5%D0%B9%D1%81%D1%82%D0%B2%D0%B8%D1%8F%20v18.pdf).
  That authenticated customer integration uses a dedicated login/password token and user-scoped
  operations. It is not the same contract as the unauthenticated public procedure export and does
  not authorize reusing the existing generic `api_key` placeholder without an audited schema
  change.
- <https://www.tektorg.ru/robots.txt> allows page/name/OKPD query shapes and disallows other query
  strings and frame paths. It is indexing guidance, not a rate, reuse or retention licence.

The official public export is meaningful positive access evidence; it is not a guessed or hidden
endpoint. However, the published material does not define request-rate ceilings, retry or
`Retry-After` behavior, maximum page size, page-base/out-of-range behavior, snapshot consistency,
schema version/change notification, source-wide timezone/currency normalization, or permission and
limits for retaining/reusing raw responses and documents. The WSDL models money as `xsd:float`,
which is not by itself an approved exact-decimal contract. The discovery `hash` has no published
versioning semantics. No rate headers were present on the inspected discovery/WSDL responses.

Login, forms, private paths, credentials, CAPTCHA/anti-bot bypass, undocumented operations and bulk
collection were not exercised. No `procedures` SOAP data request was sent.

## 4. Definition of Ready verdict

| Requirement | Result |
|---|---|
| Identity | PASS |
| Permitted access method | PARTIAL PASS — official public export exists |
| Host/operation/request/response schema | PARTIAL PASS — discovery and WSDL exist, version policy absent |
| Pagination/date windows | PARTIAL PASS — fields/totals exist; bounds, maximum and consistency absent |
| Rate/retry/`Retry-After` | BLOCKED |
| Timezone/currency/exact money semantics | BLOCKED |
| Stable identity/status/document mapping | BLOCKED — fields exist, normalization contract incomplete |
| Approved real fixtures | BLOCKED; intentionally not captured |
| Raw response/document retention and reuse | BLOCKED |
| Disable/rollback | PASS — existing disabled settings owner |

Итог: `BLOCKED_EXTERNAL`. A public machine endpoint removes the endpoint-discovery blocker but does
not waive the remaining mandatory Definition of Ready fields. Parser/client, expected-red adapter
tests, fixture capture and live verification must not start with guessed limits or inferred rights.

## 5. Unblock and rollback

АО «ТЭК-Торг» должно опубликовать либо письменно подтвердить для Collector:

1. rate ceilings, concurrency, retry/backoff and `Retry-After` behavior;
2. maximum/default page size, page base, out-of-range and snapshot/completeness rules;
3. schema/version/change-notification policy and exact section coverage;
4. timezone, currency and exact monetary-value semantics;
5. permission and limits for raw response/document retention and reuse;
6. approved redacted positive/empty/page/error/rate/schema-drift fixtures and field mapping.

После unblock новый TekTorg package начинается с amendment этого audit и approved redaction до
tests/code. Официальный контакт площадки: `help@tektorg.ru`; Codex сообщений не отправлял.

Этот docs-only audit откатывается revert-коммитом; identity, credentials, settings, DB and
historical data не меняются. `tek_torg` остаётся disabled/not configured.

## 6. Локальная валидация

- focused identity/factory/catalog contour: `33 passed in 8.71s`;
- full suite: `2467 passed, 2 warnings in 240.61s`;
- Ruff: `All checks passed`; format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan и `git diff --check`: passed.

Tests used fresh command-scoped `--basetemp` paths because the host's old global pytest temp root
has a previously diagnosed ACL defect; repository files and test thresholds were not changed.
Warnings — неизменные `openpyxl` notices; dependencies не менялись. PR-head и exact merge-SHA
Windows Quality Gate обязательны до принятия audit package.
