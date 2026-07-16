# RM-131 — implementation plan настроек площадок

Дата: 17 июля 2026 года.
Baseline: `e76a6029f90b3511f361fece8ea7557f50e00495`.
Ветка: `feat/rm-131-provider-settings`.

План основан на `docs/RM-131_AUDIT.md`, D-03/D-04/D-05 из
`docs/RM-126_REQUIREMENTS.md`, завершённых RM-128–RM-130 и canonical Definition of Done. Scope
RM-132+ не включён.

## 1. Mandatory order

1. Commit audit, this plan and roadmap evidence as docs-only.
2. Add seven ownership-focused expected-red modules without production changes.
3. Run the exact red contour; accept only missing RM-131 symbols/behavior.
4. Record exact failure evidence and commit tests separately.
5. Implement pure schema/load/migration/identity/snapshot domain.
6. Adapt the existing repository and manager façade.
7. Pass one snapshot through existing session/factory composition.
8. Adapt the existing dialog/controller/legacy handoff.
9. Run focused, neighbor and full workflow-equivalent gates and record exact evidence.
10. Feature PR → merge → exact merge-SHA Windows gate → separate docs-only closeout.

## 2. Pure settings domain

Prefer extending `app/tenders/collector/provider_settings.py`; add a pure
`provider_definitions.py` only if tests prove definitions cannot be shared without importing
persistence/network/credentials.

Add:

- schema v2 constants and persisted key allowlist;
- immutable per-provider non-secret configuration;
- `ProviderSettingsLoadStatus` and frozen load result;
- immutable catalog/effective snapshot and explicit value-origin enum;
- canonical provider identity and explicit alias resolver;
- strict HTTP(S) endpoint parser without user-info/query/fragment;
- pure v1-general + v1-commercial → v2 migration.

No Qt, SQLite, network, health, keyring or adapter construction belongs in the pure domain.

## 3. Existing repository migration

Upgrade `ProviderEnablementRepository` in place:

- retain public compatibility methods where safe;
- make `<data>/collector_provider_settings.json` schema v2 canonical;
- preserve top-level `providers` boolean map;
- add `updated_at` and `configuration`;
- expose typed `load_result()` and fail-closed mutations;
- strict-decode known fields/types, duplicate/casefold collisions and aware timestamp;
- never overwrite corrupt/future input;
- read split v1 in memory without write;
- on first explicit mutation, back up every existing source byte-for-byte and atomically replace only
  the canonical target;
- preserve `commercial_provider_settings.json` for rollback/old-reader compatibility;
- clean temp on failure and do not repeat migration after v2 is present.

The legacy `CommercialProviderSettingsRepository` becomes read-compatibility/migration input only.
Do not add another storage owner.

## 4. Catalog and alias identity

Build one deterministic ordered descriptor catalog from existing definitions:

- EIS and MOS descriptors;
- eight existing commercial definitions;
- uniqueness by canonical ID and source/alias rules;
- aliases only `sber_a`, `rts_tender`, `roseltorg` to their explicit commercial canonical IDs;
- same-ID sync placeholders remain compatible;
- generic `commercial` is rejected as ambiguous;
- unknown IDs stay unknown and never become executable sources.

Resolve profile/schedule aliases at read/use boundaries without rewriting their JSON files. UI and
new settings writes use canonical IDs only.

## 5. One effective snapshot

Adapt `CollectorProviderManager` to:

- own/use the canonical repository and load one typed catalog snapshot;
- derive `states()`/`enabled_provider_ids()` from that snapshot;
- expose bounded configuration update APIs for known non-secret fields;
- make environment overrides explicit/read-only in effective display state;
- keep health and vertical verification joins read-only and separate;
- stop mirroring enablement into the commercial legacy file;
- keep explicit health checks and current network lifecycle unchanged.

Credentials are resolved only by existing adapter credential boundaries. Public/display snapshots
contain only configured-state metadata, never key values or masked fragments.

## 6. Collector composition

Adapt existing seams only:

1. `TenderSearchUiController` creates/receives one manager and passes its snapshot/repository boundary
   to the existing `CollectorRunSession`.
2. `CollectorRunSession.run()` captures the immutable settings snapshot before building the service.
3. `create_default_collector_service()` and `create_default_async_providers()` accept that snapshot or
   a narrowly equivalent canonical boundary.
4. Commercial catalog/adapters consume the supplied effective settings and do not independently
   reopen `commercial_provider_settings.json`.
5. EIS/MOS behavior, cancellation, partial results, health monitor and service pipeline are unchanged.
6. Composition remains no-network; a runtime and network are still created only for an explicit run.

Do not create a new factory/catalog/session/engine or move scheduler ownership.

## 7. UI and scheduler refresh

Keep `TenderProviderManagerDialog` as the sole settings entry:

- add presentation-only controls for `access_confirmed` and `api_base_url` on supported commercial
  descriptors;
- show persisted/default/environment origin and editability;
- validate/save through manager APIs only;
- block mutations for corrupt/future catalog;
- leave MOS replacement-only keyring dialog unchanged;
- after save, call the existing controller refresh so provider manager, unified panel and Collector
  dialog receive the same snapshot;
- have scheduler dialog refresh from the same manager snapshot;
- preserve still-valid selection after canonicalization.

In the legacy platforms page, add only narrow explanatory text/action directing users to canonical
Collector sources. Keep `PlatformConnection` CRUD and `ManualConnectorTester` compatibility behavior;
do not import/delete/execute those entries as Collector providers.

## 8. Expected-red contract

Add before any production implementation:

- `tests/test_rm131_provider_settings_schema.py`;
- `tests/test_rm131_provider_settings_migration.py`;
- `tests/test_rm131_provider_identity.py`;
- `tests/test_rm131_provider_settings_composition.py`;
- `tests/test_rm131_provider_settings_dialog.py`;
- `tests/test_rm131_legacy_platform_handoff.py`;
- `tests/test_rm131_provider_settings_security.py`.

Expected-red assertions cover typed statuses, strict persistence, split-v1 precedence, two-source
backup/rollback, aliases, one snapshot identity, manager/run/scheduler parity, existing dialog,
legacy separation, no secrets and no startup network. Record exact command and failures in the audit.

## 9. Regression contour

In addition to the seven RM-131 modules, run existing owners:

- `tests/test_collector_provider_settings.py`;
- `tests/test_collector_provider_control.py`;
- `tests/test_commercial_provider_catalog.py`;
- `tests/test_commercial_provider_adapter.py`;
- `tests/test_collector_async_provider_factory.py`;
- `tests/test_collector_provider_factory_settings.py`;
- `tests/test_collector_run_session.py`;
- `tests/test_tender_provider_manager_dialog.py`;
- `tests/test_tender_provider_ui_controller.py`;
- `tests/test_tender_collector_ui_controller.py`;
- `tests/test_tender_search_ui_controller.py`;
- `tests/test_collector_scheduler.py`;
- `tests/test_tender_collector_scheduler_controller.py`;
- `tests/test_user_settings.py`;
- `tests/test_bootstrap_tender_search_integration.py`;
- EIS/MOS and vertical verification tests touched by composition.

Keep RM-130 profile/scheduler fixtures byte-identical except explicit test temp data.

## 10. Verification

Environment:

```powershell
$env:PYTHONUTF8 = "1"
$env:QT_QPA_PLATFORM = "offscreen"
$python = "C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe"
New-Item -ItemType Directory -Force .tmp | Out-Null
```

Focused RM-131:

```powershell
& $python -m pytest -q --basetemp=.tmp/rm131-focused `
  tests/test_rm131_provider_settings_schema.py `
  tests/test_rm131_provider_settings_migration.py `
  tests/test_rm131_provider_identity.py `
  tests/test_rm131_provider_settings_composition.py `
  tests/test_rm131_provider_settings_dialog.py `
  tests/test_rm131_legacy_platform_handoff.py `
  tests/test_rm131_provider_settings_security.py
```

Then run the neighbor files from section 9, full pytest and every exact command from
`.github/workflows/quality-gate.yml`: secret scan, Ruff check/format, configured mypy, offline
credential smoke, migration/schema smoke, public import, headless composition, release/build smoke,
full pytest and `pip_audit --skip-editable`. Finish with `git diff --check` and clean tracked status.

No test or composition command may perform live provider I/O.

## 11. Commit and release sequence

1. `docs(rm-131): audit provider settings ownership`
2. `test(rm-131): define provider settings migration contract`
3. `feat(rm-131): add canonical provider settings contract`
4. `feat(rm-131): migrate split provider settings to schema v2`
5. `feat(rm-131): unify provider catalog identity`
6. `feat(rm-131): share provider settings across collector composition`
7. `feat(rm-131): adapt provider settings UI and legacy handoff`
8. `test(rm-131): cover provider settings rollback and security`
9. `docs(rm-131): record provider settings acceptance evidence`

Inseparable implementation commits may be combined, but docs-only audit, expected-red and post-merge
closeout remain separate.

Feature PR is merged only after green PR matrix. Then verify the exact merge SHA with Windows Python
3.12/3.13 and create `docs/rm-131-completion` with
`docs(rm-131): close provider settings stage`. Only merged closeout may mark RM-131 `DONE` and activate
RM-132.

## 12. Rollback and stop rule

Application rollback is a scoped revert of RM-131 feature commits. Data rollback uses byte-for-byte
backups of general/commercial v1; failed replace preserves both originals; legacy commercial input is
not deleted. Profile/schedule data is never mass-rewritten.

Stop if implementation requires a new settings file/repository/manager/catalog/factory/engine/vault/
health subsystem, DB migration, destructive legacy migration, startup network, secret display/read,
scheduler redesign, working commercial adapter invention, score/decision/AI change or RM-132+ scope.
