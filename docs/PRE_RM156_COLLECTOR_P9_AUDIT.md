# PRE-RM-156 Collector P9 — stabilization audit and implementation gate

Дата: 23 июля 2026 года.

Статус: `ACCEPTED`; audit опубликован и принят fresh exact merge-SHA Quality Gate. Stabilization
implementation начата отдельным package; Collector closeout не начат.

## 1. Entry gate

- Baseline: accepted P8 closeout merge
  `f4fead191323f50c4b5d7a1359e24006c1a3bcb5`.
- P8 closeout PR #153 head `ead2de338628c5dd8b6ae7de19779ceec9dcc102`;
  PR-head run `29997803117` успешен: jobs `89175538704` (3.12), `89175538779` (3.13).
- Fresh exact run `29998310114` успешен: jobs `89177176148` (3.12),
  `89177176164` (3.13), включая full suite и dependency audit.
- P8 принят с TenderGuru
  `BLOCKED_EXTERNAL / ENTITLEMENT_AND_LICENSE_REQUIRED`; producer не создан.

## 2. Reused owners and existing evidence

| Boundary | Existing owner/evidence | P9 decision |
|---|---|---|
| 13 built-ins and aliases | `canonical_provider_definitions()`, `provider_identity.py` | reuse exact order; no second catalog |
| Runtime/factory/settings/credentials | existing async factory, provider manager, schema-7 settings, keyring/environment service | inspect only; no new owner |
| Offline reference samples | accepted EIS and Mos Supplier fixtures/parsers | compose one no-network diagnostic |
| Pagination/cancellation/checkpoints/artifacts | accepted P3/P4 contracts | rerun existing contours |
| Performance/resources | `benchmark_pre_rm156_collector_p3.py` | rerun unchanged 10k/25-cycle budgets |
| Migration/backup/restore | `CollectorSchemaMigrator` 15→16, verified backup and explicit restore | perform one isolated drill |
| Windows/full/build/frozen/dependency audit | `quality-gate.yml` | require PR-head and exact merge-SHA success |
| Provider access evidence | accepted P6/P7 audits | preserve honest external blockers |
| Aggregator isolation | accepted P8 access audit and queue hardening | rerun negative contour |

Existing migration contracts already cover old/current/future/corrupt inventory, verified backup,
explicit restore, source preservation and schema-16 identity aliases. Existing P3 benchmark already
measures exact 10,000 raw / 5,000 merged, nearest-rank p95, RSS, 25 cycles, task/thread/handle/temp
growth and cancellation ≤1 second. P9 does not create replacement migration, benchmark or health
owners.

## 3. Honest readiness inventory

No built-in currently qualifies as `WORKING`, because none has both accepted offline contract and
approved live verification evidence:

| Provider | P9 readiness | Evidence |
|---|---|---|
| `eis` | `BLOCKED_EXTERNAL / LIVE_VERIFICATION_NOT_APPROVED` | accepted `IMPLEMENTED_OFFLINE`; live canary not authorised |
| `mos_supplier` | `BLOCKED_EXTERNAL / CREDENTIAL_AND_LIVE_VERIFICATION_REQUIRED` | accepted `IMPLEMENTED_OFFLINE`; lawful token/live approval absent |
| `zakaz_rf` | `BLOCKED_EXTERNAL / MACHINE_CONTRACT_REQUIRED` | accepted P6 access audit |
| `roseltorg` | `BLOCKED_EXTERNAL / MACHINE_CONTRACT_REQUIRED` | accepted P6 access audit |
| `rad` | `BLOCKED_EXTERNAL / WRITTEN_AUTOMATION_PERMISSION_REQUIRED` | accepted P6 access audit |
| `tek_torg` | `BLOCKED_EXTERNAL / CONTRACT_FIXTURES_AND_RATE_RULES_REQUIRED` | accepted P6 access audit |
| `ets_nep` | `BLOCKED_EXTERNAL / IDENTITY_REAUDIT_REQUIRED` | accepted P6 access audit |
| `sber_a` | `BLOCKED_EXTERNAL / MACHINE_CONTRACT_REQUIRED` | accepted P6 access audit |
| `rts_tender` | `BLOCKED_EXTERNAL / MACHINE_CONTRACT_REQUIRED` | accepted P6 access audit |
| `gazprombank` | `BLOCKED_EXTERNAL / PUBLISHED_FEED_UNAVAILABLE` | accepted P6 access audit |
| `b2b_center` | `BLOCKED_EXTERNAL / CONTRACT_AND_PERMISSION_GATED` | accepted P7 access audit |
| `fabrikant` | `BLOCKED_EXTERNAL / PUBLISHED_API_SCOPE_MISMATCH` | accepted P7 access audit |
| `otc` | `BLOCKED_EXTERNAL / PUBLIC_HTML_WITHOUT_MACHINE_CONTRACT` | accepted P7 access audit |

`DISABLED` остаётся runtime user choice, а не способ скрыть access blocker. Ни hostname, ни token,
ни health HTTP response не переводят provider в `WORKING`.

## 4. Gaps and expected-red contract

Audit выявил два implementation gaps:

1. Нет единого no-network `checkall`/sample diagnostic, который:
   - проверяет exact 13 catalog/factory identities;
   - парсит approved EIS/Mos fixtures;
   - выводит bounded deterministic honest matrix;
   - выполняет isolated schema-15 backup/restore drill;
   - не читает credentials и не делает сеть.
2. Unexpected exception в `CollectorProviderManager._check_real()` формирует public/persisted
   health message из raw exception type/text. Это допускает утечку token/private URL при ошибке
   вне уже классифицированных transport boundaries.

Новый expected-red contour содержит шесть strict xfail contracts:

- exact 13/no-network report;
- honest matrix без ложного `WORKING`;
- two reference fixture samples;
- bounded deterministic secret-free JSON;
- migration/backup/restore drill;
- fixed safe unexpected-health error.

Implementation снимает markers только после прохождения всех шести assertions. Diagnostic
композирует existing owners; runtime catalog/readiness state machine и DB schema не меняются.

Локальная characterization:

- expected-red: `6 xfailed in 8.66s`;
- focused catalog/provider-control/schema/backup/prerequisite contour:
  `30 passed, 6 xfailed in 14.37s`;
- Ruff check и format check нового test file, repository secret scan и `git diff --check`
  успешны.

## 5. Planned package order

1. Этот audit/expected-red package: tests and docs only.
2. Отдельный stabilization implementation package:
   - `scripts/check_pre_rm156_collector_offline.py`;
   - minimal fixed-message health exception hardening;
   - tests marker removal;
   - operations/support/rollback documentation;
   - exact local performance/resource/migration/security/full evidence.
3. Feature PR, PR-head Windows 3.12/3.13 gate, merge, fresh exact merge-SHA gate.
4. Отдельный docs-only canonical Collector closeout только если общий Definition of Done выполнен
   и owner принимает documented external blockers.

До merge/exact audit package stabilization implementation не начинается. Production RM-156,
RM-157 и RM-158 не начинаются.

## 6. Rollback

Audit package откатывается одним tests/docs commit. Application, DB/schema, settings, credentials,
fixtures, provider readiness, RM-107 score/recommendation и critical stop-factor не изменяются.

## 7. Publication acceptance

- Commits: tests `1a588f6`, docs `3f9ae22`.
- PR #154 head `3f9ae22b86e04f25963f9c179b51b90b02818215`.
- PR-head run `29999339166` успешен: jobs `89180529149` (3.12),
  `89180529224` (3.13).
- Merge `8aa152f09043b3798040fb41482153a66269a35d`.
- Fresh exact run `29999808833` успешен: jobs `89182019589` (3.12),
  `89182019632` (3.13), включая dependency audit.
