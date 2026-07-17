# RM-133 — implementation plan ручной регистрации площадки

Дата: 17 июля 2026 года.
Baseline: `76687a50fe679bfcecc8cc48796fa4fcfae2bba6`.
Ветка: `feat/rm-133-manual-provider-registration`.

План основан на `docs/RM-133_MANUAL_PROVIDER_AUDIT.md`, D-03/D-04/D-05 из
`docs/RM-126_REQUIREMENTS.md`, закрытых RM-131/RM-132 и canonical Definition of Done. Scope
RM-134+ не включён.

## 1. Mandatory sequence

1. Commit audit, this plan and roadmap audit evidence as docs-only.
2. Add seven expected-red modules without production changes.
3. Run exact red contour; accept only missing RM-133 symbols/behavior.
4. Record exact red evidence and commit tests separately.
5. Add pure immutable model/validation/catalog projection.
6. Upgrade the existing repository from schema v2 to v3 with rollback-safe migration.
7. Add manager commands and application/domain execution guards.
8. Adapt the existing dialog/controller; preserve legacy separation.
9. Run focused, neighbor, full workflow-equivalent gates and write acceptance evidence.
10. Feature PR → merge → exact merge-SHA Windows gate → separate docs-only closeout.

## 2. Pure registration domain

Add one storage-free pure module under `app/tenders/collector` for:

- `ManualProviderDraft` and immutable `ManualProviderRegistration`;
- `ManualProviderLifecycle.PROTOCOL_REQUIRED` and typed origin/manual capability projection;
- typed command status/error/result without raw input or exception;
- NFKC display-name validation and comparison key;
- strict inert HTTP(S) homepage/endpoint normalization without DNS;
- stable `manual_<uuid4().hex>` ID validation/factory;
- duplicate/collision validators over the complete resolved snapshot;
- bounded `ProviderRegistrationOnlyError` / `PROTOCOL_REQUIRED` execution category.

Do not place Qt, persistence, keyring, network client, adapter construction or callable/import path in
this module.

## 3. Schema v3 in the existing repository

Extend `ProviderEnablementRepository` in place:

- set `SCHEMA_VERSION = 3`;
- preserve v2 `providers`, `configuration`, `updated_at` semantics;
- add deterministic `manual_registrations` mapping keyed by stable manual ID;
- extend typed load result/snapshot with immutable registrations;
- read valid v2 in memory without write;
- on first explicit mutation create byte-exact v2 backup and atomically write v3;
- preserve existing split-v1 backup/read behavior and materialize directly to v3 on mutation;
- expose repository methods used by manager register/update commands under the existing lock;
- reload and run duplicate/catalog validation inside the same mutation lock;
- keep corrupt/future fail closed and original bytes unchanged;
- clean temp and preserve original on replace failure;
- keep legacy commercial and user settings bytes untouched.

Manual enablement is derived false. A tampered `providers[manual_id]=true` may be retained only if
safe for rollback, but must never change snapshot enabled/runnable state and should be normalized to
false on the next successful explicit manual mutation.

## 4. Resolved catalog projection

Keep `canonical_provider_definitions()` byte/logically stable for built-ins. Add a pure resolved
catalog function/read model that:

- appends manual registrations in deterministic order;
- exposes origin, lifecycle and runnable/factory/protocol/credential/health capabilities;
- uses a zero-capability `ProviderDescriptor` with `TenderSource.CUSTOM`, disabled default and
  `manual_registration` implementation status only for display compatibility;
- validates built-in IDs, aliases/targets, manual IDs, name keys and endpoint keys;
- permits multiple `CUSTOM` registrations while rejecting identity ambiguity;
- does not add manual IDs to the alias table.

## 5. Application commands

Extend `CollectorProviderManager` with synchronous typed commands:

- `register_manual_provider(draft)`;
- `update_manual_provider(provider_id, draft_or_patch)`.

The manager creates the ID once, delegates atomic conflict/persistence to the existing repository and
maps validation/schema/persistence failures to fixed safe command results. One command result contains
only provider ID, status/error category, lifecycle, safe message and aware UTC timestamp.

Removal/archive is excluded until profile/scheduler reference semantics are designed. Built-ins and
manual registrations cannot be deleted through RM-133 UI/API. Registration commands never call the
credential service, health repository, vertical verification or legacy store.

## 6. Fail-closed execution

Add guards at existing seams:

1. `ProviderSettingsSnapshot` resolves manual IDs but reports them registration-only and disabled.
2. `CollectorProviderManager.set_enabled(True)` rejects manual registrations with a bounded error.
3. Unified request resolution rejects `runnable=False` even if a forged state says enabled.
4. Existing controller/scheduler start path filters/rejects manual IDs before worker creation.
5. `CollectorRunSession.run()` calls snapshot execution validation before `runtime_factory()`.
6. Existing async factory remains static built-ins only and never creates a manual adapter.
7. Environment values and hand-edited JSON cannot alter manual lifecycle.

No guard may include endpoint/raw input in its error text.

## 7. Existing UI adaptation

Adapt only `TenderProviderManagerDialog` and `TenderSearchUiController`:

- add action `Добавить площадку вручную`;
- add presentation-only modal editor with display name, homepage URL and optional endpoint URL;
- omit protocol, credentials, headers, parser, connection test and executable configuration;
- locally gate Save and then revalidate through manager command;
- disable Save after accept to guard repeated submission;
- refresh the same provider table/unified/Collector/scheduler views after success;
- show manual row disabled with `Требуется выбор протокола`;
- disable enable/configure credential/check actions;
- add edit-metadata action for a selected manual row; keep stable ID;
- show only fixed safe validation/conflict messages; never status/log endpoint.

Existing commercial configuration and MOS/commercial credential dialogs stay unchanged.

## 8. Legacy handoff

Keep `PlatformConnection`, `UserSettingsStore`, `ManualConnectorTester`, compatibility notices,
canonical-manager action and disabled legacy credential widget unchanged. Add only regression guards:

- no automatic/explicit import in RM-133;
- no `user_settings.json` rewrite when canonical manager opens or registration is saved;
- no legacy keyring read/delete;
- legacy health result cannot affect canonical registration state.

## 9. Expected-red modules

- `tests/test_rm133_manual_provider_model.py`;
- `tests/test_rm133_manual_provider_schema.py`;
- `tests/test_rm133_manual_provider_catalog.py`;
- `tests/test_rm133_manual_provider_composition.py`;
- `tests/test_rm133_manual_provider_dialog.py`;
- `tests/test_rm133_manual_provider_security.py`;
- `tests/test_rm133_legacy_platform_handoff.py`.

The red suite uses fake ID/time factories, fake runtime/network/DNS/keyring seams and unique secret/
CRLF sentinels. Accept only missing new boundary/behavior, not unrelated regressions.

## 10. Required test contract

Focused assertions cover:

- immutable model, stable ID/rename, aware UTC, bounded Unicode/control/bidi validation;
- URL normalization, default-port/trailing-slash duplicate keys and unsafe input rejection;
- missing/v2/v3/corrupt/future load; first backup; atomic rollback; deterministic persistence;
- whole-catalog identity/alias/name/endpoint collision guards;
- registration-only capability projection and manual JSON enablement tampering;
- manager command typing, conflict byte preservation and concurrent duplicate create;
- unified/profile/scheduler/factory/session pre-runtime execution guards;
- existing manager action/form/refresh/edit flow and disabled manual row;
- no credential/legacy/network/DNS/import/subprocess/filesystem execution;
- no sentinel/raw endpoint in errors, repr, public payload, logs, UI, support/crash/export.

## 11. Neighbor regression

Run at minimum:

- RM-130 saved profile and unified search modules;
- all RM-131 schema/migration/identity/composition/dialog/security/legacy modules;
- all RM-132 credential service/environment/composition/dialog/security/legacy modules;
- provider control/settings/factory/session modules;
- provider/unified/Collector/scheduler dialogs and controllers;
- bootstrap/startup/shutdown, user settings, diagnostic support bundle and crash reporting;
- EIS/MOS/commercial adapter/catalog regression touched by catalog projection.

No validation command may perform live provider I/O, DNS or host-keyring reads.

## 12. Verification

Use Windows Python 3.12.7, `PYTHONUTF8=1`, `QT_QPA_PLATFORM=offscreen` and ignored local basetemp.
Run focused seven RM-133 modules, neighbor contour, full pytest and every exact command from
`.github/workflows/quality-gate.yml`:

- `python scripts/check_repository_secrets.py`;
- `python -m ruff check .`;
- `python -m ruff format . --check`;
- `python -m mypy` with the configured 20-file contour;
- offline credential, database/schema, import, composition and release/build smokes;
- `python -m pytest -q`;
- `python -m pip_audit --skip-editable`;
- `git diff --check` and clean tracked status.

## 13. Commit and release sequence

1. `docs(rm-133): audit manual provider registration boundaries`
2. `test(rm-133): define manual provider registration contract`
3. `feat(rm-133): add registration-only provider model`
4. `feat(rm-133): migrate provider settings to schema v3`
5. `feat(rm-133): project manual registrations in provider catalog`
6. `feat(rm-133): guard manual providers from execution`
7. `feat(rm-133): add canonical manual provider form`
8. `test(rm-133): cover registration migration and execution guards`
9. `docs(rm-133): record manual provider acceptance evidence`

Implementation commits may combine inseparable changes. Docs-only audit, expected-red and post-merge
closeout remain separate. Feature PR title:
`feat(rm-133): add safe manual provider registration`.

After green PR matrix: merge feature, verify exact merge SHA on Windows Python 3.12/3.13, create
`docs/rm-133-completion`, merge docs-only closeout and verify final main gate. Only closeout may mark
RM-133 `DONE` and RM-134 sole `IN PROGRESS`.

## 14. Rollback and stop rule

Application rollback is a scoped feature revert. Data rollback restores the byte-exact v2 (or split
v1) backups. Failed replace leaves original current file untouched; no SQLite or legacy rollback is
needed.

Stop if implementation requires a second settings owner/file/catalog/manager/factory/engine, DB
migration, arbitrary credential identity, dynamic code/import, automatic legacy migration, network/
DNS during composition or mutation, silent reference cascade, dependency update, RM-134+ behavior or
deterministic decision/AI change.
