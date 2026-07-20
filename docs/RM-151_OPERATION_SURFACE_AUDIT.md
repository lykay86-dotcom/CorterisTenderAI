# RM-151 operation, notification and feedback surface audit

## Audit verdict

Baseline `c07773772a360d9bd6f7a3da0b18f44c6315d725` has one accepted search lifecycle owner,
one scheduler/notification persistence owner, one modern shell/router, one crash/report/support
owner set and one workflow health lifecycle. RM-151 must adapt these owners; it must not replace
them with a task framework, event bus, second notification store or second crash database.

The current source contains 17 worker classes, 11 `QRunnable` references, one `QThread`
construction, two `QThreadPool` constructions, six `QTimer` constructions, 134 `QMessageBox`
calls, 13 status-bar `showMessage` calls and 14 `setHtml` calls. The audit found 77 direct
`str(exc/error/exception)` expressions in `app/`; these are candidates, not 77 independent
operation owners. Every user-visible operation group is classified below.

## Entry gate and method

- RM-150 feature PR #108 merged as `8d6640691ca3e0fc6a22d7e6dd2d732955e0eedd`.
- Exact feature merge-SHA run `29708473745` succeeded on Windows Python 3.12 and 3.13.
- RM-150 docs-only PR #109 merged as this baseline; post-closeout run `29708921882` succeeded
  with exact `headSha=c07773772a360d9bd6f7a3da0b18f44c6315d725`.
- Canonical docs make RM-151 the only `IN PROGRESS` stage and keep RM-152–RM-200 `PLANNED`.
- Inventory searched worker/thread/timer/future/progress/cancel APIs, message/status/rich-text
  APIs, raw exceptions, crash/support/scheduler/backup/recovery owners, signal wiring and tests.
- Existing RM-140, RM-142, RM-143, RM-144, RM-148, RM-149 and RM-150 contracts were treated as
  immutable owner boundaries.

Risk is `O1` critical, `O2` high or `O3` medium. Decision is `keep`, `adapt` or `migrate` at the
presentation-contract boundary; it does not authorize moving business work or adding threads.

## Identity, owner and execution inventory

| ID | Surface / kind / journey | Trigger and exact subject identity | Business owner | Lifecycle owner / execution |
|---|---|---|---|---|
| OPS001 | manual collector search / `tender_search` / J07 | unified panel, collector dialog, profile action; profile ID + run ID + generation | Collector session/search runtime | `TenderSearchUiController`; owned `QThreadPool`/`QRunnable` |
| OPS002 | scheduled collector run / `scheduled_search` / J08 | timer/startup/run-now; schedule profile ID + run ID | `CollectorScheduler` + collector session | `TenderCollectorSchedulerUiController` timer delegating to search controller |
| OPS003 | notification center / `notification_history` / J08 | top bar, `Ctrl+Shift+N`, menu; notification ID/run ID | `CollectorNotificationService` | scheduler UI controller + existing dialog; synchronous capped JSON repository |
| OPS004 | source monitoring / `source_monitoring` / J08 | collector terminal transition; provider ID + evidence ID | source monitoring service | scheduler UI controller publication; synchronous notification projection |
| OPS005 | Dashboard refresh / `dashboard_refresh` / J01/J03 | startup/timer/button; dashboard generation | dashboard snapshot builder + two repositories | `DashboardController`; one `QThread` + auto-refresh timer |
| OPS006 | analytics refresh/export / `analytics_refresh` / J09 | route filters/refresh/export; immutable analytics query/fingerprint | analytics application/service | analytics page/controller; synchronous bounded service/export |
| OPS007 | document download / `tender_documents` / J09 | explicit action; RM-149 registry key + document request | document service/storage | `TenderSearchUiController`; per-key `QRunnable` |
| OPS008 | requirements analysis / `requirements_analysis` / J09 | explicit action; registry key | requirements analysis service | `TenderSearchUiController`; per-key `QRunnable` |
| OPS009 | full analysis / `full_analysis` / J09/J10 | explicit action/cancel; registry key | full-analysis service/orchestrator | `TenderSearchUiController`; cancellable per-key `QRunnable` |
| OPS010 | AI recheck / `ai_recheck` / J10 | explicit recheck; registry key | existing AI orchestrator | `TenderSearchUiController`; per-key `QRunnable` |
| OPS011 | participation score / `participation_score` / J09 | explicit action; registry key | approved score/decision service | `TenderSearchUiController`; per-key `QRunnable` |
| OPS012 | provider connection checks / `provider_health` / J06/J10 | one/all explicit check; provider IDs | provider manager/manual health owners | `TenderSearchUiController`; cancellable `QRunnable` |
| OPS013 | workflow system health / `system_health` / J13 | startup/timer/button; workflow DB identity | `SystemHealthService`/monitor | `BusinessWorkflowPage` + `SystemHealthMonitor`; owned pool/timers |
| OPS014 | database diagnostics/recovery / `database_recovery` / J13/J15 | explicit health/recover; DB fingerprint + backup identity | diagnostics/maintenance/recovery services | workflow page/dialog; currently synchronous |
| OPS015 | workflow backup/restore / `workflow_backup` / J13 | explicit create/restore; exact backup path identity + revision | backup service/catalog/maintenance | workflow page/backup dialog; synchronous with confirmation |
| OPS016 | automatic backup / `automatic_backup` / J13 | timer/manual-now; workflow DB generation | automatic backup service/settings | workflow page timer; synchronous owner call |
| OPS017 | workflow Excel import / `workflow_import` / J12/J13 | file picker/preview/confirm; selected source + preview fingerprint | workflow importer/repository | workflow page/dialog; synchronous |
| OPS018 | workflow Excel export/template / `workflow_export` / J12 | explicit export/save; visible snapshot + destination | export/template services | workflow page; synchronous |
| OPS019 | legacy tender-workspace DB tools / `legacy_database_maintenance` / J13/J15 | explicit backup/restore/optimize/export; DB/backup identity | existing DB maintenance services | `TenderWorkspacePage`; synchronous compatibility surface |
| OPS020 | legacy imports/price/catalog/docs generation / `legacy_file_operation` / J12/J13 | explicit file/action; selected tender/file/catalog identity | existing import/catalog/document services | `TenderWorkspacePage`; synchronous compatibility surface |
| OPS021 | crash capture/report dialog / `crash_capture` / J02 | unhandled failure/launch; crash report identity | crash reporting service | bootstrap `QtCrashBridge`/dialog; signal-driven |
| OPS022 | crash report center / `crash_report_history` / J02 | health center/menu; report identity/path fingerprint | `CrashReportCatalogService` | existing dialog; synchronous list/copy/delete |
| OPS023 | diagnostic support bundle / `support_bundle` / J02/J13 | explicit export; synthetic bundle request/report selection | `DiagnosticSupportBundleService` | crash/system-health/workflow surfaces; synchronous |
| OPS024 | launch guard/safe mode / `startup_recovery` / J02/J15 | startup/repeated crash; launch-state identity | `LaunchGuardService` + DB/disk checks | bootstrap/safe-mode dialog; synchronous startup boundary |
| OPS025 | provider settings/credentials/discovery / `provider_configuration` / J06/J10 | explicit edit/save/test; provider stable ID | provider config, credential and discovery owners | existing controller/dialogs; mixed sync + OPS012 check |
| OPS026 | financial snapshot/export/recovery / `financial_projection` / J13 | workflow/analytics export and restore; RM-148 record/snapshot ID | `app.financial` + workflow repository | existing workflow/analytics surfaces; synchronous bounded |
| OPS027 | table load/filter/sort/export / `table_projection` / J07/J09/J12 | page changes/export; RM-150 surface/row/snapshot identity | existing page/service owners | RM-150 model/widget adapters; in-memory synchronous |
| OPS028 | shell startup/shutdown / `application_lifecycle` / J01/J16 | process start/close; shell generation | bootstrap/runtime composition | modern shell + RM-144 page/controller shutdown protocols |
| OPS029 | capability/catalog/commercial editors / `bounded_editor_operation` / other | explicit load/save/calculate; catalog or registry identity | existing domain services | modal dialogs; bounded synchronous |
| OPS030 | ordinary CRUD/status changes / `bounded_mutation` / J12 | explicit confirmed action; stable workflow/registry ID | repositories/services | owning page/dialog; bounded synchronous |

## State, feedback, safety and decision inventory

| ID | Current states/messages | Raw-error and diagnostics path | Cancel / retry / close and late guard | Persistence | Risk / decision / regression evidence |
|---|---|---|---|---|---|
| OPS001 | RM-140 idle/queued/running/cancelling/terminal/closed; panel/dialog/status | safe collector error mapper exists; run evidence persists | confirmed cancel, retry new generation, generation/revision/close guard | run/registry history | O1 / adapt shared episode projection / RM-140 lifecycle, redaction, shutdown tests |
| OPS002 | scheduled/started/result/failure; status + notifications | failure text may reach `for_failure(message)` | admission guarded; retry is new run; controller shutdown stops timer | schedule JSON + notifications | O2 / adapt / scheduler controller tests |
| OPS003 | empty/list/read/unread; table + badge | persisted title/message accepted as plain strings; no correlation/action identity | close/reopen dialog; no destructive retry | schema-v1 capped atomic JSON | O1 / migrate envelope adapter without schema change / notification tests |
| OPS004 | degraded/recovered/stale/invalid | typed templates already safe | duplicate evidence IDs dedupe; no cancel | notifications JSON | O2 / keep typed templates, adapt envelope / RM-139 notification tests |
| OPS005 | loading/ready/partial/error/stale | repository exceptions interpolated into source/user messages | duplicate refresh rejected; thread cleanup exists, generation contract incomplete | none | O1 / adapt safe feedback + episode/late guard / dashboard background tests |
| OPS006 | loading/ready/partial/conflicted/stale/error/too-large | typed analytics states; export errors at UI boundary | no cancel; bounded 10k; close owned by page | none | O3 / keep domain states, adapt feedback only / RM-147 tests |
| OPS007 | started/success/failure | worker emits `str(exc)` to UI; document artifact remains owned | same-key duplicate rejected; no explicit cancel; dialogs forgotten on destroy | document storage | O1 / migrate worker projection / document UI tests |
| OPS008 | started/success/failure | worker emits `str(exc)` | retry explicit; same-key guard; destroy bookkeeping | analysis repository | O1 / migrate / requirement UI tests |
| OPS009 | running/progress/success/failure/cancel | worker emits raw exception; typed service progress exists | cancellable; owner confirmation/late generation must be formalized | analysis/decision repositories | O1 / migrate / full-analysis action/dialog tests |
| OPS010 | started/success/failure | error signal is plain string; no secret readback allowed | retry explicit new worker; per-key active map | AI repository | O1 / migrate / AI recheck/offline tests |
| OPS011 | started/success/failure | worker emits `str(exc)`; score must remain deterministic | retry explicit; no cancel; per-key active map | persisted approved score | O1 / migrate feedback only / score UI/runtime tests |
| OPS012 | running/success/failure | `safe_manual_health_error_message` exists for boundary | cancellable/abandon on shutdown; active-worker guard | health evidence | O2 / adapt common reason/episode / provider-control tests |
| OPS013 | open/running/closing/closed + health snapshot | failure message may contain raw exception | RM-144 owned pool, sender/lifecycle guard, idempotent bounded shutdown | journal/health evidence | O1 / adapt projection, preserve lifecycle / RM-144 + health tests |
| OPS014 | healthy/unhealthy/recovery available/running/result | multiple `QMessageBox(..., str(exc))`; diagnostics evidence exists | destructive recovery confirmed; sync close only after return | DB + backup evidence | O1 / adapt safe feedback; no threading / recovery/health tests |
| OPS015 | list/inspect/create/restore/failure | raw path/exception in dialogs and journal details | exact path/revision revalidated by RM-150; confirmation required | backup files/catalog/journal | O1 / adapt / backup-center and RM-150 tests |
| OPS016 | due/running/success/failure/skipped | raw exception recorded as journal details/message | timer stopped by RM-144; retry is new check | settings/backups/journal | O2 / adapt / auto-backup tests |
| OPS017 | selected/preview/valid/warning/imported/failure | raw exception in modal; source path visible | explicit preview/confirm; no cancel during sync span | repository + safety artifacts | O1 / adapt; characterize before any threading / import tests |
| OPS018 | selected/exported/failure | raw exception/path in modal | visible snapshot fixed; new attempt on retry | output artifact | O2 / adapt safe feedback / export tests |
| OPS019 | healthy/result/failure; generic modals | direct `str(exc)` and absolute paths | restore confirmed; no late callback because sync | DB/backups/output | O1 / adapt compatibility boundary / DB migration/backup tests |
| OPS020 | selected/result/failure | direct `str(exc)` and output paths | synchronous; retry repeats explicit action | imported/generated artifacts | O2 / adapt safety only / legacy workspace tests |
| OPS021 | captured/dialog/details/copied/bundled | intentionally exposes scrubbed traceback and report path; raw bundle failure | dialog close does not delete artifact | crash report files | O1 / adapt safe summary while preserving explicit diagnostic details / crash tests |
| OPS022 | empty/list/details/copied/deleted/error | scrubbed traceback is explicit diagnostic view; operations use `str(exc)` modals | delete exact report with confirmation; selection identity exists | crash reports | O1 / adapt correlation/retrieval / catalog/center tests |
| OPS023 | creating/created/inspection/failure | internal bundle may retain policy-approved evidence; UI leaks raw exception/path | no cancel; retry explicit; artifact must survive notification dismiss | support bundle file | O1 / adapt correlation + safe label / support-bundle tests |
| OPS024 | normal/safe-mode/check/recovery/error/exit | `str(exc)` stored in check details; path risk | recovery explicit; process lifecycle owns close | launch state/crash evidence | O1 / adapt / safe-mode/bootstrap tests |
| OPS025 | missing/configured/checking/saved/error | many owners already return safe messages; validation has raw fallback | cancel only connection checks; credential loaded only by owner | config/keyring/health evidence | O1 / adapt common projection, no secret readback / RM-131–136 tests |
| OPS026 | exact/partial/conflicted/error/exported | RM-148 typed safe states; file error remains UI boundary | sync, bounded, exact snapshot; retry explicit | workflow schema v3/artifacts | O2 / keep numeric owner, adapt feedback / RM-148 tests |
| OPS027 | loading/empty/error/partial/ready | no repository I/O in model; export boundary may fail | exact selection/action token; no background cancellation | none | O3 / keep; use identities for notification actions / RM-150 tests |
| OPS028 | starting/running/closing/closed | bootstrap/crash boundary owns diagnostics | RM-144 ordered shutdown and late guards | launch/crash state | O1 / adapt only shared presentation / bootstrap/frozen/lifecycle tests |
| OPS029 | idle/result/failure | direct `str(exc)` in several modal editors | sync; explicit retry; exact domain identity varies | existing domain stores | O2 / adapt safe projection; no episode persistence / dialog tests |
| OPS030 | idle/confirmed/success/failure | raw exception in CRUD dialogs | bounded sync, exact ID, destructive confirmations | existing repositories | O2 / keep lifecycle, adapt static safe feedback helper / workflow tests |

## Existing owner findings

1. `TenderSearchUiController` is the only production collector/document/analysis/score worker
   owner. RM-151 may add episode adapters but not worker services.
2. `TenderCollectorSchedulerUiController` constructs the only
   `CollectorNotificationRepository`. Top bar and `Ctrl+Shift+N` already route through RM-142 to
   its `notifications_action`; the prepared-TZ “message-box stub” is no longer present on the
   canonical baseline.
3. `CollectorNotificationRepository` is schema v1, atomic and capped at 200. It silently treats
   damaged JSON as empty and has read-all/clear but no per-item dismiss/action/correlation. RM-151
   will wrap current storage compatibly; any schema change is a stop condition.
4. RM-144 already owns workflow monitor/page/shell shutdown. Shared transitions must reject late
   feedback but cannot replace its pool/timer cleanup.
5. Crash reports and support bundles intentionally retain actionable technical evidence under
   their existing privacy policy. Safe user projection must not erase or rewrite those artifacts.
6. Most workflow/file operations are synchronous. RM-151 will not thread them without separate
   thread-safety evidence; it can still provide honest busy/terminal feedback and safe errors.

## Default implementation slice

The shared Qt-free slice will cover immutable episodes/transitions/progress/capabilities, safe
allowlist-first feedback, opaque diagnostic correlation records, notification envelopes/dedupe and
announcement coalescing. Representative adapters will cover OPS001, OPS003, OPS005, OPS007–OPS013,
OPS015, OPS021–OPS024 and OPS028. Other `adapt` sites use the same safe projection helper/static
guard without acquiring a second lifecycle owner. OPS006/OPS026/OPS027 remain domain-contract
`keep` sites.

## No-schema / no-dependency decision

No new dependency, database, notification schema migration, network/AI call or telemetry path is
required. Persistence compatibility is through an adapter over legacy schema-v1 notifications;
unknown/damaged storage behavior is characterized and not silently redefined in the first
production commit. If per-item dismiss/correlation persistence cannot be represented without a
schema revision, that persistence is deferred and documented rather than implemented implicitly.

