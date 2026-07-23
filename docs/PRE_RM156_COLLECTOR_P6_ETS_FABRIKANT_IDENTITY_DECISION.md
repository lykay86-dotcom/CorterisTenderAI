# PRE-RM-156 Collector P6 — ETS/НЭП ↔ Fabrikant identity/section ownership audit

Дата: 23 июля 2026 года.

Статус: `ACCEPTED`.

## 1. Основание и inventory

Official evidence confirms one operator, АО «ЭТС», and the 1 February 2025 domain migration
`etp-ets.ru` → `44.fabrikant.ru`. The repository currently has separate canonical placeholders:

- `ets_nep`: federal P6 identity, legacy homepage, `44.fabrikant.ru` network contour;
- `fabrikant`: P7 commercial/general identity, `fabrikant.ru` contour;
- separate enum values, catalog entries, network settings, environment/keyring names and UI state;
- persisted provider IDs may exist in search profiles, run outcomes, artifacts/checkpoints,
  analytics/export and settings JSON.

No native adapter exists for either identity. Official material proves common operator/account
migration, but no public machine contract proves whether both contours share one schema/protocol or
require section-specific implementations.

ETS/НЭП audit was accepted as `BLOCKED_EXTERNAL / IDENTITY_REAUDIT_REQUIRED`: PR #136 head
`9765e7d6bc3c2ca59ac0647f565bf1aab12849ef`, PR-head run `29970355532` (jobs
`89090866063`/`89090866150`), merge `a3ac0d88759002468aa6a3d5cb5c6ba887ba9e26`, exact run
`29970713352` (jobs `89091950572`/`89091950535`), all successful.

## 2. Decision

1. Retain both canonical IDs as disabled section-scoped placeholders. Do not guess an alias or
   rewrite persisted identity without a proven protocol/section mapping.
2. Classify the relationship as `SAME_OPERATOR / SECTION_BOUNDARY_UNPROVEN`, not as two proven
   independent platforms and not yet as a safe legacy alias.
3. Future access work has one implementation owner for АО «ЭТС». It may expose section-specific
   provider views only if audited protocol/schema/authorization differences require them.
4. Before code, a contract package must prove exact host/section coverage and decide one of:
   canonical alias migration, shared adapter with section profiles, or audited distinct adapters.
5. Any alias/migration must inventory and preserve credentials, settings, search profiles, DB run
   outcomes, artifacts/checkpoints, exports and rollback. No such mutation occurs here.
6. `ets_nep` remains `BLOCKED_EXTERNAL`; `fabrikant` remains disabled and receives no readiness
   claim. After merge/exact, a separate docs-only order decision may move to `sber_a`.

This preserves the P5 exact-13 compatibility contract while preventing duplicate runtime business
logic. RM-107 score/recommendation/critical stop-factor priority is unchanged.

## 3. Scope and rollback

Docs-only. No application/tests, identity aliases, settings, credentials, endpoints, fixtures,
DB/schema/migrations or dependencies change. Rollback is revert of this decision; historical IDs
and data remain untouched.

## 4. Локальная валидация

- focused identity/factory/catalog contour: `33 passed in 11.64s`;
- neighboring crash-report/dashboard contour: `15 passed in 9.54s`;
- alphabetical prefix through `test_dashboard_background_refresh.py`, with the active workflow's
  `QT_QPA_PLATFORM=offscreen`: `965 passed in 98.58s`;
- final full suite with the same workflow environment: `2467 passed, 2 warnings in 230.78s`;
- Ruff: `All checks passed`; format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan and `git diff --check`: passed.

Every pytest command used a fresh command-scoped `--basetemp`. The first full local attempt, run
without `QT_QPA_PLATFORM`, ended in native Windows heap status `0xc0000374` near the background
refresh tests rather than a Python assertion. The exact neighboring contour passed, and the
problematic prefix plus full suite passed after matching the active Quality Gate's explicit
`offscreen` setting. No application/test/threshold change was made to mask the environment-specific
failure. Warnings are the unchanged `openpyxl` notices; dependencies did not change. PR-head and
exact merge-SHA Windows Quality Gate remain mandatory before this decision is accepted.

## 5. Publication acceptance

- PR #137 head `e3550871a95f0c103ee7f6e2799ccc120c1d2ba4`;
- PR-head Quality Gate `29971869854`: jobs `89095401781` (Python 3.12) и `89095401782`
  (Python 3.13) successful;
- merge commit `cd39b8e82d2ce208aa4498462c545f0fab894044`;
- exact merge-SHA Quality Gate `29972112388`: jobs `89096127682` (Python 3.12) и
  `89096127713` (Python 3.13) successful, including dependency audit.

Только после exact success создан отдельный docs-only worktree решения о переходе к `sber_a`.
