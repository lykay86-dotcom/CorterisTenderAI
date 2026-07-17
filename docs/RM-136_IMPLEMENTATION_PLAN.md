# RM-136 — implementation plan безопасной проверки подключения

Дата: 17 июля 2026 года
Baseline: `ef5cee6d0ef2079f23866fbb809575806f52a0d4`
Ветка: `feat/rm-136-manual-provider-health-check`

План основан на `docs/RM-136_CONNECTION_HEALTH_AUDIT.md`, закрытых RM-131–RM-135,
canonical roadmap и Definition of Done. RM-137+ не включён.

## 1. Mandatory sequence

1. Commit audit и этот plan отдельным docs-only commit.
2. Добавить expected-red RM-136 tests без production changes.
3. Запустить exact red contour; принять только отсутствующий RM-136 contract.
4. Зафиксировать expected-red отдельным commit.
5. Реализовать immutable health/binding/target/admission domain.
6. Повысить existing health schema v1 -> v2 и settings schema v5 -> v6.
7. Расширить existing credential façade и static manual adapter/factory dependencies.
8. Реализовать bounded API/RSS/FTP/FTPS probes и one-shot service.
9. Подключить manager/admission/UI с cancellation и no-auto-enable.
10. Выполнить focused/neighbor/full workflow-equivalent gates и acceptance evidence.
11. Feature PR -> green CI -> explicit merge -> exact merge-SHA gate -> separate closeout.

## 2. Pure health and binding domain

Создать `manual_provider_health.py`:

- health contract version 1;
- closed enums stages/outcomes/health/reason codes;
- frozen `HealthCheckBinding`, stage/result/evidence/read-model/command types;
- deterministic safe payload and bounded messages/stages;
- aware UTC timestamps and monotonic duration validation;
- protocol snapshot fingerprint and exact current binding builder;
- TTL freshness evaluator (15 minutes), clock anomaly and future/corrupt fail-closed;
- pure admission decision requiring explicit enabled + fresh `PASSED/HEALTHY` exact evidence;
- no Qt, socket, keyring, settings write or Collector persistence.

## 3. Target policy and narrow transport

Создать `manual_probe_transport.py` with injected ports:

- resolver returns bounded typed answers;
- target policy canonicalizes endpoint and classifies every IPv4/IPv6 candidate;
- prohibit non-global/special ranges, metadata, obfuscated literals, unsafe ports, userinfo,
  control/bidi/CRLF and origin-changing credential forwarding;
- connector uses only validated address while preserving TLS SNI/hostname verification;
- no environment proxy/custom CA/trust-all/downgrade;
- bounded total/connect/read timeouts, response/listing/sample caps, redirect count and transient
  retry count;
- safe typed transport errors without raw target/exception;
- deterministic fakes/local controlled server seams.

HTTP/RSS implement GET only. FTP/FTPS implement passive read-only login, listing and one bounded
suffix-matching sample; no active/mutation/recursive surface exists.

## 4. Protocol selection schema v6

Extend `manual_provider_protocol.py` and existing repository:

- add closed `ManualProviderFtpsMode {IMPLICIT, EXPLICIT}`;
- mode is valid only for FTPS;
- implicit uses `ftps://` default 990; explicit uses typed AUTH TLS policy/default 21;
- preserve endpoint secrecy/public payload rules;
- settings schema v6; strict current decoder;
- v5 FTPS selection migrates in memory to `IMPLICIT`, other families to no mode;
- first explicit mutation creates byte-exact `.v5-*.bak`; atomic replace/rollback unchanged;
- corrupt/future/unknown fields fail closed.

No health result or secret is added to provider settings.

## 5. Health evidence repository v2

Upgrade `ProviderCheckRepository` in place:

- typed load statuses and strict schema v2;
- latest manual result/evidence per stable provider ID;
- deterministic serialization and sorted keys;
- atomic temp replace and first v1 byte-exact backup;
- legacy v1 is diagnostic-only/unverified;
- compare current binding/check ID before replace;
- explicit invalidate without deleting configuration/credential;
- cancelled operation is not persisted over previous evidence;
- corrupt/future blocks verification/admission and preserves bytes;
- no raw payload/listing/certificate/IP/exception/secret.

## 6. Credential façade extension

Extend `ProviderCredentialService`, not keyring ownership:

- allow code-derived manual descriptors only for validated stable IDs and allowlisted kinds;
- deterministic non-secret descriptor revision/fingerprint;
- API key namespace and FTP/FTPS username/password namespaces;
- optional environment name remains absent for manual credentials;
- runtime-only resolution result has secret fields `repr=False` and no public serializer;
- missing/backend failure typed and bounded;
- manager save/replace/delete invalidates provider evidence;
- UI never prefill/readback/fingerprint secret value.

## 7. Adapter/factory and payload compatibility

Type `ManualAdapterDependencies` with one runtime probe/execution port. Existing compiler remains
static and no-I/O. `CompiledManualTenderProvider.check_health()` delegates only when an admitted
explicit operation supplies the dependency; save/load/compile/startup remain denied/no-I/O.

Health service uses the compiled adapter identity and existing RM-135 bounded parser/mapping preview:

- MIME/format checked before parse;
- actual bounded sample only;
- required mappings all present for `PASSED/HEALTHY`;
- empty/no matching record -> `DEGRADED/INSUFFICIENT_SAMPLE`;
- Decimal/aware datetime/missing/provenance semantics unchanged;
- no production `UnifiedTender`, DB/checkpoint/dedup/history mutation during check.

Normal manual adapter instances are rebuilt from current snapshot; no stale cache.

## 8. One-shot service

`ManualProviderHealthService.test_connection(command)`:

1. normalize provider ID and acquire per-provider single-flight/global semaphore;
2. snapshot registration and build exact binding;
3. preconditions/compile/target/credential gates before network;
4. run deterministic stages with cancellation and monotonic timings;
5. protocol transport + bounded compatibility check;
6. recompute binding from fresh settings/credential state;
7. persist only still-current final result; create evidence only for `PASSED/HEALTHY`;
8. release resources/locks and apply cooldown.

Dependencies (clock, resolver, transport, credential resolver, repository) are injected. Public tests
use fakes/local servers only.

## 9. Manager, invalidation and admission

Extend `CollectorProviderManager`:

- expose typed start/read/cancel-compatible test command;
- manual configured provider gets check availability even while disabled;
- states distinguish health, verification freshness and enabled state;
- mutation of registration/protocol/spec/credentials invalidates evidence immediately;
- `set_enabled(True)` for manual requires current ready evidence but never occurs automatically;
- `assert_runnable_provider_ids()` delegates manual IDs to one canonical admission evaluator.

Extend `ProviderSettingsSnapshot` minimally with derived admission metadata, not persisted evidence.
Manager, controller/unified/profile, scheduler callback, run-session and factory all recalculate/recheck
the same binding before runtime creation. Built-in paths retain current behavior.

## 10. UI worker and UX

Adapt only existing dialog/controller:

- manual configured row gets `Проверить подключение` independent of enabled checkbox;
- pre-start confirmation shows display name, protocol and safe hostname summary;
- staged text, no fake percentage;
- worker owns `CollectorCancellationToken`; Cancel/close requests cancellation;
- per-provider double-click and global busy state guarded;
- fixed safe reason messages and aware timestamp/valid-until;
- health/verified/enabled displayed separately;
- success shows `Готов к включению` and leaves checkbox off;
- stale edit refreshes immediately;
- no raw exception passed from worker to Qt.

Business policy remains in domain/service; Qt assembles commands and presents results only.

## 11. Expected-red modules

Add before production code:

- `tests/test_rm136_health_model.py`;
- `tests/test_rm136_health_binding.py`;
- `tests/test_rm136_target_policy.py`;
- `tests/test_rm136_http_rss_probe.py`;
- `tests/test_rm136_ftp_ftps_probe.py`;
- `tests/test_rm136_health_persistence.py`;
- `tests/test_rm136_credential_binding.py`;
- `tests/test_rm136_health_service.py`;
- `tests/test_rm136_health_admission.py`;
- `tests/test_rm136_health_dialog.py`;
- `tests/test_rm136_health_security.py`;
- `tests/test_rm136_legacy_handoff.py`.

Expected red covers missing symbols only; tripwires forbid public DNS, host keyring, legacy tester,
startup probe, DB/tender/checkpoint mutation and raw sentinel leakage.

## 12. Neighbor regression

Run all RM-131–RM-135 modules plus:

- provider settings/control/credentials/definitions/factory/session;
- async HTTP/network/runtime/health monitor/rate limiter/cancellation;
- EIS/MOS checkpoints and provider health;
- manual adapter parser/mapping/preview/provenance;
- unified/profile/scheduler/run-session admission;
- manager dialog/controller/legacy/support/crash/bootstrap/shutdown;
- schema migration/build/import/offline smokes.

No automated command contacts a public provider or real credential store.

## 13. Verification

Use Windows Python 3.12.7, UTF-8, Qt offscreen and isolated local basetemp. Execute:

1. focused RM-136;
2. neighbor RM-131–RM-135/owner contour;
3. controlled local-server transport integration tests;
4. full pytest;
5. repository secret scan;
6. Ruff check/format;
7. configured mypy plus changed-contour mypy;
8. offline credential, DB/schema, import, composition and release/build smokes;
9. startup/shutdown/no-network smokes;
10. dependency audit;
11. Windows event-loop/path/encoding/high-DPI contour;
12. `git diff --check` and tracked status review.

CI must pass Python 3.12 and 3.13. After feature merge run exact merge-SHA Windows gate.

## 14. Commit/release sequence

1. `docs(rm-136): audit connection health boundaries`
2. `test(rm-136): define manual connection health contract`
3. `feat(rm-136): add version-bound health evidence`
4. `feat(rm-136): add safe manual probe transport`
5. `feat(rm-136): integrate manual connection testing`
6. `feat(rm-136): enforce health-bound admission`
7. `test(rm-136): cover health security and lifecycle`
8. `docs(rm-136): record connection health acceptance evidence`

Feature title: `feat(rm-136): add safe manual provider health check`.

Feature merge требует явного подтверждения. Only a later merged docs-only closeout may mark RM-136
`DONE` and determine/activate the next stage from current roadmap.

## 15. Rollback and stop rule

Code rollback is scoped feature revert. Data rollback restores byte-exact v5 settings and v1 health
backups. No SQLite/keyring value migration exists; credential account names remain deterministic.

Stop if implementation requires second settings/health store, health monitor, catalog, manager,
factory, Collector or vault; public-network tests; unrestricted URL/method/header/body/FTP commands;
automatic probe/enable/profile/schedule mutation; destructive legacy migration; DB schema change;
decision/AI semantics change or RM-137+ scope.
