# PRE-RM-156 Collector — implementation plan

Дата: 22 июля 2026 года.

Baseline: `c20bed32492dc80b48748c79a87da73107533ddd`.

Нормативный contract:
[`PRE_RM156_COLLECTOR_CONTRACT.md`](PRE_RM156_COLLECTOR_CONTRACT.md).

Rollback:
[`PRE_RM156_COLLECTOR_ROLLBACK_PLAN.md`](PRE_RM156_COLLECTOR_ROLLBACK_PLAN.md).

Работы выполняются строго последовательно. Каждый package получает отдельную ветку/worktree/PR и
merge-SHA Quality Gate. Следующий package начинается от свежего `origin/main` только после merge и
успешного exact merge-SHA run предыдущего. Provider work packages не выполняются параллельно.

## 1. Общие правила каждого package

1. Проверить canonical `STATUS`, `ROADMAP`, `DEFINITION_OF_DONE`, `ROADMAP_HISTORY` и clean
   `origin/main`.
2. Создать отдельный `codex/pre-rm156-collector-<package>` worktree.
3. До application edits зафиксировать scope, consumers, schema/settings impact и rollback.
4. Сначала characterization/expected-red, затем минимальная implementation.
5. Не создавать нового production owner и не расширять scope следующим package.
6. Использовать только real redacted fixtures с provenance; synthetic fixture не доказывает
   provider contract.
7. Live diagnostics explicit opt-in и не входят в pytest/CI.
8. Выполнить focused, mandatory offline, migration, bootstrap, build/frozen, RM-155 guard, full
   pytest, Ruff, format, mypy, secret scan и pip-audit.
9. Записать точные commit/PR/run IDs; после merge проверить exact merge SHA.
10. Rollback не удаляет user data, settings, decisions, artifacts или audit evidence.

## 2. P2 — expected-red correctness contracts

Ветка: `codex/pre-rm156-collector-correctness-contracts`.

Scope: только tests/fixtures/test documentation; production `app/` не изменяется.

Добавить tests из contract section 15:

- all-page consumption и cursor cycle;
- cancellation between pages;
- atomic checkpoint/page commit и replay;
- zero-success/timeout terminal status;
- discovery-before-normalize на multi-page path;
- completion-order determinism;
- duplicate identity rejection;
- artifact/page commit coupling;
- full error/secret redaction;
- migration old/current/future/corrupt/backup/restore;
- overlapping run admission.

Так как отдельный P2 PR обязан быть зелёным, отсутствующие boundaries фиксируются
`pytest.mark.xfail(strict=True, reason="PRE-RM156 expected-red: <contract-id>")`. Перед marker
проверяется, что тест действительно падает по ожидаемой причине, а не на setup/import. P3/P4
удаляют каждый marker в том же commit, который реализует boundary; неожиданный XPASS остаётся
failure. P2 merge evidence перечисляет число `xfailed` и exact reasons.

Exit: application diff пуст; все expected-red tests fail for intended assertion under direct
unmarked run; regular suite green with strict xfail; exact merge-SHA Quality Gate success.

## 3. P3 — shared page/artifact/checkpoint foundation

Ветка: `codex/pre-rm156-collector-page-foundation`.

Основные изменения:

- backward-compatible page extension в `async_provider.py`;
- page loop в существующем `AsyncProviderSearchEngine`;
- typed query fingerprint/resume/checkpoint models;
- accepted-page repository transaction в `CollectorStateRepository`;
- content-addressed raw artifact store + metadata в существующей DB;
- run terminal truth table, включая `TIMED_OUT`;
- cancellation checks и bounded budgets;
- process-wide run lease только если P2 докажет необходимость;
- progress/page/artifact/counter projection через existing progress/monitoring owners.

Schema change допускается только как version 15 с explicit 14→15 migration, inventory/dry-run,
backup/readback/restore tests. Нельзя переносить existing tables в новую DB. Existing one-page
fake/legacy providers продолжают работать через default adapter.

Acceptance:

- снять соответствующие strict xfail markers P2;
- exact-data 10k same-host p95 ≤ 10,000 ms, regression ≤ 20%, RSS delta ≤ 64 MiB;
- interactive/scheduled budgets enforced;
- 25-cycle resource soak, cancellation ≤ 1 second offline;
- migration/backup/restore и full quality gates green.

## 4. P4 — reference adapters repair

Ветка/PR 1: `codex/pre-rm156-collector-eis-reference`.

Ветка/PR 2 после merge: `codex/pre-rm156-collector-mos-reference`.

### EIS

- оформить provider package/contract/parser versions без копирования shared utilities;
- перейти на shared page contract и bounded public HTML pagination;
- checkpoint только после accepted page commit;
- raw search/detail/document-page artifacts с provenance/retention;
- CAPTCHA/access-denied/login/structure drift fail closed;
- сохранить truthful `public_html` connection mode;
- real redacted fixtures и optional live diagnostic.

### Mos Supplier

- подтвердить documented server pagination либо честно ограничить adapter до доказанного scope;
- bearer secret только environment/keyring;
- shared page/artifact/checkpoint foundation;
- auth/contract/parse response classification;
- real redacted fixtures и optional live diagnostic;
- отсутствие token = `BLOCKED_EXTERNAL`/`NOT_CONFIGURED`, не network attempt.

Exit каждого PR: общий provider contract, mapping/provenance/documents/health, disable/rollback и
exact merge-SHA gate. Только после этого provider может пройти readiness выше
`IMPLEMENTED_OFFLINE`.

## 5. P5 — identity/catalog expansion

Ветка: `codex/pre-rm156-collector-provider-identity`.

- добавить `zakaz_rf`, `rad`, `ets_nep` в versioned domain/schema path;
- сделать `sber_a`, `rts_tender`, `roseltorg` canonical;
- направить `_commercial` legacy IDs в canonical IDs;
- сохранить unknown/ambiguous legacy values без silent reassignment;
- унифицировать factory/catalog/settings/UI/export/import identity;
- мигрировать settings и DB references с backup/readback;
- legacy sync catalog либо делегирует canonical read model, либо остаётся frozen compatibility
  projection с явным retirement evidence;
- все 13 built-ins отображаются с truthful readiness; отсутствующий adapter не runnable.

Exit: uniqueness/collision/migration tests во всех composition paths, старые profiles/settings/run
history читаются, secrets/data не потеряны.

## 6. P6 — federal/operator adapters

Каждая площадка — отдельный последовательный worktree/PR после собственного Definition of Ready:

1. `zakaz_rf`;
2. `roseltorg`;
3. `rad`;
4. `tek_torg`;
5. `ets_nep`;
6. `sber_a`;
7. `rts_tender`;
8. `gazprombank`.

До implementation в `docs/providers/<provider_id>.md` фиксируются identity, lawful access,
official documentation, endpoint/method/auth, rate/terms, fixtures provenance, pagination/cursor/
date-window, timezone, fields/documents, health/error mapping, contract/parser version и rollback.
Если access evidence отсутствует, PR ограничивается honest `BLOCKED_EXTERNAL` metadata/tests; network
scraping, registration, CAPTCHA/WAF bypass и guessed endpoint запрещены.

## 7. P7 — commercial adapters

Отдельно и последовательно:

1. `b2b_center`;
2. `fabrikant`;
3. `otc`;
4. commercial sections федеральных операторов внутри их existing owner.

Порядок может измениться только canonical docs решением владельца на основании доступного lawful
contract/API evidence. Commercial placeholder не заменяется network code до DoR. Любой provider
без договора/ключа/документации остаётся `BLOCKED_EXTERNAL`; общая foundation при этом может быть
закрыта.

## 8. P8 — aggregator discovery

Ветка: `codex/pre-rm156-collector-discovery-gate`.

- перевести discovery producers на общий page/artifact contract;
- доказать gate до normalization/dedup на final и progress snapshots;
- official verification повторно получает data только через official provider;
- aggregator values не становятся field candidates official record;
- queue/retry/manual review/attempt history bounded и sanitized;
- readiness остаётся отдельной от 13 built-ins.

## 9. P9 — stabilization и prerequisite closeout

Feature stabilization branch:

- all-provider offline check/sample diagnostics;
- settings/DB migration, backup/restore и downgrade-read evidence;
- deterministic multi-provider order/partial/failed/timeout/cancel contours;
- 10k performance и 25-cycle resource evidence;
- security/legal negative tests;
- Windows Python 3.12/3.13 full gates, build/frozen/offline diagnostics;
- operations/support/provider docs и rollback drill.

После feature merge и exact merge-SHA success создаётся отдельный docs-only closeout от fresh
`origin/main`. Closeout отмечает prerequisite завершённым только по общему Definition of Done,
записывает все external blockers и возвращает RM-156 к production-модели контрагента. RM-157 и
RM-158 до этого не начинаются.

## 10. Commit discipline

Минимальный порядок внутри implementation PR:

1. `test(pre-rm156): characterize <boundary>`;
2. `test(pre-rm156): define <contract-id>` (если не пришёл из P2);
3. `feat/fix(pre-rm156): implement <bounded scope>`;
4. `docs(pre-rm156): record <package> acceptance`.

Schema migration, provider implementation и unrelated cleanup не смешиваются. Reformat-only diff
не включается. Каждый снятый xfail указывает implementation commit и contract ID.
