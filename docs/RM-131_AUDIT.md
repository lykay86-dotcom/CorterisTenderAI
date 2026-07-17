# RM-131 — аудит настроек площадок

Дата аудита: 17 июля 2026 года.
Baseline: `e76a6029f90b3511f361fece8ea7557f50e00495`.
Ветка: `feat/rm-131-provider-settings`.
Worktree: `C:\CorterisTenderAI_1_5_1\.worktrees\rm-131-provider-settings`.

## 1. Entry gate

Gate пройден до создания feature branch:

- `docs/STATUS.md` и `docs/ROADMAP.md` назначают RM-130 `DONE`, RM-131 — единственным
  `IN PROGRESS`, RM-132–RM-200 — `PLANNED`;
- `docs/ROADMAP_HISTORY.md` содержит feature merge RM-130
  `3a4d53067b7b0f8eaf0b5969c139284c9d5ed987`, успешный exact merge-SHA run
  `29534568925` и отдельный docs-only closeout;
- после `git fetch origin --prune` локальные `HEAD`, `main` и `origin/main` совпали на
  `e76a6029f90b3511f361fece8ea7557f50e00495`;
- post-closeout Quality Gate run `29535586550` имеет `success` на точном baseline для Windows
  Python 3.12 и 3.13;
- tracked основной checkout чист; пользовательские untracked `.agents/` и `skills-lock.json` не
  изменялись и в feature worktree не переносились;
- до начала работы не существовало local/remote ветки или открытого PR RM-131;
- RM-130 schema-v2 миграция завершена: profile хранит provider IDs, scheduler — собственные ссылки;
  массовая rewrite этих файлов RM-131 не требуется;
- read-only проверка default data directory обнаружила отсутствие `search_profiles.json`,
  `collector_schedule.json`, `collector_provider_settings.json` и
  `commercial_provider_settings.json`, поэтому незавершённого локального migration state нет.

Полностью прочитаны canonical roadmap/DoD/history, `docs/RM-126_AUDIT.md`,
`docs/RM-126_REQUIREMENTS.md`, RM-128/RM-129/RM-130 audit/plan, текущий Windows workflow и handoff
RM-131. Все обязательные historical points входят в baseline, включая `81db5bc` commercial catalog,
`27562ed` provider manager, `f09d07e` RM-126 audit, `a67f5df` RM-128 closeout, `f9b43c3` RM-129
feature merge, `9dd8e9c` RM-129 closeout и RM-130 feature/closeout commits.

## 2. Baseline evidence

Среда: Windows, Python `3.12.7`, `PYTHONUTF8=1`, `QT_QPA_PLATFORM=offscreen`, repository-local
ignored basetemp. Live network и credential reads не выполнялись.

- provider/UI/factory/session/scheduler/legacy contour: `41 passed in 9.41s`;
- full pytest: `1656 passed in 80.26s (0:01:20)`;
- exact post-closeout GitHub run `29535586550`: both matrix jobs and all workflow steps successful.

## 3. Current owners and construction sites

| Concern | Current owner/path | Consumers | Finding |
|---|---|---|---|
| General enablement | `ProviderEnablementRepository`, `collector_provider_settings.json`, schema v1 | manager and default factory | canonical path candidate; corrupt/future currently collapse to empty/default |
| Commercial non-secret settings | `CommercialProviderSettingsRepository`, `commercial_provider_settings.json`, schema v1 | manager-side commercial catalog | second settings owner; enablement duplicated |
| Effective commercial resolution | `CommercialProviderCatalog` | manager definitions/health and factory adapters | includes environment and keyring resolution; currently rebuilt independently |
| Manager façade | `CollectorProviderManager` | provider dialog, unified panel, Collector dialog, scheduler controller | correct application owner; keep and extend |
| Run composition | `CollectorRunSession` → `create_default_collector_service()` | every unified/dialog/scheduled run | creates commercial catalog without persisted commercial path |
| Health | `ProviderCheckRepository`, `collector_provider_health.json` | explicit manager health checks/UI | operational state, not settings; keep separate |
| C19 verification | `VerticalSourceVerificationRepository`, shared SQLite | UI status only | verified-working evidence, not settings; keep separate |
| Credentials | MOS config and `CommercialSecretResolver` over env/keyring | adapters and explicit credential dialog | RM-132 boundary; never persist/read for display in RM-131 |
| Legacy manual connections | `UserSettingsStore.platforms` + `ManualConnectorTester` | legacy settings page only | compatibility tester, not Collector catalog or production source |
| Profile references | `TenderSearchProfileRepository`, `search_profiles.json` schema v2 | legacy/unified search | preserve bytes; resolve aliases read-compatibly only |
| Schedule references | `CollectorScheduleRepository`, `collector_schedule.json` schema v1 | scheduler UI/controller | preserve bytes; validate/resolve against the same snapshot at use time |

Production construction search found:

- one default manager construction and one default session construction in
  `TenderSearchUiController`;
- one canonical `ProviderEnablementRepository` path in manager and the same path recreated by the
  collector service factory;
- one `CommercialProviderSettingsRepository` construction inside manager only;
- four manager-side `create_commercial_provider_catalog(settings_path=...)` calls;
- one factory fallback `create_commercial_provider_catalog()` with no settings path.

No third store, manager, catalog, provider factory, search engine, credential vault or health system is
needed.

## 4. Confirmed divergence

The UI and actual run do not consume one effective settings snapshot:

1. `CollectorProviderManager.states()` rebuilds a commercial catalog with
   `<data>/commercial_provider_settings.json` and the manager environment.
2. `CollectorRunSession.run()` builds a service without injecting manager state.
3. `create_default_collector_service()` creates only a general enablement repository.
4. `create_default_async_providers()` falls back to `create_commercial_provider_catalog()` without a
   persistence path.
5. Therefore persisted `access_confirmed` and `api_base_url` can be visible in manager UI but absent
   from the adapter used by the next Collector run.

`CollectorProviderManager.set_enabled()` also writes general enablement and then mirrors commercial
enablement into the second JSON. Failure between writes can leave contradictory values. Environment
enablement can make the commercial resolved object enabled while general enablement still filters the
adapter out. These are ownership bugs, not a reason for another façade.

## 5. Provider identity matrix

Canonical async/Collector identities remain descriptor IDs:

| Canonical ID | Source | Sync/legacy identity | Rule |
|---|---|---|---|
| `eis` | EIS | `eis` | same identity, different port |
| `mos_supplier` | MOS_SUPPLIER | none | canonical as-is |
| `b2b_center` | B2B_CENTER | `b2b_center` placeholder | same identity |
| `gazprombank` | GAZPROMBANK | `gazprombank` placeholder | same identity |
| `fabrikant` | FABRIKANT | none | canonical as-is |
| `tek_torg` | TEK_TORG | `tek_torg` placeholder | same identity |
| `otc` | OTC | none | canonical as-is |
| `sber_commercial` | SBER_A | `sber_a` placeholder | explicit alias `sber_a` |
| `rts_commercial` | RTS_TENDER | `rts_tender` placeholder | explicit alias `rts_tender` |
| `roseltorg_commercial` | ROSELTORG | `roseltorg` placeholder | explicit alias `roseltorg` |

Generic sync placeholder `commercial` has no one-to-one commercial source and must not be migrated or
enabled automatically. Aliases are accepted only at the resolution boundary for profile/schedule and
legacy settings compatibility. UI and resolved snapshots expose canonical IDs. RM-131 does not rewrite
`search_profiles.json` or `collector_schedule.json` merely to canonicalize a reference.

## 6. Chosen canonical settings contract

The existing `ProviderEnablementRepository` and path
`<data>/collector_provider_settings.json` become the one non-secret settings persistence boundary.
The class may gain a more precise public name only as an alias/compatibility surface; a second
repository class or file is not introduced.

Target schema v2 preserves the v1 top-level enablement map for old-reader compatibility and adds
configuration:

```json
{
  "schema_version": 2,
  "updated_at": "2026-07-17T00:00:00+00:00",
  "providers": {
    "eis": true,
    "b2b_center": false
  },
  "configuration": {
    "b2b_center": {
      "access_confirmed": false,
      "api_base_url": "https://api.example.test"
    }
  }
}
```

Allowed persisted fields are only:

- explicit enablement boolean;
- aware UTC `updated_at`;
- commercial `access_confirmed` boolean;
- normalized HTTP(S) `api_base_url` without user-info, query or fragment.

Forbidden values include API keys, tokens, passwords, usernames, environment variable values, masked
secret fragments, raw errors, response bodies, health state and C19 verification state.

## 7. Typed load and resolved snapshot

The existing settings domain gains immutable types:

- `ProviderSettingsLoadStatus`: `MISSING`, `CURRENT`, `MIGRATED_SPLIT_V1`, `CORRUPT`,
  `UNSUPPORTED_FUTURE`;
- frozen load result with source versions, warnings and backup/quarantine evidence;
- frozen provider configuration and catalog snapshot;
- explicit value origin such as default, persisted, legacy migrated or environment override;
- pure alias resolver and canonical descriptor catalog.

`load_result()` is no-network and no-secret. Missing/current/split-v1/corrupt/future are distinguishable.
Corrupt/future input is never silently replaced. Compatibility `load()/is_enabled()` can remain thin
wrappers where they do not weaken fail-closed mutation rules.

Environment remains runtime-only. A resolved snapshot may report that a field is overridden and
non-editable, but it must not expose the environment value as persisted state or read a credential for
display. The snapshot given to an adapter may contain runtime secret material only through the existing
credential boundary; public/display snapshots must be secret-free.

## 8. Split-v1 migration and rollback

Migration sources:

- general v1: `collector_provider_settings.json` with `providers: {id: bool}`;
- legacy commercial v1: `commercial_provider_settings.json` with
  `providers: {id: {enabled, access_confirmed, api_base_url}}`.

Deterministic precedence:

1. explicit general enablement for canonical ID or explicit alias;
2. legacy commercial `enabled` when general enablement is absent;
3. descriptor `enabled_by_default` when neither source has an explicit value;
4. environment affects only runtime resolution, never the migrated persisted value.

Configuration uses current canonical v2 when present, otherwise valid legacy commercial fields.
Conflicting canonical/alias or duplicated source values produce bounded warnings and deterministic
canonical precedence; unknown IDs are preserved only where safe and never promoted to a provider.

On first explicit mutation of split-v1 state:

1. capture exact bytes and revalidate both inputs under the repository lock;
2. create byte-for-byte sibling backups for every existing source;
3. build the complete schema-v2 payload in memory;
4. write a sibling temporary file and atomically replace the canonical target;
5. preserve the legacy commercial file for rollback/old-reader compatibility;
6. on any failure keep originals/backups and remove the temp;
7. subsequent load recognizes v2 and does not repeat migration.

Read alone does not destructively migrate. A missing canonical file plus valid commercial v1 is a
typed `MIGRATED_SPLIT_V1` in-memory result until explicit save/mutation.

## 9. Composition decision

`TenderSearchUiController` already owns one manager, one Collector session and one scheduler
controller. The target is repository/snapshot injection through these existing objects:

1. manager loads one canonical catalog snapshot;
2. provider manager dialog, unified panel, Collector dialog and scheduler dialog receive states
   derived from that snapshot;
3. controller validates aliases/selections against a fresh snapshot before starting a run;
4. one immutable resolved snapshot crosses `CollectorRunSession` into the existing factory;
5. factory creates EIS/MOS/commercial adapters from that snapshot without re-reading a divergent file;
6. composition/startup remains offline; network starts only inside explicit run or health action.

Repository-per-consumer recreation is acceptable only if path/schema/locking and snapshot identity are
proven equivalent. The preferred implementation injects one repository/catalog owner from manager to
session because the controller already owns both and this makes parity directly testable.

## 10. Existing UI adaptation

`TenderProviderManagerDialog` remains the only provider settings entry point. It may use a small
presentation-only child editor for known non-secret fields. Business rules, URL normalization,
migration, alias resolution, origin/editability and persistence stay outside QWidget.

Required behavior:

- enablement, status and known non-secret configuration reflect one snapshot;
- commercial sources can edit `access_confirmed` and normalized `api_base_url`;
- environment-overridden fields show origin and are read-only;
- EIS has no invented endpoint editor; MOS credentials keep the existing replacement-only keyring
  dialog and are not moved into provider settings;
- save refreshes provider manager, unified panel, Collector dialog and scheduler dialog;
- corrupt/future status is honest and mutations are blocked;
- legacy «Площадки API/RSS/FTP» is explicitly labelled compatibility/manual connection testing and
  links users to canonical Collector sources without importing or deleting entries.

## 11. Expected-red test boundary

Add seven new modules before production implementation:

- `test_rm131_provider_settings_schema.py` — strict schema/load statuses/URL/time/security;
- `test_rm131_provider_settings_migration.py` — split-v1 precedence, backups, rollback, idempotency;
- `test_rm131_provider_identity.py` — canonical descriptors, explicit aliases, collision guards;
- `test_rm131_provider_settings_composition.py` — one snapshot manager/session/factory/scheduler;
- `test_rm131_provider_settings_dialog.py` — existing dialog edit/origin/refresh contract;
- `test_rm131_legacy_platform_handoff.py` — compatibility/manual separation and no destructive import;
- `test_rm131_provider_settings_security.py` — no secrets/raw errors/unsafe endpoints/startup network.

Existing provider/factory/session/scheduler/UI tests remain regression owners. Expected red must fail
only for missing RM-131 symbols/behavior and is committed separately before production changes.

## 12. Risks and guards

| Risk | Required guard |
|---|---|
| enablement precedence changes | split-v1 fixtures for explicit/default/environment cases |
| alias selects wrong source | exhaustive explicit matrix and `commercial` rejection |
| partial migration loses input | two-source byte backups and replace-failure injection |
| UI/run divergence remains | identity/equality assertion on manager and service snapshot |
| stale scheduled reference runs silently | alias-aware current-snapshot validation before worker |
| secret reaches JSON/UI/export | adversarial secret values and byte/text scans |
| startup performs I/O | network tripwire for manager/controller/factory composition |
| commercial placeholder looks working | exact `NOT_CONFIGURED`/unverified behavior regression |
| health/C19 state is migrated as config | persistence-key allowlist tests |
| RM-130 files are rewritten | before/after byte equality for profile/schedule fixtures |

## 13. Non-scope and stop conditions

Non-scope: new credentials UI/vault, arbitrary manual provider registration, protocol choice, working
commercial connector implementation, health subsystem rewrite, C19 live verification, normalization,
dedup, search parallelism, scheduler monitoring semantics, lifecycle shutdown, DB/schema migrations,
score/recommendation/critical stop/AI and RM-132+.

Stop implementation if it requires a second settings file/repository/manager/catalog/factory/search
engine/health subsystem/credential vault, DB migration, mass rewrite of RM-130 profiles/schedules,
destructive legacy platform migration, startup live network or decision semantics change.

## 14. Audit decision

**ACCEPTED FOR DOCS-ONLY AUDIT COMMIT.** The confirmed defect is solvable inside existing owners by
upgrading `collector_provider_settings.json` to schema v2, migrating split v1 deterministically and
injecting one immutable resolved snapshot through the existing manager/session/factory/controller.
Production and test changes remain blocked until this audit and
`docs/RM-131_IMPLEMENTATION_PLAN.md` are committed separately, followed by expected-red evidence.

## 15. Expected-red evidence

After docs-only commit `243ab56`, seven RM-131 test modules were added without production changes and
run with the exact focused command from the implementation plan.

Exact result: expected collection failure, `7 errors in 4.49s`. Every error was limited to an absent
RM-131 public boundary:

- `ProviderConfiguration` and the typed provider-settings schema API;
- pure `app.tenders.collector.provider_definitions` identity module;
- legacy compatibility handoff constants in the existing tender workspace.

There was no application assertion failure, network call, Qt failure, Windows Temp error or unrelated
baseline regression. Ruff check passed and Ruff format reported all seven new files formatted.
Production implementation is unblocked by the audit/test ordering gate.

## 16. Feature acceptance evidence

Implementation is fixed in three scoped production/regression commits:

- `83f4c0a` — canonical descriptor identity, schema-v2 typed load, strict endpoint validation and
  deterministic split-v1 migration inside the existing repository;
- `b7398bd` — one immutable settings snapshot across manager/session/factory and existing provider,
  unified, Collector, scheduler and legacy handoff UI;
- `a27b44b` — corrupt/future pre-runtime blocking, conflict/alias/byte-preservation/security guards and
  public typed exports.

The existing owners remain singular: one `CollectorProviderManager`, one canonical
`<data>/collector_provider_settings.json`, one existing async factory/session, one provider manager
dialog and one scheduler/controller path. `commercial_provider_settings.json` is read only as split-v1
migration input and is never deleted or written by the manager. Health JSON, C19 SQLite verification,
keyring/environment credential boundaries and legacy `UserSettingsStore.platforms` remain separate.

Accepted behavior:

- schema v2 preserves the boolean `providers` map and adds only aware UTC `updated_at` plus strict
  non-secret `configuration`;
- missing/current/migrated/corrupt/future are typed; corrupt/future bytes are preserved and block UI
  mutation, factory construction and Collector runtime before network creation;
- first split-v1 mutation creates byte-exact timestamped backups of both existing sources, atomically
  replaces only the canonical file, cleans temp on failure and does not repeat migration;
- general enablement wins over legacy commercial enablement with a bounded conflict warning;
- only audited aliases map to canonical IDs; profile/schedule files remain byte-identical and generic
  `commercial` is rejected;
- environment overrides are runtime-only, visible as read-only origin and absent from persistence;
- public/display snapshot contains no credentials or masked secret fragments;
- persisted manager state is passed through `CollectorRunSession` to the existing factory, removing
  the former UI/run commercial settings divergence;
- save refreshes manager, unified panel, Collector dialog and scheduler dialog; legacy manual
  connection testing is explicitly marked compatibility and links to the canonical manager;
- EIS/MOS adapters, commercial honest-placeholder behavior, cancellation/partial collection,
  health/C19 state, RM-130 profile schema and deterministic decision/critical-stop semantics remain
  unchanged.

Exact local Windows/Python 3.12.7 results on 17 July 2026:

| Check | Exact result |
|---|---|
| Focused seven RM-131 modules | `30 passed in 4.37s` |
| Neighbor provider/UI/factory/session/scheduler/legacy contour | `76 passed in 12.01s` |
| Full pytest | `1686 passed in 63.19s (0:01:03)` |
| Repository secret scan | `Repository secret scan passed.` |
| Ruff check | `All checks passed!` |
| Ruff format | `562 files already formatted` |
| Mypy | `Success: no issues found in 20 source files` |
| Offline credential smoke | `2 passed in 4.58s` |
| Migration/schema smoke | `5 passed in 2.92s` |
| Public import smoke | `DashboardController` |
| Headless composition smoke | `1 passed in 0.18s` |
| Release/build smoke | `6 passed in 3.15s` |
| Dependency audit | `No known vulnerabilities found`; editable project skipped |
| Diff/status | `git diff --check` success; tracked worktree clean |

The first workflow-shaped pytest smoke attempt reached no application code and reported two setup
errors because global `%LOCALAPPDATA%\Temp\pytest-of-сooocorteris` is inaccessible (`WinError 5`).
The exact same tests passed with repository-local ignored basetemp as permitted by the handoff. The
first sandboxed dependency audit was blocked by cache/socket permissions (`WinError 10013`); the exact
command passed with approved external/cache access and no intervening code or dependency change.

**FEATURE IMPLEMENTATION READY FOR PR/CI.** RM-131 remains `IN PROGRESS`. It must not be marked
`DONE`, and RM-132 must not start, until the feature PR is merged, the exact merge-SHA Windows Quality
Gate succeeds on Python 3.12 and 3.13, and a separate docs-only closeout is merged.

## 17. Merge and exact-SHA closeout evidence

Feature PR #68 (`feat(rm-131): consolidate provider settings`) passed Quality Gate run
`29538903447` on feature HEAD `259685ef4ee00d73196b703b06a95c0717dfbff7`:

- Python 3.12 — `1686 passed in 90.24s`;
- Python 3.13 — `1686 passed in 101.46s`;
- both jobs passed secret scan, Ruff check/format (`562 files`), mypy (20 source files), all required
  offline/migration/import/composition/build smoke tests and dependency audit.

PR #68 was merged into `main` as `bbfd8e3b858a29f07d7b55fde5fdb5a80a1d9cf2`. Exact merge-SHA
Quality Gate run `29562019173` completed successfully:

- Python 3.12 — `1686 passed in 105.77s`;
- Python 3.13 — `1686 passed in 69.02s`;
- every required job and step completed with `success`; the official-actions Node.js 24 warning is
  non-blocking CI maintenance evidence and did not affect acceptance.

The merge contains only the audited RM-131 provider-settings scope. It does not introduce a second
settings owner, persist credentials, change DB/schema/migrations, health/C19 state,
normalization/ranking, deterministic score/recommendation, critical stop-factor priority or AI
contracts.

**ACCEPTED FOR DOCS-ONLY CLOSEOUT.** RM-131 satisfies the Definition of Done and may be marked
`DONE`; RM-132 becomes the sole `IN PROGRESS` stage while RM-133–RM-200 remain `PLANNED`.
