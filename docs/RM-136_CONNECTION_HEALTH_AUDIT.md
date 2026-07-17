# RM-136 — аудит безопасной проверки подключения ручного провайдера

Дата аудита: 17 июля 2026 года
Baseline / RM-135 docs-closeout SHA: `ef5cee6d0ef2079f23866fbb809575806f52a0d4`
Ветка: `feat/rm-136-manual-provider-health-check`
Статус: audit завершён до изменения application-кода.

## 1. Roadmap alignment и entry gate

Критический gate пройден однозначно:

- `docs/STATUS.md`, `docs/ROADMAP.md` и `docs/ROADMAP_HISTORY.md` назначают RM-136
  единственным `IN PROGRESS`; RM-135 имеет `DONE`, RM-137–RM-200 — `PLANNED`;
- прежняя конфликтующая нумерация отсутствует в текущем canonical roadmap;
- feature PR RM-135 #76 слит как
  `306b20977b6c23956488dc471da63af17f197e25`;
- exact feature merge-SHA run `29586643112` успешен на Python 3.12/3.13;
- docs-only closeout PR #77 слит как точный baseline
  `ef5cee6d0ef2079f23866fbb809575806f52a0d4`;
- final exact closeout-SHA run `29589905109` имеет `success`; jobs
  `87916095488` (Python 3.12) и `87916095437` (Python 3.13), каждый обязательный
  step завершён `success`;
- GitHub CLI авторизован как `lykay86-dotcom`; PR и run проверены read-only;
- branch/worktree созданы непосредственно от `ef5cee6d`; root checkout и пользовательские
  untracked `.agents/`/`skills-lock.json` не менялись;
- полностью прочитаны canonical roadmap/status/DoD/history, audit/plan/acceptance
  RM-131–RM-135 и полное ТЗ RM-136.

Application changes разрешены только после отдельного commit этого audit и
`docs/RM-136_IMPLEMENTATION_PLAN.md`, затем отдельного expected-red commit.

## 2. Baseline evidence и версии

Среда: Windows, Python 3.12.7, `PYTHONUTF8=1`, `QT_QPA_PLATFORM=offscreen`, отдельный
repository-local basetemp. Live provider I/O, публичный DNS и host credential read не выполнялись.

- full pytest, первый прогон: `1823 passed, 2 warnings in 81.54s`;
- full pytest, повтор без изменений: `1823 passed, 2 warnings in 73.16s`;
- owner contour RM-131–RM-135/settings/credentials/health/HTTP/checkpoint/run-session:
  `149 passed in 10.17s`;
- repository secret scan: `Repository secret scan passed.`;
- Ruff check: `All checks passed!`;
- Ruff format: `592 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- offline credential smoke: `2 passed in 7.01s`;
- DB/schema smoke: `5 passed in 5.01s`;
- headless composition: `1 passed in 0.39s`;
- release/build: `6 passed in 5.60s`;
- public import: `DashboardController`;
- dependency audit: editable package skipped, `No known vulnerabilities found`;
- `git diff --check` и tracked status: clean.

Оба warnings — принятые openpyxl extension warnings legacy fixture RM-132.

| Boundary | Baseline contract |
|---|---|
| Provider settings | schema v5; v4 in-memory migration и byte-exact backup |
| Manual adapter | `MANUAL_ADAPTER_SPEC_VERSION = 1`, monotonic revision, semantic SHA-256 fingerprint |
| Manual lifecycle | `CONNECTION_TEST_REQUIRED`, disabled, registration-only, non-runnable |
| Factory | static `build_manual_async_provider()` → existing `AsyncTenderProvider`; construction no-I/O |
| Runtime ownership | one `CollectorNetworkRuntime`, `CollectorRunSession` closes it in `finally` |
| Credentials | one storage-free `ProviderCredentialService`; descriptors have no revision marker yet |
| Provider health | generic `ProviderHealth` + schema-v1 `ProviderCheckRepository` latest record |
| Circuit breaker | one in-memory `ProviderHealthMonitor`, scoped to each Collector network runtime |
| Checkpoints | EIS/MOS Collector checkpoints in existing SQLite; unrelated to connection evidence |
| C19 verification | separate full vertical live-smoke SQLite evidence; not reusable as RM-136 binding |

## 3. Current owners and call-site graph

```text
TenderProviderManagerDialog
  -> TenderSearchUiController._ProviderCheckWorker
  -> CollectorProviderManager.check_providers()
  -> built-in AsyncTenderProvider.check_health()
  -> ProviderCheckRepository (collector_provider_health.json, schema v1)

Manual registration/protocol/spec
  -> ProviderEnablementRepository (collector_provider_settings.json, schema v5)
  -> ProviderSettingsSnapshot / resolved_provider_catalog()
  -> build_manual_async_provider() / CompiledManualTenderProvider
  -> current live methods fail connection_test_required

Normal execution
  -> UI/profile/scheduler
  -> CollectorProviderManager.assert_runnable_provider_ids()
  -> CollectorRunSession (second pre-runtime guard)
  -> one CollectorNetworkRuntime
  -> create_default_collector_service()/create_default_async_providers()
  -> AsyncProviderSearchEngine / existing ProviderHealthMonitor
```

Существующие owners сохраняются:

- settings/spec/protocol — `ProviderEnablementRepository`;
- credential values — `app.security.secrets` за `ProviderCredentialService`;
- latest provider diagnostics/evidence — `ProviderCheckRepository`;
- application façade — `CollectorProviderManager`;
- runtime adapter factory — `async_provider_factory.py`;
- execution — `CollectorRunSession` и existing UI/profile/scheduler chain;
- in-run circuit breaker — `ProviderHealthMonitor` без redesign.

Нужен отдельный one-shot `ManualProviderHealthService`, потому что built-in
`AsyncTenderProvider.check_health()` и in-run circuit breaker не имеют revision binding, stages,
freshness, target policy или stale-completion guard. Service не является вторым monitor/catalog/store:
он orchestrates explicit operation и пишет результат в existing health repository owner.

## 4. Health owner findings

`ProviderHealth` содержит только provider ID, coarse status, строковый timestamp/message и latency.
`ProviderCheckRepository` schema v1:

- не проверяет schema version;
- permissive пропускает invalid records;
- не имеет atomic stale-write guard/backup/future-state distinction;
- не хранит protocol/spec/credential/policy binding или TTL;
- сохраняет raw `message`/`last_error`;
- не различает operation outcome, health, verification и enablement.

`ProviderHealthMonitor` — корректный единственный circuit breaker normal Collector, но он:

- in-memory и пересоздаётся с runtime;
- хранит raw exception text;
- не является persisted verification;
- не должен запускать periodic/manual probes и не меняется архитектурно в RM-136.

EIS/MOS checkpoints относятся только к successful collection cursor/watermark. C19 vertical smoke
проверяет полный pipeline и SQLite/UI, поэтому не является коротким connection test и не мигрируется.
Live scripts запускаются только оператором; startup и scheduler provider probes не вызывают.

Решение: повысить existing `ProviderCheckRepository` до schema v2 и хранить только последнюю
canonical manual evidence. Legacy v1 читается как diagnostic/unverified и никогда не мигрирует
`AVAILABLE` в runnable evidence. История не добавляется; retention = latest per provider.

## 5. Runtime adapter/factory findings

`CompiledManualTenderProvider` уже exact-bound к stable provider ID, spec revision/fingerprint и
protocol family, создаётся static compiler registry без I/O и получает dependencies через DI.
Это правильный adapter для probe и будущего admitted execution; несовместимая lightweight copy не
создаётся.

Gaps:

- dependencies пока untyped `object` и live methods всегда denied;
- endpoint/protocol selection не включены в adapter fingerprint;
- credential resolver не вызывается;
- no stale runtime cache существует — это безопасно и сохраняется;
- parser/mapping handoff доступен через existing bounded RM-135 preview functions;
- normal factory intentionally не перечисляет manual registrations;
- run-session rejects every manual ID, не проверяя evidence.

RM-136 типизирует runtime probe dependency, но compile/save/load остаются no-I/O. Normal adapter
instances остаются scoped и никогда не кэшируются между revisions.

## 6. HTTP/RSS transport capability matrix

| Capability | Existing `AsyncHttpClient` | RM-136 decision |
|---|---|---|
| Session ownership/close | есть | reuse runtime lifecycle |
| TLS/system trust | есть через `build_ssl_context` | reuse, без UI custom CA/verify false |
| Proxy isolation | runtime default `trust_env=False` | mandatory |
| Bounded streaming body | есть, default 50 MiB | stricter per-spec one-shot cap |
| Retry/backoff/cancel | есть | dedicated bounded policy/total deadline |
| Redirects | automatic, default true | manual probe disables and revalidates every hop |
| SSRF/DNS classification | отсутствует | new canonical target policy + resolver port |
| DNS rebinding/TOCTOU | отсутствует | connect only to validated resolved address |
| Safe errors | incomplete; raw detail and cause survive | typed reason codes, no raw exception |
| MIME/sniffing | отсутствует generically | validate before RM-135 parse |
| Decompression cap | counts decoded chunks only | explicit compressed/decompressed caps |

Existing client is safe for code-owned domains, but cannot prove pinned arbitrary-target connect.
Audit therefore permits one narrowly scoped `manual_probe_transport.py`: it extends the existing
runtime composition with resolver/connector ports and code-owned HTTP/FTP protocol operations. Это не
второй general HTTP client/Collector; public surface только bounded read-only probe/fetch.

API/RSS rules: HTTPS GET only, no user method/body/cookie/header bag, maximum 3 redirects, target
revalidation each hop, cross-origin auth removal, no environment proxy, code-owned Accept/Auth,
bounded status/MIME/body/decompression and total deadline. HTTP 2xx alone never creates evidence.

## 7. FTP/FTPS findings

Canonical async FTP/FTPS transport отсутствует. Единственный `ftplib` path — legacy
`ManualConnectorTester`; он разрешает direct DNS, не pin-ит passive endpoint, не даёт cooperative
cancellation и не является verification evidence. Его reuse запрещён.

Минимальный transport должен иметь:

- passive mode only; active mode и mutation commands отсутствуют в API;
- bounded connect/auth/listing и максимум один bounded `RETR` sample по allowlisted suffix;
- exact remote base path, no traversal/glob/recursive walk/symlink following;
- EPSV preferred; PASV endpoint повторно проходит target policy;
- listing bytes/items и sample bytes capped;
- FTP plaintext даёт `DEGRADED/INSECURE_TRANSPORT`, поэтому не создаёт runnable evidence;
- FTPS certificate/hostname verification, no downgrade, protected control/data channels;
- explicit/implicit mode только typed.

RM-134 persisted selection поддерживает лишь `ftps://`/990, то есть безопасно выражает implicit
mode, но не explicit AUTH TLS. Для обязательного typed dispatch требуется additive
`ManualProviderFtpsMode` и provider settings schema v6. Existing v5 FTPS selection детерминированно
migrирует как `IMPLICIT`; другие families получают `None`. Это единственное schema изменение.

## 8. Credential boundary

Existing `ProviderCredentialService` остаётся единственным application façade над keyring owner.
UI write-only/no-prefill, backend errors bounded, environment override runtime-only.

Gaps:

- descriptors только built-in API keys;
- `_resolve()` отвергает stable manual IDs;
- нет runtime-only resolution API через façade;
- нет descriptor version/fingerprint;
- replacement/delete не invalidates health evidence;
- username/password manual auth не имеет code-owned namespaces.

RM-136 добавляет dynamic descriptors, выводимые только из validated stable manual ID и allowlisted
kind: `api_key`, `username`, `password`. Keyring names deterministic; manual environment override не
угадывается. Descriptor fingerprint — SHA-256 от non-secret contract fields/version, не от value.
Runtime resolution возвращает frozen secret-bearing object с redacted repr только внутри explicit
health/adapter operation. Missing required credential blocks before DNS/network.

Evidence credential marker связывает descriptor fingerprint + configured origin/presence. Любой
canonical save/replace/delete немедленно invalidates evidence; admission также пересчитывает marker.
Secret/hash/value не сохраняются и не сравниваются.

## 9. Evidence contract, binding и persistence

Новый immutable contract version 1:

- operation outcome: `PASSED`, `DEGRADED`, `FAILED`, `BLOCKED`, `CANCELLED`;
- health: existing-compatible `HEALTHY`, `DEGRADED`, `UNHEALTHY`, `UNKNOWN`;
- deterministic ordered stages и stable reason codes из ТЗ;
- aware UTC start/finish/valid-until, duration только monotonic;
- bounded safe messages; raw endpoint/IP/payload/listing/certificate/exception отсутствуют.

Exact `HealthCheckBinding` содержит:

- stable provider ID;
- protocol snapshot SHA-256 (family, canonical endpoint, payload/auth/FTPS mode/TLS policy);
- adapter spec version/revision/fingerprint;
- credential descriptor marker без secret;
- target policy `manual-target-policy-v1`;
- transport policy `manual-probe-transport-v1`;
- health contract version 1.

TTL policy: code-owned `15 minutes`. Она консервативна, bounded, тестируется на exact boundary и не
может быть отключена UI/settings. `PASSED + HEALTHY + exact current binding` создаёт evidence;
остальные outcomes — diagnostic result only. Clock rollback/future/corrupt version fail closed.

Schema v2 `collector_provider_health.json`:

- latest record per provider only;
- deterministic JSON, atomic sibling temp replace;
- first v1 mutation creates byte-exact `.v1-*.bak`;
- typed missing/current/migrated-v1/corrupt/future load;
- compare-and-replace by binding/check ID rejects stale completion;
- interrupted/transient state never persisted as healthy;
- secrets/raw transport artifacts forbidden.

Provider settings schema v6 stores only typed FTPS mode and existing manual enablement boolean. Health
evidence не копируется в settings.

## 10. Probe pipeline

Deterministic fail-fast stages:

1. `PRECONDITIONS` — current manual registration/protocol/spec, not archived, supported capabilities;
2. `TARGET_POLICY` — canonical endpoint, scheme/port/path/userinfo/control policy;
3. `CREDENTIAL_AVAILABILITY` — descriptor/presence and runtime resolution only now;
4. `DNS_RESOLUTION` — bounded all-answer classification;
5. `CONNECT` — pinned allowed address and total deadline;
6. `TLS` — chain, hostname/SNI, FTPS control/data protection;
7. `AUTHENTICATION` — code-owned auth strategy;
8. `PROTOCOL` — bounded read-only GET or passive listing/sample;
9. `PAYLOAD_COMPATIBILITY` — MIME/format and existing RM-135 bounded parser;
10. `MAPPING_COMPATIBILITY` — required mappings on actual bounded sample;
11. `FINALIZE` — recompute current binding, close/clean resources, atomic evidence write.

Empty valid response/listing returns `DEGRADED/INSUFFICIENT_SAMPLE`; no test data/defaults are
invented. No tender/document/checkpoint/dedup/history/DB mutation occurs.

## 11. Lifecycle, read model и enablement

Configuration lifecycle remains `CONNECTION_TEST_REQUIRED`; verification is separate state:

```text
UNVERIFIED -> CHECKING -> VERIFIED (fresh exact evidence)
                    |-> FAILED/BLOCKED/CANCELLED
VERIFIED -> STALE on TTL/binding/credential/policy change
```

Successful check:

- exposes `READY_FOR_ENABLEMENT` in read model;
- does not write `enabled=true`, profile or schedule;
- enables a separate user enable action;
- normal admission still requires explicit persisted enablement plus fresh exact evidence.

Canonical admission is recalculated in one service and reused by manager, unified search/profile,
scheduler callback, `CollectorRunSession` and manual factory construction. Hand-edited
`enabled=true`, UI status text or tampered health JSON cannot bypass it. Evidence is rechecked
immediately before runtime creation.

Built-in provider enablement/check paths and current health monitor remain unchanged.

## 12. Concurrency, cancellation и resource policy

- single-flight per provider;
- global maximum 2 simultaneous manual checks;
- code-owned cooldown 5 seconds after completion; typed `ALREADY_RUNNING`/`RATE_LIMITED`;
- total deadline includes DNS/connect/TLS/auth/protocol/parse and any transient retry;
- at most 2 attempts only for explicitly transient connect/read categories; auth/TLS/policy/parse
  are never retried; `429` does not trigger aggressive retry;
- `CollectorCancellationToken` checked between stages and during I/O;
- cancel closes sockets/tasks/buffers and returns `CANCELLED` without replacing previous evidence;
- completion recomputes binding; changed spec/protocol/credential rejects stale write;
- UI worker owns token, exposes Cancel and clears busy state on success/failure/cancel/close;
- startup/save/load/compile/dialog-open perform no probe.

## 13. Threat model

Tests cover literal/encoded/IPv4-mapped IPv6, loopback/private/link-local/CGNAT/multicast/reserved/
metadata targets, mixed DNS answers, rebinding, redirect and FTP passive bounce; unsafe ports,
userinfo/CRLF/bidi, auth exfiltration cross-origin, environment proxy, TLS wrong-host/self-signed/
downgrade, FTP mutation/traversal/glob/recursion, XXE/XInclude, decompression/JSON/XML/listing bombs,
retry/redirect loops, stale completion, clock rollback, tampered evidence, raw payload/secret leaks,
cancel leaks, startup probe and admission bypass.

Automated tests use fakes and controlled local servers only. Public sites, real credentials and legacy
tester are never invoked automatically.

## 14. Expected-red boundary

Before production implementation add focused modules for:

- immutable result/stage/binding/status semantics and safe serialization;
- target/DNS/redirect/TLS/FTP passive policy;
- credential descriptors/runtime resolution/invalidation;
- schema v6 and health evidence schema v2 migration/TTL/stale writes;
- API/RSS/FTP/FTPS protocol probes and existing RM-135 mapping compatibility;
- single-flight/cooldown/cancellation/resource cleanup;
- manager/read model/UI confirmation/progress/cancel/no-auto-enable;
- profile/scheduler/unified/run-session/factory canonical admission;
- legacy byte preservation/no tester/keyring guessing/startup network.

Accepted red may contain only missing RM-136 symbols/behavior and is committed separately.

### Accepted expected-red evidence

После docs-only commit `f4bb93a` добавлены только 12 контрактных test modules из плана. Exact
focused command завершился ожидаемо: `12 errors during collection in 6.03s`. Все ошибки относятся
исключительно к отсутствующим RM-136 boundaries:

- modules `manual_provider_health` и `manual_probe_transport`;
- symbols `ManualProviderFtpsMode`, `manual_credential_descriptors` и
  `safe_manual_health_error_message`.

Существующий production-код до этого red-run не изменялся; неожиданных import/runtime failures нет.

## 15. Selected extension points and allowed files

New justified modules:

- `app/tenders/collector/manual_provider_health.py` — domain/application service, binding/admission;
- `app/tenders/collector/manual_probe_transport.py` — narrow pinned resolver/transport ports and
  read-only probes.

Existing owners allowed to change:

- `manual_provider_protocol.py`, `manual_provider_registration.py`, `manual_adapter.py`;
- `provider_settings.py`, `provider_control.py`, `provider_credentials.py`;
- `async_provider_factory.py`, `run_session.py`, `network_runtime.py`, collector public exports;
- existing provider manager dialog/controller and focused tests/docs.

`pyproject.toml`/workflow меняются только если required quality contour objectively needs the new
typed modules; dependency addition is not expected.

## 16. Unchanged and excluded contracts

Unchanged: built-in provider IDs/adapters/factories, EIS/MOS checkpoints, one in-run health monitor,
Collector SQLite schema v14, `UnifiedTender`, normalizer/dedup/provenance, RM-107 score/recommendation
and absolute critical stop-factor, AI, legacy `user_settings.json`/`ManualConnectorTester`, public
canary opt-in behavior.

Excluded: full Collector orchestration inside the check, tender/document persistence, background/
periodic monitoring, scheduler health polling, alerts/SLA, automatic enable/profile/schedule change,
arbitrary methods/headers/bodies/cookies/FTP commands, scraping/bypass, circuit-breaker redesign,
new vault/catalog/settings/Collector/health monitor and RM-137+.

## 17. Audit decision

**ACCEPTED FOR DOCS-ONLY AUDIT COMMIT.** RM-136 is implementable by extending the existing health
repository, credential façade, manager, manual adapter/factory and admission seams. One one-shot
application service and one narrowly scoped pinned manual transport are justified by missing
revision-aware evidence, SSRF/DNS enforcement and canonical FTP/FTPS support. Production changes
remain blocked until this audit and implementation plan are committed, followed by separate accepted
expected-red evidence.
