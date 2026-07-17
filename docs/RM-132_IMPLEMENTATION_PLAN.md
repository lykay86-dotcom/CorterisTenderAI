# RM-132 — implementation plan безопасного ввода credentials

Дата: 17 июля 2026 года.
Baseline: `d86b8867b298203e550074037e0c3a09f5bf2aa1`.
Ветка: `feat/rm-132-secure-credentials-input`.

План основан на `docs/RM-132_SECURE_CREDENTIALS_AUDIT.md`, D-05 из
`docs/RM-126_REQUIREMENTS.md`, закрытом RM-131 и canonical Definition of Done. RM-133+ не включён.

## 1. Mandatory sequence

1. Commit audit, this plan and roadmap audit evidence as docs-only.
2. Add seven expected-red modules without production changes.
3. Run the exact red contour; accept only missing RM-132 public symbols/behavior.
4. Record exact red evidence and commit tests separately.
5. Harden `app.security.secrets` without changing service/account compatibility.
6. Add one storage-free typed provider credential service over the existing owner.
7. Inject it through `CollectorProviderManager` and existing controller/dialog seams.
8. Remove masked/readback/raw-error and arbitrary legacy credential paths.
9. Run focused, neighbor, full workflow-equivalent gates and write acceptance evidence.
10. Feature PR → merge → exact merge-SHA Windows gate → separate docs-only closeout.

## 2. Infrastructure hardening

Extend `app/security/secrets.py` in place:

- keep `SERVICE = "CorterisTenderAI"` and canonical account names;
- retain `save_secret`, runtime-only `load_secret`, idempotent `delete_secret` compatibility;
- add presence-only `has_secret`;
- wrap backend failures in bounded typed categories without raw text/cause chaining;
- never log, format, serialize or return the value except `load_secret` to runtime adapters;
- provide a small injected backend protocol/adapter if required by tests, without persistence.

## 3. Typed application service

Add a pure/application module under `app/tenders` that:

- constructs one immutable credential descriptor registry from existing MOS and commercial definitions;
- allows only canonical provider IDs and descriptor-declared logical kinds;
- rejects unknown/ambiguous/duplicate provider, alias, kind, environment or keyring identities;
- returns frozen state/command results with enums, safe message and aware UTC timestamp;
- preserves exact valid input whitespace, rejects empty/control/oversized input;
- serializes replacement/delete with an in-process lock;
- uses one set operation for replacement and idempotent delete;
- distinguishes protected-store configured, environment override, missing, invalid and backend unavailable;
- never exposes a secret in repr/public payload/result/error.

## 4. Manager and runtime composition

Adapt existing `CollectorProviderManager`:

- own or receive one credential service;
- expose `credential_state`, `save_credential`, `delete_credential` only;
- join only safe cached/read state into `ProviderDisplayState`;
- make ordinary `states()` no-keyring and no-network;
- keep explicit health/run runtime resolution through existing MOS/commercial adapter paths;
- do not write provider settings JSON or health SQLite for credential commands.

Update MOS/commercial runtime surfaces:

- remove masked value properties from public/display payload;
- preserve runtime-only secret values `repr=False`;
- stop stripping valid credential whitespace;
- convert resolver backend errors to bounded categories;
- retain explicit run/health credential loading and current network semantics.

## 5. Existing UI adaptation

Generalize `ProviderCredentialsDialog` and the existing manager dialog/controller:

- configure MOS and all eight commercial descriptor credentials through manager commands;
- show only safe state/origin;
- never prefill or create a masked placeholder from the real value;
- explicit confirmation for replacement and delete;
- Cancel performs no backend operation;
- clear widget/new-value buffer after take/operation;
- guard repeated submit and use accessible labels/object names without secret content;
- display only fixed service result messages for backend errors;
- opening provider UI performs no network and startup composition performs no keyring read.

Legacy manual platform page keeps non-secret CRUD and explicit compatibility testing but removes
arbitrary credential save/load/delete. Existing unknown keyring entries are preserved for rollback and
the page links to the canonical Collector provider manager.

## 6. Expected-red modules

- `tests/test_rm132_credential_service.py`;
- `tests/test_rm132_credential_identity.py`;
- `tests/test_rm132_credential_environment.py`;
- `tests/test_rm132_credential_dialog.py`;
- `tests/test_rm132_credential_composition.py`;
- `tests/test_rm132_credential_security.py`;
- `tests/test_rm132_legacy_credentials_handoff.py`.

The tests use unique sentinels and fake backends only; no host keyring or live network is allowed.

## 7. Neighbor regression

Run RM-131 settings/identity/composition/security modules plus:

- `tests/test_collector_provider_control.py`;
- `tests/test_collector_provider_settings.py`;
- `tests/test_commercial_provider_catalog.py`;
- `tests/test_commercial_provider_adapter.py`;
- `tests/test_collector_mos_supplier_provider.py`;
- `tests/test_mos_supplier_api_config.py`;
- `tests/test_collector_async_provider_factory.py`;
- `tests/test_tender_provider_manager_dialog.py`;
- `tests/test_tender_provider_ui_controller.py`;
- `tests/test_user_settings.py`;
- `tests/test_ai_provider_selection.py` and `tests/test_ai_provider_settings_ui.py`;
- `tests/test_diagnostic_support_bundle.py` and `tests/test_crash_reporting.py`;
- `tests/test_bootstrap_tender_search_integration.py` and shutdown neighbors.

## 8. Verification

Use Windows Python 3.12.7, `PYTHONUTF8=1`, `QT_QPA_PLATFORM=offscreen`, and ignored repository-local
basetemp. Run focused seven RM-132 modules, neighbor contour, full pytest, then every command from
`.github/workflows/quality-gate.yml`:

- `python scripts/check_repository_secrets.py`;
- `python -m ruff check .`;
- `python -m ruff format . --check`;
- `python -m mypy` using the exact `pyproject.toml` contour;
- offline credential, migration/schema, import, composition and release/build smokes;
- `python -m pytest -q`;
- `python -m pip_audit --skip-editable`;
- `git diff --check` and clean tracked status.

No validation command may perform live provider I/O or read the host keyring.

## 9. Commit and release sequence

1. `docs(rm-132): audit credential input boundaries`
2. `test(rm-132): define secure credential input contract`
3. `feat(rm-132): unify protected credential commands`
4. `feat(rm-132): migrate provider credential dialogs`
5. `test(rm-132): cover secret redaction and lifecycle`
6. `docs(rm-132): record secure credentials acceptance`

Feature PR title: `feat(rm-132): secure API and credential input`.

Only after green PR matrix: merge feature, verify exact merge SHA on Windows Python 3.12/3.13, create
`docs/rm-132-completion`, merge docs-only closeout, and verify final main gate. Only closeout marks
RM-132 `DONE` and RM-133 sole `IN PROGRESS`.

## 10. Rollback and stop rule

Rollback is a scoped feature revert. Protected-store service/account names do not change; previous
runtime remains compatible. No JSON/SQLite migration exists. Legacy arbitrary keyring entries are
preserved and never guessed, copied or deleted.

Stop if implementation requires a second vault, new persistence, custom encryption, arbitrary secret
name, saved-value UI readback, new provider/catalog/network engine, startup network/keyring read, DB
migration, automatic live check, dependency update, RM-133+ behavior or decision/AI semantics change.
