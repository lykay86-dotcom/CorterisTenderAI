# PRE-RM-156 Collector P6 — РТС-тендер access audit

Дата: 23 июля 2026 года.

Статус: `ACCEPTED / BLOCKED_EXTERNAL`. Application implementation запрещена Definition of Ready.

## 1. Entry gate

- Baseline: docs-only order merge `ffc2f4e8f8b3c0db502a4a26c2f8ea69b0a7931f`.
- PR #140 head `ca7a3c53841336d1cfe544ed5326b7d2160eef7f`; PR-head Quality Gate
  `29974875827` успешен: jobs `89104418590` (3.12), `89104418532` (3.13).
- Exact merge-SHA run `29975119548` успешен: jobs `89105143244` (3.12), `89105143234`
  (3.13), включая dependency audit.
- Scope — official read-only access/legal/contract audit. Adapter, fixture, endpoint settings,
  dependency, migration и live claim не добавляются.

## 2. Existing owners

`TenderSource.RTS_TENDER`, canonical ID `rts_tender`, legacy alias `rts_commercial`, settings
schema 7, network catalog and credential compatibility already exist. The commercial catalog
stores official homepage metadata; default registry keeps an honest placeholder and no native
sync/async РТС-тендер adapter exists.

Current generic network metadata allows only `rts-tender.ru` and `www.rts-tender.ru`; it is not an
audited access contract and does not cover section subdomains. Existing keyring account name
`collector.rts_commercial.api_key` and environment variable `CORTERIS_RTS_COMMERCIAL_API_KEY`
were not read or changed. Future implementation must reuse shared runtime, page/checkpoint/
artifact, repository, settings and secret owners without a second catalog/factory.

## 3. Official evidence

- <https://www.rts-tender.ru/> identifies ООО «РТС-тендер» in its official response and currently
  returns an Anti-DDoS browser-verification page to an ordinary read-only HTTP client.
- <https://www.rts-tender.ru/robots.txt> also returned `503 Service Temporarily Unavailable` with
  the same `noindex, nofollow` Anti-DDoS challenge rather than a robots policy. The challenge
  explicitly detects non-browser/automation clients. It was not solved or bypassed.
- Official section pages such as <https://www.rosatom.rts-tender.ru/> expose human-facing public
  tender cards that are indexed by search engines. Section-specific public HTML is not published
  machine API/feed documentation and does not establish source-wide coverage.
- Official B2B-Center material identifies B2B-РТС as a group/platform combining the distinct
  `РТС-тендер`, `B2B-Center` and `OTC` businesses. This proves common group ownership, not a shared
  provider identity, schema, protocol or permission contract. Canonical IDs remain separate and
  no alias/shared adapter is guessed.
- Official search and documentation discovery found training/demonstration systems and human
  regulations, but no public Collector-ready procurement API/feed contract.

Only ordinary read-only `GET` and search discovery were used. Login, registration, browser
challenge solving, cookies replay, JavaScript execution, private paths, credentials, CAPTCHA/
anti-bot bypass, form submission, document download, bulk collection and guessed endpoints were
not exercised. No procurement payload or document was retained as a fixture.

The inspected official materials do not publish permission for automated collection/reuse, exact
section/host coverage, authentication, request/response schema, version lifecycle, pagination/
date-window completeness, request-rate/retry behavior, timezone/currency/exact-money rules,
document mapping, or raw response/document retention limits. Search-indexed human HTML and internal
browser challenge mechanics are not promoted to a machine contract.

## 4. Definition of Ready verdict

| Requirement | Result |
|---|---|
| Identity | PASS — canonical RTS identity remains distinct |
| Public human section cards | PARTIAL PASS — section-specific indexed HTML exists |
| Permitted automated access and reuse | BLOCKED |
| Ordinary client access | BLOCKED — official Anti-DDoS challenge, no bypass permitted |
| Official API/feed and exact host/section coverage | BLOCKED |
| Request/response schema and version lifecycle | BLOCKED |
| Pagination/date windows/completeness | BLOCKED |
| Rate/retry/`Retry-After` | BLOCKED |
| Timezone/currency/exact money semantics | BLOCKED |
| Stable identity/status/document mapping | BLOCKED |
| Approved real fixtures | BLOCKED; intentionally not captured |
| Raw response/document retention and reuse | BLOCKED |
| Disable/rollback | PASS — existing disabled placeholder/settings owner |

Итог: `BLOCKED_EXTERNAL`. Parser/client, expected-red adapter tests, fixture capture and live
verification must not start by bypassing Anti-DDoS, scraping indexed section HTML or guessing a
shared B2B-РТС protocol. `rts_tender` remains disabled/not configured.

## 5. Unblock and rollback

ООО «РТС-тендер» должно опубликовать либо письменно подтвердить для Collector:

1. permitted non-browser API/feed or stable machine-access method and exact section coverage;
2. automation, data reuse, raw response and document retention rights and limits;
3. authentication/challenge exemption, request/response schema, version policy and field mapping;
4. pagination/date-window, ordering, snapshot and source-wide completeness rules;
5. rate ceilings, concurrency, retry/backoff and `Retry-After` behavior;
6. timezone, currency, exact monetary-value and document semantics;
7. whether any B2B-Center/OTC protocol component is shared, without merging canonical identities;
8. approved redacted positive/empty/page/error/auth/rate/schema-drift fixtures.

После unblock новый РТС-тендер package начинается с amendment этого audit и approved redaction до
tests/code. Официальный support channel доступен через operator website; Codex сообщений не
отправлял.

Этот docs-only audit откатывается revert-коммитом; identities, aliases, credentials, settings, DB
and historical data не меняются. RM-107 score/recommendation/critical stop-factor priority
неизменны.

## 6. Локальная валидация

- focused identity/factory/catalog contour: `33 passed in 13.89s`;
- full suite: `2467 passed, 2 warnings in 252.61s`;
- Ruff: `All checks passed`; format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan и `git diff --check`: passed.

Pytest used the active workflow's `QT_QPA_PLATFORM=offscreen` and fresh command-scoped
`--basetemp`; repository files/tests/thresholds were not changed. Warnings — неизменные `openpyxl`
notices; dependencies не менялись.

## 7. Publication acceptance

- PR #141 head `00c0e6900e8d3390f8858d1fbdf9193695684ccf`;
- PR-head Quality Gate `29975868619`: jobs `89107358104` (Python 3.12) и `89107358117`
  (Python 3.13) успешны;
- merge commit `3944dbd0ec35bc358d5149a9cf005b27884b6570`;
- exact merge-SHA Quality Gate `29976202290`: jobs `89108357449` (Python 3.12) и
  `89108357536` (Python 3.13) успешны, включая dependency audit.

Только после exact success создан отдельный docs-only worktree решения о следующем P6 target.
