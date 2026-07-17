# RM-135 — implementation plan безопасного конструктора адаптера

Дата: 17 июля 2026 года  
Baseline: `9008f8caee02c09221ab9e2e7da1c130420d0689`  
Ветка: `feat/rm-135-safe-custom-adapter-builder`

План основан на `RM-135_CUSTOM_ADAPTER_AUDIT.md`, canonical RM-126 handoff, закрытых RM-131–RM-134
и Definition of Done. RM-136+ live execution не включён.

## 1. Mandatory sequence

1. Commit audit и этот plan отдельным docs-only commit.
2. Добавить expected-red tests без production changes; принять только отсутствующий RM-135 contract.
3. Зафиксировать expected-red отдельным commit.
4. Добавить pure spec/selectors/mappings/transforms/preview/compiler.
5. Повысить existing provider settings schema v4 -> v5 и добавить revisions.
6. Расширить existing manager/factory projection без production admission.
7. Встроить presentation-only wizard в existing provider manager/controller.
8. Добавить security/execution/legacy regressions.
9. Выполнить focused/neighbor/full workflow-equivalent gate и acceptance evidence.
10. Feature PR -> green CI -> explicit merge confirmation -> exact merge-SHA gate -> separate closeout.

## 2. Pure manual adapter domain

Создать `app/tenders/collector/manual_adapter.py`:

- `MANUAL_ADAPTER_SPEC_VERSION = 1`;
- closed enums data format, selector kind, canonical target field, transform, diagnostic status/code;
- frozen `SourceRequestSpec`, `RecordSelectorSpec`, `FieldMappingSpec`, `AdapterResourceLimits`,
  `ManualAdapterSpec`;
- canonical deterministic serialization and semantic SHA-256 fingerprint;
- aware UTC timestamps and monotonic revision;
- strict bounded validation; no arbitrary mapping bag or executable field;
- safe public payload/repr without endpoint, sample, credential or raw source value.

Spec binds stable provider ID and selected protocol family but does not duplicate endpoint or secret.
Protocol compatibility is checked against the current RM-134 selection at compile/save.

## 3. Restricted parsing, mapping and preview

Implement pure bounded parsers over supplied bytes/text:

- JSON: exact object-key/array-step path segments only;
- XML/RSS/Atom: exact namespace-aware element segments; reject DTD/entity/XInclude before parse;
- CSV only for FTP/FTPS with allowlisted delimiter/encoding and hard row/field caps;
- no JSONPath/XPath functions, regex, recursive wildcard or filesystem/network access.

Map only code-defined `UnifiedTender` targets. Allowed pure transforms: trim/collapse/empty-to-missing,
Unicode normalization, exact Decimal parse, explicit aware datetime parse, URL normalization,
literal enum mapping and bounded list normalization. Missing required values become diagnostics; never
invent defaults. Preview returns bounded safe canonical values plus source-path/transform/status/spec
revision provenance and never persists raw sample or creates a production tender.

## 4. Compiler and runtime adapter

Add static code-owned builder map for API/RSS/FTP/FTPS. Compiler:

- accepts only validated current registration/spec;
- checks provider/protocol/version/fingerprint/capabilities;
- receives transport/parser/credential resolver references through DI but invokes none;
- returns typed VALID/INVALID/UNSUPPORTED result and safe diagnostics;
- creates a new scoped `AsyncTenderProvider` instance with spec/fingerprint/revision;
- performs no network/DNS/TLS/filesystem/keyring/thread/task/global-registry mutation.

All runtime live methods check cancellation then raise bounded `CONNECTION_TEST_REQUIRED` or
`ProviderCapabilityError`. API is read-only GET descriptor; FTP/FTPS expose no mutation method;
FTPS verification/downgrade flags are code constants. RM-136 will add admitted transport execution.

## 5. Schema v5 and revision policy

Extend `ProviderEnablementRepository` only:

- `SCHEMA_VERSION = 5`; add `MIGRATED_V4` status;
- current manual registration may contain `adapter_spec` and bounded `adapter_spec_history`;
- valid v4 -> `adapter_spec=None` in memory, stable identity/protocol/timestamps preserved;
- first mutation creates byte-exact v4 backup, then atomic v5 replace;
- strict unknown/future/corrupt fail-closed decode;
- compare-and-replace by registration `updated_at`;
- no-op semantic save does not write/increment;
- changed save increments revision; previous current enters bounded history;
- rollback creates a new current revision; clear requires UI confirmation and keeps history/protocol;
- credentials, sample and runtime objects are forbidden from persistence.

## 6. Manager/catalog/factory integration

Extend existing owners:

- manager commands: draft/read/compile/preview/save/clear/rollback with typed safe results;
- catalog/display projection: `adapter_configured`, fingerprint/revision and
  `CONNECTION_TEST_REQUIRED`, while enabled/runnable remain false;
- factory helper delegates to static compiler but ordinary built-in provider composition does not
  enumerate or execute manual adapters;
- run session/unified/profile/scheduler/health guards continue to reject every manual provider before
  runtime creation, including tampered enabled/ready-like JSON.

No global runtime cache is introduced, so cleared/changed revisions cannot be reused by production
composition. Compiler instance metadata is immutable and exact-bound to revision/fingerprint.

## 7. Credential handoff

Spec stores only RM-134 auth kind. Optional replacement input is write-only and passed by controller to
the existing `ProviderCredentialService` with descriptor identity derived from validated stable manual
ID and allowlisted kind. Staged order is credential write then spec save; any partial failure remains
non-runnable and returns typed remediation. Builder/preview/save/load never resolve credential value;
clear spec never deletes credential implicitly.

## 8. Existing UI wizard

Add one `ManualAdapterWizardDialog` inside `tender_provider_manager_dialog.py` and one existing
manager signal/controller route:

- manual provider only; source and RM-134 protocol are read-only;
- controlled data format, selector segments, mappings/targets/transforms and resource limits;
- bounded pasted/local sample preview explicitly labelled offline/unverified;
- diagnostics and missing required fields; save disabled on blocking errors;
- cancel leaves repository unchanged; double-save guarded; stale conflict is explicit;
- clear/rollback require confirmation;
- success: `Адаптер настроен. Требуется проверка подключения.`;
- no active connection/health button or fake network spinner.

Qt contains presentation/draft assembly only; parsing/validation/compile/persistence remain manager/domain.

## 9. Expected-red and regression files

Add focused RM-135 modules covering spec, schema, compiler/protocol builders, selectors/mapping,
offline preview, factory/execution guard, dialog/security and legacy handoff. Use fake dependencies,
unique sentinels and network/DNS/keyring/thread tripwires. Commit the accepted red before implementation.

Neighbor contour includes all RM-131–RM-134 tests, provider settings/control/factory/session,
normalizer/dedup/verification/provenance, unified/profile/scheduler guards, manager/controller/UI,
legacy/support/crash/bootstrap/shutdown and existing providers.

## 10. Verification

Use Python 3.12.7, UTF-8, Qt offscreen and repository-local basetemp. Run:

1. focused RM-135;
2. neighbor RM-131–RM-134 and owner contour;
3. full `pytest`;
4. exact workflow secret/Ruff/format/mypy/smoke/import/full/dependency commands;
5. explicit no-network/no-DNS/no-keyring/no-thread compile/preview/startup tests;
6. `git diff --check` and tracked status review.

No validation invokes live provider I/O.

## 11. Commit/release sequence

1. `docs(rm-135): audit safe custom adapter boundaries`
2. `test(rm-135): define custom adapter specification contract`
3. `feat(rm-135): add versioned safe adapter specification`
4. `feat(rm-135): compile custom adapters without side effects`
5. `feat(rm-135): add restricted mapping and offline preview`
6. `feat(rm-135): add custom adapter wizard`
7. `test(rm-135): cover adapter security and execution guards`
8. `docs(rm-135): record custom adapter acceptance evidence`

Feature title: `feat(rm-135): add safe custom adapter builder`.

Feature merge and exact merge-SHA gate require explicit confirmation. Only a later merged docs-only
closeout may mark RM-135 `DONE` and activate RM-136.

## 12. Rollback and stop rule

Application rollback is scoped feature revert. Data rollback restores byte-exact v4 backup; v5
current content remains inspectable and no SQLite/keyring/sample/network side effect is introduced by
migration. Stop if implementation requires a second store/catalog/factory/Collector/vault,
unrestricted parser/config DSL, live egress/credential resolution, DB migration, legacy import/delete,
normalization/decision/AI change or RM-136 functionality.
