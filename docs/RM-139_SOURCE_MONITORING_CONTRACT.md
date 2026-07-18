# RM-139 — контракт мониторинга источников

Contract/policy version: `source-monitoring-v1`  
Статус: implementation target

## Boundary

Monitoring — pure/read-only projection существующих enablement, explicit health, operational run,
circuit, checkpoint, schedule и C19 facts. Projection не является новым source of truth, не пишет
JSON/SQLite, не читает secret и не выполняет DNS/HTTP/FTP.

## Snapshot

`SourceMonitoringSnapshot` immutable и содержит aware UTC `observed_at`, строго возрастающую
`revision`, `policy_version` и sources в deterministic provider order. Provider IDs unique,
trimmed/casefolded.

Каждый `SourceMonitoringState` сохраняет отдельные dimensions:

1. readiness: enabled, runnable, configured;
2. connection: explicit health status, checked/success time, freshness;
3. operational: latest accepted Collector outcome, last run/success, circuit/cooldown;
4. checkpoint: supported/present/scope/update/freshness;
5. verification: latest C19 status, evidence identity/age и `qualifies_as_working`;
6. schedule: active membership и next due;
7. attention: derived closed level и ordered safe reasons.

Один boolean `working` запрещён. Connection success и successful Collector outcome никогда не
повышают C19 до `WORKING`.

## Time and freshness

Все output timestamps — aware UTC. Naive, malformed или future beyond 5-minute skew становится
`INVALID/UNKNOWN` и не участвует в success/cooldown arithmetic.

- built-in connection TTL: 24h;
- manual evidence: exact `valid_until`, boundary current при `observed_at < valid_until`, stale при
  `observed_at >= valid_until`;
- active checkpoint TTL: clamp(`2 * schedule interval + 5m`, 1h, 48h);
- inactive checkpoint TTL: 24h;
- C19 TTL: 30d.

Exact boundary считается expired. Unsupported checkpoint имеет `NOT_APPLICABLE`, а не warning.

## Operational history and circuit

Operational evidence читается из existing `collector_runs`/`collector_run_providers`.
`success/empty` сбрасывают consecutive failures; `failed/timed_out` с remote/network/timeout safe
codes увеличивают их; `cancelled/unsupported/skipped/circuit_open` не увеличивают и не превращают
предыдущий success в failure. `not_configured` остаётся отдельным admission state.

Existing `ProviderHealthPolicy` определяет threshold/cooldown. Hydration переводит aware UTC
cooldown boundary в bounded monotonic remaining duration. Expired cooldown восстанавливается как
`DEGRADED`, не `AVAILABLE`. Success только из accepted terminal outcome. Reprocessing same
`(run_id, provider_id, status)` idempotent, late RM-138 results отсутствуют в accepted persisted rows.

## Attention priority

Closed order: `CRITICAL > WARNING > INFO > NONE`. Reasons deterministic и ordered:

1. corrupt/invalid/future evidence;
2. disabled/not configured/not runnable;
3. unavailable/cooldown/failed operational state;
4. unavailable/stale connection state;
5. stale checkpoint;
6. failed/stale/unverified C19;
7. missing/unknown evidence.

Reason содержит только stable code и фиксированное русское bounded сообщение. Raw exception,
traceback, endpoint, URL, credential, response body, document/tender payload и private path
запрещены.

## Notifications

Initial snapshot и repeated refresh не уведомляют. Significant transitions:

- operational available → degraded/cooldown/unavailable;
- recovery degraded/cooldown/unavailable → available;
- checkpoint current → stale;
- qualifying C19 working → failed/unverified/stale;
- invalid/corrupt evidence warning.

ID = stable provider ID + transition kind + new evidence identity. Existing repository deduplicates
ID and keeps capped/unread semantics. `notify_failures` gates degradation/warning/recovery events.
C19 остаётся отдельным transition от connection health.

## Operations and UI

Passive refresh only reads. Explicit check uses existing `_ProviderCheckWorker` and manager. While
the sole Collector worker is active, explicit check is rejected. Manual/scheduled/freshness runs
share the existing `_collector_worker` and busy callback.

`TenderProviderManagerDialog` only renders supplied immutable states. It shows connection,
operational/circuit, checkpoint, C19, last successful collection, observed time/freshness and safe
attention separately. Qt does not calculate TTL, transition IDs, circuit admission or reason
priority. Opening/refreshing the dialog performs no network call.

## Compatibility and authority

No DB/JSON schema change. Existing provider IDs, settings, health/manual evidence, schedule,
notifications, C19, Collector results and public APIs remain readable. RM-137 normalization/dedup,
RM-138 cancellation/terminal semantics, RM-107 score/recommendation/hard exclusion and absolute
critical stop-factor priority are unchanged. AI has no monitoring or decision authority.
