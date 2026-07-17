# RM-132 — аудит безопасного ввода credentials

Дата аудита: 17 июля 2026 года.
Baseline: `d86b8867b298203e550074037e0c3a09f5bf2aa1`.
Ветка: `feat/rm-132-secure-credentials-input`.
Worktree: `C:\CorterisTenderAI_1_5_1\.worktrees\rm-132-secure-credentials-input`.

## 1. Entry gate

Gate пройден до любых application changes:

- `origin/main` указывает на docs-only closeout merge RM-131
  `d86b8867b298203e550074037e0c3a09f5bf2aa1`;
- feature PR #68 RM-131 слит коммитом
  `bbfd8e3b858a29f07d7b55fde5fdb5a80a1d9cf2`;
- exact feature merge-SHA Quality Gate run `29562019173` успешен на Windows Python 3.12/3.13;
- final post-closeout Quality Gate run `29562744319` успешен на точном baseline: Python 3.12 —
  `1686 passed in 84.06s`, Python 3.13 — `1686 passed in 82.28s`;
- `docs/STATUS.md` и `docs/ROADMAP.md` назначают RM-131 `DONE`, RM-132 — единственным
  `IN PROGRESS`, RM-133–RM-200 — `PLANNED`;
- открытого PR, local/remote branch или worktree RM-132 до начала не существовало;
- tracked основной checkout чист; пользовательские untracked `.agents/` и `skills-lock.json` не
  изменялись; локальный устаревший `main` не перематывался, ветка создана прямо от `origin/main`;
- полностью прочитаны canonical roadmap/DoD/history, `docs/RM-126_REQUIREMENTS.md`,
  `docs/RM-131_AUDIT.md`, `docs/RM-131_IMPLEMENTATION_PLAN.md`, current `pyproject.toml`, Windows
  workflow и handoff RM-132.

RM-131 завершил один non-secret settings owner за `CollectorProviderManager`; credential/keyring
boundary намеренно не менялся и передан RM-132.

## 2. Baseline evidence

Среда: Windows, Python 3.12.7, `PYTHONUTF8=1`, `QT_QPA_PLATFORM=offscreen`, repository-local ignored
basetemp. Live network и host credential reads не выполнялись тестами.

- credential/provider/settings/UI/support/crash contour: `71 passed in 6.41s`;
- full pytest: `1686 passed in 74.30s (0:01:14)`;
- первый запуск не достиг application assertions: отсутствовал родитель `.tmp` для explicit
  `--basetemp`, что дало setup-only `FileNotFoundError`; после создания ignored `.tmp` те же exact
  команды прошли без code/config change;
- final prerequisite GitHub run `29562744319`: both matrix jobs and every workflow step `success`.

## 3. Existing owner and infrastructure boundary

`app/security/secrets.py` — единственный production-модуль, который импортирует `keyring` и вызывает
`set_password`, `get_password`, `delete_password`. Service name стабилен: `CorterisTenderAI`.

Текущий public API:

| Function | Behavior | Finding |
|---|---|---|
| `save_secret(name, value)` | direct `keyring.set_password` | raw backend exception; arbitrary name/value |
| `load_secret(name)` | returns stored value | valid runtime primitive, unsafe для UI/read model |
| `delete_secret(name)` | idempotent only for `PasswordDeleteError` | other raw backend errors escape |

Fake seams сейчас создаются monkeypatch/injected `Callable`; typed backend port, bounded error category,
presence-only operation, operation result, concurrency guard и aware operation timestamp отсутствуют.

`app/core/ai/provider_selection.py` уже является отдельным application service для AI provider
selection поверх того же `app.security.secrets`; он не является tender-provider credential owner и не
должен заменяться вторым vault. Он остаётся neighbor regression scope. RM-132 не объединяет AI и
tender provider identity catalogs и не меняет AI runtime/provider semantics.

## 4. Tender credential identities

Канонические provider IDs определены existing RM-131 catalog; фактический logical kind для всех
подтверждённых tender credentials сейчас один — `api_key`.

| Canonical provider | Protected-store name | Environment override |
|---|---|---|
| `mos_supplier` | `collector.mos_supplier.api_key` | `CORTERIS_MOS_API_KEY` |
| `b2b_center` | `collector.b2b_center.api_key` | `CORTERIS_B2B_API_KEY` |
| `gazprombank` | `collector.gazprombank.api_key` | `CORTERIS_GPB_API_KEY` |
| `fabrikant` | `collector.fabrikant.api_key` | `CORTERIS_FABRIKANT_API_KEY` |
| `tek_torg` | `collector.tek_torg.api_key` | `CORTERIS_TEK_TORG_API_KEY` |
| `otc` | `collector.otc.api_key` | `CORTERIS_OTC_API_KEY` |
| `sber_commercial` | `collector.sber_commercial.api_key` | `CORTERIS_SBER_COMMERCIAL_API_KEY` |
| `rts_commercial` | `collector.rts_commercial.api_key` | `CORTERIS_RTS_COMMERCIAL_API_KEY` |
| `roseltorg_commercial` | `collector.roseltorg_commercial.api_key` | `CORTERIS_ROSELTORG_COMMERCIAL_API_KEY` |

EIS credentials не требует. Username/password/client credentials для canonical providers текущими
descriptors не подтверждены и не должны угадываться.

RM-131 aliases `sber_a`, `rts_tender`, `roseltorg` collision-free разрешаются только к canonical IDs.
Production writer для alias keyring names не найден, поэтому automatic value migration не требуется.
Произвольные legacy `platform:<display name>` не имеют доказанного one-to-one соответствия catalog и
не могут автоматически копироваться или удаляться.

## 5. Current call sites

| Call site | Current behavior | Decision |
|---|---|---|
| `TenderSearchUiController.configure_provider_credentials()` | MOS-only direct save, затем raw load/readback и exact value comparison | заменить manager-owned safe command result; readback удалить |
| `CollectorProviderManager.states()` / `_definitions()` / `_initial_state()` | `MosSupplierApiConfig.from_environment()` может читать host keyring при ordinary composition/state rendering | обычный snapshot должен быть no-secret/no-network; state query только через safe explicit boundary |
| `MosSupplierApiConfig.from_environment()` | runtime env → keyring fallback; token stored `repr=False` | сохранить только runtime adapter path; не использовать для UI state |
| `AsyncMosSupplierTenderProvider.validate_configuration()` | показывает fragment из `masked_token` | заменить boolean configured metadata |
| `CommercialSecretResolver` | runtime env → keyring fallback, `.strip()` меняет value, `last_error` содержит `str(exc)` | сохранить runtime-only resolution; exact value и bounded error |
| `CommercialProviderResolvedSettings.public_payload()` | boolean плюс `masked_api_key` fragment | fragment удалить; оставить safe boolean state |
| legacy `TenderWorkspacePage` platforms tab | arbitrary `platform:<name>` save/delete/load, один secret передаётся как password и API key | credential field отключить; не читать/писать/удалять guessed secret; направить к canonical manager |
| `ManualConnectorTester` | explicit live test и raw `str(exc)` | остаётся compatibility tester без credentials; raw network cleanup — RM-134/RM-136, не startup |
| async factory/runtime adapters | читают secrets только при explicit Collector run/health composition | сохранить infrastructure/runtime path |

Commercial provider manager сейчас редактирует только non-secret `access_confirmed` и
`api_base_url`; credential command для восьми commercial descriptors отсутствует.

## 6. Confirmed gaps

1. Нет единого typed application contract `save/has/delete` для canonical tender provider и
   allowlisted logical kind.
2. MOS UI подтверждает save чтением полного секрета обратно и сравнением значения.
3. Ordinary provider state construction может прочитать host keyring до explicit run/health action.
4. Commercial providers имеют runtime secret resolution, но не имеют безопасного save/delete UI.
5. Replacement/delete confirmation, idempotent safe result, double-submit guard и backend-unavailable
   read model не централизованы.
6. Leading/trailing whitespace сейчас silently удаляется в MOS dialog/config и commercial resolver.
7. Commercial public payload и MOS diagnostic содержат masked fragments реального значения.
8. `CommercialSecretResolver.last_error` и raw keyring exceptions могут содержать backend text,
   private account path или sentinel value.
9. Legacy UI создаёт arbitrary secret identity из user display name, читает значение дважды и
   передаёт одно значение одновременно как password/API key.
10. Нет централизованного collision guard между provider ID, logical kind, keyring account name и
    confirmed aliases.

## 7. Leak-path audit

- Canonical `collector_provider_settings.json` schema v2 содержит только enablement,
  `access_confirmed`, normalized endpoint и aware timestamp; secret keys/values/masked fragments
  запрещены existing tests.
- SQLite writes credentials не найдены; Collector/AI/business schemas не содержат provider secrets.
- `MosSupplierApiConfig.api_token` и commercial resolved `api_key` используют `repr=False`; однако
  explicit masked properties создают derivative secret data и должны быть удалены из public paths.
- Provider UI/status currently can show raw health errors; RM-132 must guarantee only credential
  backend errors are bounded. General network-health error hardening remains RM-136.
- `SensitiveDataFilter`, support bundle `_Redactor` и crash `_CrashRedactor` redact common labelled
  patterns and bearer headers, but cannot prove removal of an arbitrary unlabelled backend sentinel.
  Therefore raw credential/backend exception text must not leave the infrastructure boundary.
- No automatic clipboard use exists in credential forms. Existing crash-report clipboard actions copy
  already redacted reports and are not credential UI.
- No provider credential is intentionally included in export/support bundle/telemetry; the commercial
  `masked_api_key` public field is the one confirmed export-like violation.
- Qt dynamic properties/snapshots do not currently store provider tokens; new dialog must clear widget
  text and must not prefill on reopen.

## 8. Chosen minimal architecture

1. Extend existing `app.security.secrets` in place with a presence-only operation and sanitized typed
   backend errors; preserve `load_secret` only for runtime adapters.
2. Add one narrow application service over that owner for canonical tender provider credentials. It
   owns no storage and accepts an injected fake backend for tests.
3. Build credential descriptors from existing MOS constant and commercial definitions; validate
   canonical IDs, logical kinds, protected-store names, env names and aliases for collisions.
4. Expose frozen safe state/result objects containing IDs, enums, fixed message and aware UTC
   timestamp only. Secret values/raw exceptions are `repr`/serialization-inaccessible.
5. Make `CollectorProviderManager` own/inject this service and expose safe state/save/delete commands.
   Ordinary `states()` and startup remain no-keyring/no-network.
6. Generalize the existing `ProviderCredentialsDialog` for MOS and commercial sources: no prefill,
   exact new-value submission, explicit replacement/delete confirmation, input clearing and
   double-submit guard.
7. Keep actual secret loading inside explicit runtime adapter construction. Environment remains
   runtime-only, never copied; UI reports only the environment origin and treats save as read-only.
8. Remove masked fragments and raw credential backend text from public payload/diagnostics.
9. Retire arbitrary legacy credential CRUD without deleting existing keyring entries. Legacy manual
   non-secret entries and unauthenticated explicit tester remain for rollback/compatibility.

This is an application façade over the one existing Windows keyring owner, not a second vault.

## 9. Replacement, delete and concurrency policy

- empty/all-whitespace/control-character/oversized values fail before backend access;
- valid leading/trailing spaces are preserved byte-for-byte; no `.strip()` is applied to saved or
  runtime credential material;
- save on configured protected-store state requires explicit `replace=True` from confirmed UI;
- replacement performs one protected-store set; the old value is never intentionally deleted first;
- delete requires explicit UI confirmation, is idempotent and does not touch provider settings;
- environment override is reported without exposing its value, is never copied and is not removed by
  protected-store delete;
- one service lock and dialog busy state serialize repeated submit in-process;
- every error becomes a bounded category such as `BACKEND_UNAVAILABLE`, `ACCESS_DENIED`,
  `INVALID_INPUT`, `NOT_CONFIGURED` or `OPERATION_FAILED` without `str(exc)`.

## 10. Migration and rollback

Confirmed canonical keyring account names remain unchanged, so normal MOS/commercial credentials need
no data rewrite. No proven writer for alias keyring names exists. Ambiguous `platform:<name>` entries
are preserved untouched and ignored by the canonical command service; guessing a mapping would violate
RM-126/RM-131 identity rules.

Application rollback is a scoped revert of RM-132 feature commits. Existing keyring values remain
usable by the previous version because canonical account names and service name are unchanged. Legacy
arbitrary values are neither migrated nor deleted. No JSON/SQLite/schema migration is required.

## 11. Expected-red boundary

Before production changes add separate modules covering:

- `test_rm132_credential_service.py` — typed states/results, exact save/replacement/delete, validation;
- `test_rm132_credential_identity.py` — descriptor allowlist, aliases and collisions;
- `test_rm132_credential_environment.py` — explicit runtime override isolation;
- `test_rm132_credential_dialog.py` — no prefill, confirmation, clear/cancel/double submit;
- `test_rm132_credential_composition.py` — manager safe state and no startup keyring/network;
- `test_rm132_credential_security.py` — sentinel absence in repr/errors/log/JSON/SQLite/export;
- `test_rm132_legacy_credentials_handoff.py` — no arbitrary keyring CRUD and preserved legacy entries.

Expected red is accepted only for absent RM-132 symbols/behavior. Existing RM-131/provider/runtime/UI,
AI keyring isolation, support/crash, startup and full baseline must remain green.

## 12. Non-scope and stop rules

Non-scope: manual provider creation, protocol selection, adapter builder, live connection test redesign,
health subsystem rewrite, general network-error cleanup, new scraping/API contract, normalization,
parallel search, scheduler monitoring, DB migration, AI provider redesign, score/recommendation/critical
stop-factor changes, dependencies and RM-133+.

Stop if implementation requires a new vault/file/table/encryption scheme, arbitrary UI secret names,
credential readback for display, inferred legacy mapping, startup/live network, DB migration, second
provider catalog/settings owner, automatic connection check or decision/AI semantics change.

## 13. Audit decision

**ACCEPTED FOR DOCS-ONLY AUDIT COMMIT.** Confirmed gaps are solvable by extending the existing
`app.security.secrets` infrastructure boundary, adding one storage-free typed tender credential façade
owned by `CollectorProviderManager`, and adapting existing UI/runtime seams. Production changes remain
blocked until this audit and `docs/RM-132_IMPLEMENTATION_PLAN.md` are committed separately, followed by
expected-red evidence.

## 14. Expected-red evidence

After docs-only audit commit `25b2eed`, seven RM-132 test modules were added without production
changes and run with the exact focused command from the implementation plan.

Accepted result: collection failure, `7 errors in 3.90s`. Six modules failed only because
`app.tenders.provider_credentials` does not yet exist; the legacy handoff module failed only because
the new `LEGACY_PLATFORM_CREDENTIAL_NOTICE` boundary does not yet exist. Ruff check passed for all
seven files.

An initial red run also reported a test-only typo in the existing ConfigManager import path. That typo
was corrected before accepting evidence; the repeated run above contains only missing RM-132
symbols/behavior. There was no application assertion failure, network call, host keyring read, Qt
failure or unrelated baseline regression.

Production implementation is unblocked by the audit/test ordering gate. RM-132 remains
`IN PROGRESS`; RM-133+ production scope remains blocked.
