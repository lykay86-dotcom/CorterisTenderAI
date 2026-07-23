# PRE-RM-156 Collector P6 — ETS/НЭП access audit

Дата: 23 июля 2026 года.

Статус: `ACCEPTED / BLOCKED_EXTERNAL / IDENTITY_REAUDIT_REQUIRED`; application implementation
запрещена Definition of Ready.

## 1. Entry gate

- Baseline: docs-only order merge `195f4d2e22d12ca36e1c8329e241bef9c8f8832e`.
- PR #135 head `26e705f7c72d742dd0b4570cdd90084ae9f95c85`; PR-head run `29969146389`
  успешен: jobs `89087096040` (3.12), `89087095959` (3.13).
- Exact merge-SHA run `29969484418` успешен: jobs `89088142031` (3.12), `89088142008`
  (3.13), включая dependency audit.
- Scope — official read-only identity/access/legal/contract audit. Adapter, fixture, alias,
  endpoint settings, dependency, migration и live claim не добавляются.

## 2. Existing owners and identity conflict

Repository currently registers both canonical `ets_nep` and canonical `fabrikant`, with separate
commercial placeholders and generic credential accounts. `ets_nep` stores the legacy homepage
`https://www.etp-ets.ru/`; its network settings already include `44.fabrikant.ru`. No native async
provider exists for either placeholder.

Official current evidence proves these are not two independent operator platforms:

- АО «Электронные торговые системы» is the operator of Fabrikant at `fabrikant.ru` and
  `44.fabrikant.ru`;
- the official Fabrikant FAQ states that on 1 February 2025 `etp-ets.ru` changed to
  `44.fabrikant.ru` and describes migration/merging of the same organizations and user accounts;
- `https://www.etp-ets.ru/` now redirects to `https://44.fabrikant.ru/`;
- official pages use the combined historical name «НЭП-Фабрикант».

Therefore a separate `ets_nep` adapter would violate the no-duplicate identity/catalog/factory
owner contract. The existing P5 decision predates this audited migration evidence and must not be
silently overwritten inside an access package. A separate identity amendment must decide whether
`ets_nep` becomes an audited legacy alias/storage ID of `fabrikant`, and must inventory persisted
settings, credentials, outcomes, exports and UI selections before any migration.

## 3. Official access evidence

- <https://www.fabrikant.ru/about/company/IT/> identifies АО «ЭТС» and the current
  `fabrikant.ru`/`44.fabrikant.ru` operator contours.
- [Official account-migration FAQ](https://www.fabrikant.ru/faq?category-id=1594&element-id=138)
  records the `etp-ets.ru` → `44.fabrikant.ru` domain change from 1 February 2025.
- <https://www.fabrikant.ru/> publishes human search and public procedure cards; the official
  [new-search notice](https://www.fabrikant.ru/news/novyy-poisk-torgovykh-protsedur-na-etp-fabrikant-udobstvo-i-effektivnost-dlya-postavshchikov/)
  says the unified search includes 44-ФЗ procedures.
- The official [portal regulation](https://static.fabrikant.ru/files/public/inline/%D0%A0%D0%B5%D0%B3%D0%BB%D0%B0%D0%BC%D0%B5%D0%BD%D1%82.pdf)
  governs operator/client use and procurement participation, but does not publish a Collector
  API/feed, machine schema/version, rate policy or raw-retention licence.
- <https://www.fabrikant.ru/robots.txt> disallows file/download paths and explicit
  `xml_export_auctions` and `info_csv_export` actions, among many state-changing/private actions.
  Public card indexability does not establish permission to call those export actions.

No official public procurement API/feed documentation was found. Public HTML search/cards do not
define stable pagination/completeness, schema/version, rate/retry, timezone/currency normalization,
document download/retention, or data-reuse rules. Login, forms, private paths, credentials,
disallowed export actions, CAPTCHA/anti-bot bypass, hidden endpoints and bulk collection were not
exercised. No fixture was captured and no live adapter call was made.

## 4. Definition of Ready verdict

| Requirement | Result |
|---|---|
| Unique provider identity | BLOCKED — `ets_nep` and `fabrikant` are duplicate current operator identities |
| Permitted procurement automation/data use | BLOCKED |
| API/feed or explicitly permitted stable HTML contract | BLOCKED |
| Hosts/sections/schema/version | BLOCKED; current hosts known, machine contract absent |
| Pagination/rate/timezone/currency | BLOCKED |
| Approved real fixtures | BLOCKED; intentionally not captured |
| Stable identity/status/document mapping | BLOCKED |
| Raw retention/reuse | BLOCKED |
| Disable/rollback | PASS — both existing placeholders remain disabled |

Итог: `BLOCKED_EXTERNAL / IDENTITY_REAUDIT_REQUIRED`. Parser/client, expected-red adapter tests,
fixture capture and live verification must not start. The identity conflict is an additional
internal stop-line; it does not relax the external contract blockers.

## 5. Unblock and rollback

Before any provider code:

1. a separate audited identity package must reconcile `ets_nep` with `fabrikant`, including
   settings/credential/history/export compatibility and rollback;
2. АО «ЭТС» must publish or confirm a permitted procurement API/feed (or stable HTML contract),
   exact hosts/sections, schema/version and field mapping;
3. pagination/date-window/completeness, rate/retry, timezone/currency and document rules must be
   explicit;
4. raw response/document retention and reuse must be permitted;
5. approved redacted positive/empty/page/error/auth/rate/schema-drift fixtures are required.

Official support contact: `info@fabrikant.ru`; Codex сообщений не отправлял. This docs-only audit
rolls back by revert. It does not change identities, aliases, credentials, settings, DB or history.

## 6. Локальная валидация

- focused identity/factory/catalog contour: `33 passed in 8.84s`;
- full suite: `2467 passed, 2 warnings in 242.98s`;
- Ruff: `All checks passed`; format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan и `git diff --check`: passed.

Tests used fresh command-scoped `--basetemp`; the previous package's isolated native Windows/Qt
crash did not recur. Repository files/tests/thresholds were not changed. Warnings — неизменные
`openpyxl` notices; dependencies не менялись. PR-head и exact merge-SHA Windows Quality Gate
обязательны до принятия audit package.

## 7. Publication acceptance

- PR #136 head `9765e7d6bc3c2ca59ac0647f565bf1aab12849ef`;
- PR-head run `29970355532`: jobs `89090866063` (3.12), `89090866150` (3.13) successful;
- merge commit `a3ac0d88759002468aa6a3d5cb5c6ba887ba9e26`;
- exact run `29970713352`: jobs `89091950572` (3.12), `89091950535` (3.13) successful,
  including dependency audit.
