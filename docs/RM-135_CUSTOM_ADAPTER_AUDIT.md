# RM-135 — аудит безопасного конструктора пользовательского адаптера

Дата аудита: 17 июля 2026 года  
Baseline / RM-134 docs-closeout SHA: `9008f8caee02c09221ab9e2e7da1c130420d0689`  
Ветка: `feat/rm-135-safe-custom-adapter-builder`  
Статус: audit завершён до изменения application-кода.

## 1. Entry gate

- `STATUS.md` и `ROADMAP.md` назначают RM-135 единственным `IN PROGRESS`; RM-134 — `DONE`,
  RM-136+ — `PLANNED`.
- Feature PR RM-134 #74 слит как `7ef0378315f9ef76046a651d1211f3da191b7719`;
  PR run `29577913214` и exact merge run `29578571237` успешны на Python 3.12/3.13.
- Docs-only closeout PR #75 слит как baseline `9008f8caee02c09221ab9e2e7da1c130420d0689`;
  final exact-SHA run `29580225769` успешен на Python 3.12/3.13.
- Ветка и отдельный worktree созданы непосредственно от `9008f8c`. Корневой checkout и
  пользовательские untracked `.agents/`/`skills-lock.json` не изменялись.
- Полностью прочитаны canonical roadmap/status/DoD/history, RM-126 audit/requirements,
  audit/plan/acceptance RM-131–RM-134 и RM-135 ТЗ.

## 2. Baseline evidence и версии

Среда: Windows, Python 3.12.7, `PYTHONUTF8=1`, `QT_QPA_PLATFORM=offscreen`, repository-local
ignored basetemp; live provider I/O и host credential read отсутствовали.

- RM-131–RM-134 contour: `173 passed, 2 warnings in 15.60s`;
- full pytest: `1796 passed, 2 warnings in 80.54s`;
- secret scan: `Repository secret scan passed.`;
- Ruff: `All checks passed!`; format: `583 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- workflow smokes/import: `14 passed in 9.73s`; `DashboardController`;
- dependency audit: editable package skipped; `No known vulnerabilities found`.

Contract baseline:

| Boundary | Version/state at baseline |
|---|---|
| Provider settings | schema v4 |
| Collector SQLite | schema v14 |
| Collector architecture | v1 |
| Async provider API | implicit stable v1 (`AsyncTenderProvider`), no numeric public constant |
| Provider parser contract | per-adapter `parser_version`; no generic parser version |
| Canonical tender | `UnifiedTender`, no numeric schema constant |
| Normalization | one `TenderNormalizer`, no numeric public version |
| Verification/provenance | one `TenderVerificationService`, no numeric public version |

Два warnings принадлежат существующему openpyxl compatibility contour.

## 3. Owners и call-site graph

```text
TenderProviderManagerDialog
  -> TenderSearchUiController
  -> CollectorProviderManager
  -> ProviderEnablementRepository
  -> collector_provider_settings.json (schema v4)

CollectorRunSession
  -> settings snapshot runnable guard
  -> create_collector_network_runtime
  -> create_default_collector_service
  -> create_default_async_providers
  -> AsyncProviderSearchEngine
  -> CollectorService
  -> TenderNormalizer -> deduplicator -> TenderVerificationService
  -> CollectorStateRepository / tender_records
```

`canonical_provider_definitions()` остаётся static built-in catalog. `resolved_provider_catalog()`
добавляет manual registrations только как projection. Второй catalog/store/factory/Collector не нужен.

## 4. Текущий adapter/provider contract

Канонический async contract — `AsyncTenderProvider`:

- immutable `ProviderDescriptor` и stable provider ID;
- async `search`, `get_tender`, `list_documents`, `check_health`;
- optional cooperative `CollectorCancellationToken`;
- typed `TenderSearchResult`, `UnifiedTender`, `TenderDocument`, `ProviderHealth`;
- `validate_configuration()` для bounded readiness gaps;
- `connection_mode` и `parser_version` для provenance.

Contract не содержит context-manager/`aclose()` на самом provider: network resources принадлежат
`CollectorNetworkRuntime`, который закрывается `CollectorRunSession` в `finally`. Checkpoint и
freshness реализованы adapters/Collector, normalization/dedup/provenance — после provider result.

RM-135 может безопасно построить instance, реализующий этот interface, но его live methods обязаны
возвращать typed `CONNECTION_TEST_REQUIRED`/unsupported result до RM-136. Наличие object instance не
даёт admission в `CollectorRunSession`.

## 5. Protocol/transport/parser/mapping matrix

| Family | RM-134 metadata | Existing transport/parser | RM-135 decision |
|---|---|---|---|
| API | HTTPS, JSON/XML, none/API key | shared `AsyncHttpClient`; MOS JSON parser is provider-specific | compile static API adapter; offline JSON/XML only; live blocked |
| RSS/Atom | HTTPS, RSS/Atom, none | no canonical generic feed parser | bounded offline XML/feed parser; live blocked |
| FTP | FTP, none/user-password | only legacy `ManualConnectorTester`/`ftplib` | do not reuse; compile read-only capability descriptor; live blocked |
| FTPS | FTPS, none/user-password | only legacy `FTP_TLS` tester | do not reuse; TLS/no-downgrade descriptor; live blocked |

`AsyncHttpClient` verifies TLS, bounds response size, retries and supports cancellation, but its
default redirects are enabled and it has no arbitrary-target DNS/SSRF/rebinding policy. It is safe for
code-defined domains, not yet for a user endpoint. No safe canonical FTP/FTPS transport exists.
Adding live egress belongs to explicit RM-136 verification/hardening; RM-135 adds only DI ports and
side-effect-free objects, not a second network stack.

Existing JSON/XML/CSV parsing is provider-specific; a reusable restricted selector/mapping owner is
absent. A new pure manual-adapter domain module is therefore justified. It may use stdlib JSON/CSV and
ElementTree only after bounded input and explicit DTD/entity/XInclude rejection. It must not expose
JSONPath/XPath/regex/templates/code.

Canonical output remains `UnifiedTender`; money uses `TenderMoney(Decimal)`, datetime mappings require
aware values, missing fields remain missing/diagnostic, and mapping provenance enters
`raw_metadata['field_provenance']` for the existing verification owner.

## 6. Credential boundary

`ProviderCredentialService` is a storage-free typed façade over the sole `app.security.secrets`
keyring owner. Builder/compiler/preview/startup must not call `has/load/save/delete`. Spec stores only
typed auth requirement. Manual credential account names, if used by explicit UI command, derive from
validated stable provider ID and allowlisted kind; values never enter spec/fingerprint/settings.

Runtime resolution remains prohibited until an admitted RM-136+ operation. Existing built-in
descriptor identities and environment overrides remain unchanged.

## 7. Persistence/versioning decision

`ProviderEnablementRepository` remains the owner. RM-135 raises schema v4 -> v5 and adds nullable
versioned adapter spec to each manual registration:

- v4 loads in memory with `adapter_spec=None` and lifecycle `ADAPTER_REQUIRED`;
- first explicit mutation creates byte-exact v4 backup and atomic v5 replace;
- corrupt/future/unknown fields fail closed;
- optimistic concurrency uses current registration `updated_at`;
- canonical JSON and SHA-256 content fingerprint exclude timestamps, revision and secrets;
- semantic no-op save preserves revision/bytes;
- changed save increments revision and retains a bounded previous revision for rollback;
- clear preserves stable ID/protocol, returns lifecycle to `ADAPTER_REQUIRED`, and never deletes
  credentials implicitly.

SQLite/database migration is not required.

## 8. Minimal new domain and extension points

One pure module `manual_adapter.py` owns:

- immutable typed spec/submodels and hard limits;
- restricted selectors, canonical field allowlist and pure transform allowlist;
- deterministic validation/serialization/fingerprint;
- bounded offline sample parse/map/preview and safe diagnostics;
- static code-owned compiler registry for API/RSS/FTP/FTPS;
- scoped runtime adapter instances that conform to `AsyncTenderProvider` but deny live execution.

Existing extension points changed minimally:

- registration embeds spec/revision history;
- provider settings schema/repository persists it;
- manager exposes typed save/clear/rollback/preview/compile commands;
- existing async factory delegates manual construction to the static compiler without adding manual
  providers to ordinary production composition;
- existing manager dialog/controller hosts a presentation-only wizard.

## 9. Lifecycle/admission decision

```text
no protocol -> PROTOCOL_REQUIRED
protocol, no spec -> ADAPTER_REQUIRED
valid spec + offline compile -> CONNECTION_TEST_REQUIRED / UNVERIFIED
```

`READY`, `VERIFIED`, `HEALTHY`, `RUNNABLE` and auto-enable are impossible in schema/domain/UI.
Manual provider remains `enabled=False`, `registration_only=True`, `runnable=False`. Run session,
unified search, profiles, scheduler and health keep fail-closed guards before runtime/network creation.

## 10. Offline preview and sample decision

Pure preview accepts bounded bytes/text supplied explicitly. UI may read one explicitly selected local
file only after size check, but sample bytes/path are never persisted. No URL fetch, DB write,
production tender creation, dedup/search, background task or credential resolution occurs. Preview is
bounded by code-owned bytes/depth/records/fields/string limits and returns canonical safe values,
missing fields, transforms and provenance—not raw payload.

## 11. Threat model and guards

Rejected at validation/compile boundaries:

- executable text, import/class paths, eval/exec/compile, pickle, template/regex/SQL/shell;
- arbitrary HTTP method/body/header/cookie/query bag, FTP mutation/commands and protocol downgrade;
- unrestricted JSONPath/XPath, recursive wildcard/functions, XML DTD/entity/XInclude;
- user-info/query secrets, control/bidi/CRLF, private IP literals and unsupported schemes/ports;
- unbounded sample, nesting, selector, mapping, transform, record or string counts;
- secret/private endpoint/raw sample in repr, diagnostics, logs or public payload;
- stale/tampered revision/fingerprint and any configured=>runnable promotion.

DNS revalidation, redirect revalidation and live TLS/FTP verification remain RM-136 prerequisites.

## 12. Expected-red contract

Before production code add focused modules for:

- immutable spec/version/revision/fingerprint/security;
- schema v5 migration/backup/rollback/concurrency;
- API/RSS/FTP/FTPS static compiler dispatch and no-I/O construction;
- restricted JSON/XML/feed/CSV selectors and transform/mapping provenance;
- offline preview bounds/no persistence/no secret leakage;
- manager/factory/execution guards and existing UI wizard wiring;
- legacy byte preservation/no tester/keyring revival.

Accepted red may contain only missing RM-135 symbols/schema/UI behavior.

## 13. Allowed files and unchanged contracts

Allowed application owners: `manual_provider_registration.py`, new `manual_adapter.py`,
`provider_settings.py`, `provider_definitions.py`, `provider_control.py`,
`async_provider_factory.py`, existing dialog/controller and public collector exports. Tests/docs are
added in RM-135 scope.

Unchanged: built-in provider IDs/factories/adapters, network execution, health/C19 evidence,
Collector normalization/dedup semantics, `UnifiedTender` model, SQLite schema, profiles/scheduler
references, legacy store/tester, deterministic score/recommendation/critical-stop priority and AI.

## 14. Explicit RM-136 exclusions

No connection test, live health, DNS lookup, TLS handshake, credential validation/resolution,
redirect handling, remote listing/download, canary, verified state, enablement or scheduled/manual
production execution is implemented in RM-135.

## 15. Audit decision

**ACCEPTED FOR DOCS-ONLY AUDIT COMMIT.** The safe scope is implementable inside existing owners with
one justified pure domain module. Production changes remain blocked until this audit and
`docs/RM-135_IMPLEMENTATION_PLAN.md` are committed, followed by separate expected-red evidence.
