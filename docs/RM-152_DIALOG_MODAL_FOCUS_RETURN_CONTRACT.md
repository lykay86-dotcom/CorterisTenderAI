# RM-152 dialog, modal, and focus-return contract

Baseline: `9cb37b9a83f50ac9f8f8e34fdeb582c2ed76e257`

## Owner model

Each existing controller/dialog remains the only owner of execution, validation, confirmation,
close, and result. RM-152 adds a bounded local focus-origin/initial-focus convention; it does not
introduce a modal service, global event filter, second lifecycle, or callback registry.

An origin token contains stable route/surface/control and optional RM-149/RM-150 subject identity.
It contains no QWidget in persisted context, row index, display title as identity, secret, path, or
raw exception. A short-lived local weak QObject reference may be used only to resolve the same live
control and must be rejected when destroyed/hidden/disabled/off-route.

## Common policy

Every dialog defines title/role, modal/modeless ownership, initial focus, default action, Escape,
close/X and Alt+F4, validation focus, nested-dialog behavior, return origin/fallback, accessible
summary, and supported resizable minimum.

- Initial focus: first invalid field, otherwise first logical input/result collection/safe action.
- Ordinary Save/OK may be default when non-destructive and validation is explicit.
- Archive/delete/restore/import/recovery/credential deletion is never default.
- Destructive confirmation names the freshly validated safe subject; `No`/`Cancel` is default.
- Escape rejects/closes and never confirms destructive work.
- Close/X and Alt+F4 use the same unsaved/busy owner policy as visible Close/Cancel.
- Generic progress never opens a modal. Blocking confirmation remains owner-specific.
- Background update/notification does not activate a dialog or steal focus.
- After close, exact origin wins; removed exact identity returns to table/status container with no
  adjacent selection; stale route uses route fallback.

## Current inventory and decisions

There are 30 direct `QDialog` subclasses and 90 direct message-box calls. Initial `resize()` values
are preferences; growing content dialogs remain resizable and fit the RM-152 matrix.

| Dialog/surface ID | Journeys | Initial/default/Escape contract | Return/fallback | Decision |
|---|---|---|---|---|
| `crash.report` `CrashReportDialog` | J02,J15 | safe summary/first recovery; safe Close; Escape follows crash policy | invoking crash/safe-mode action or app exit owner | fix semantics/size/focus; keep artifact owner |
| `crash.center` `CrashReportCenterDialog` | J02,J15 | report list; Close default; destructive delete confirmation safe | exact report row, else list/status | fix exact row return and size |
| `safe.mode` `SafeModeDialog` | J02,J15 | diagnostic summary/safe action; Close app policy explicit | launch/safe-mode lifecycle fallback | fix first focus/HC/DPI; keep launch guard |
| `catalog.matching` `MatchingCatalogDialog` | J09,J10 | catalog table/filter; non-destructive Save only after validation | exact catalog row/action | adapt focus; raw feedback separately guarded |
| `aggregator.discovery` `AggregatorDiscoveryDialog` | J06 | result collection; Close | invoking provider action | adapt metadata/return |
| `company.capability` `CompanyCapabilityDialog` | J06,J09 | first invalid/first field; Save/Close | invoking settings action | adapt relations/validation return |
| `commercial.estimate` `CommercialEstimatorDialog` | J09,J12 | estimate table/input; no destructive default | exact tender/action | adapt identity/return/layout |
| `provider.manager` `TenderProviderManagerDialog` | J06,J10 | provider table; Close | invoking source action, exact provider row | fix semantics/selection return |
| `provider.registration` `ManualProviderRegistrationDialog` | J06 | first field; Save/Cancel | provider manager/new-source action | adapt labels/first-invalid |
| `provider.protocol` `ManualProviderProtocolDialog` | J06 | first field; Save/Cancel; delete never default | exact provider/protocol row | fix destructive/default/return guard |
| `provider.adapter` `ManualAdapterWizardDialog` | J06 | first field; Save/Cancel | exact provider/adapter row | adapt labels/resize |
| `provider.configuration` `TenderProviderConfigurationDialog` | J06 | first editable field; Save disabled if read-only | exact provider row | adapt disabled reason/return |
| `provider.credential` `ProviderCredentialsDialog` | J06,J10 | password input; Save default; Delete not default; Escape rejects | invoking credential action; no secret retained | fix explicit return; keep no-readback |
| `search.profiles` `TenderSearchProfilesDialog` | J05 | profile list/empty recovery; Close | exact profile/action | fix list semantics/return |
| `search.results` `TenderSearchResultsDialog` | J07,J09 | result table/empty close; Close | exact run/profile/query/result row | adapt RM-150 identity/focus |
| `collector.run` `TenderCollectorDialog` | J07 | operation status/first available action; Close per RM-140 | invoking search action | adapt RM-151 state/announcement/no steal |
| `collector.schedule` `TenderCollectorScheduleDialog` | J08 | schedule form/list; Close | scheduler action/exact profile | adapt labels/return/layout |
| `collector.notifications` `TenderCollectorNotificationsDialog` | J08 | first unread/first row/empty Close | topbar or canonical shortcut origin | fix same target, removed-row fallback, semantics |
| `tender.registry` `TenderRegistryDialog` | J09,J11 | registry table; Close | invoking registry action; exact selected identity | adapt RM-150 return; keep archive safe default |
| `tender.documents` `TenderDocumentsDialog` | J09 | document table/status; Close | exact RM-149 detail action | adapt name/state/return/layout |
| `tender.requirements` `TenderRequirementAnalysisDialog` | J09,J11 | findings/critical summary; Close | exact detail action/evidence identity | adapt tab/table order and size |
| `tender.verification` `TenderVerificationDialog` | J11 | conflict/evidence table; Close; resolution confirmation safe | exact verification action/critical banner | fix critical-first semantics/return/strict heights |
| `tender.full_analysis` `TenderFullAnalysisDialog` | J09,J10 | state/summary; Close; rerun confirmation `No` default | exact detail analysis action | adapt tabs/tables/RM-151 updates |
| `tender.score` `TenderParticipationScoreDialog` | J09 | critical/approved decision summary; Close | exact detail decision action | keep RM-107 order; adapt reading/focus |
| `workflow.record` `BusinessRecordDialog` | J12 | first invalid/first field; Save/Cancel | exact record/new action | adapt relations and exact record return |
| `workflow.import` `WorkflowImportPreviewDialog` | J12,J13 | preview/warnings; Import not accidental default; Cancel | import action/table; no mutation on cancel | fix destructive semantics/viewport |
| `workflow.recovery` `WorkflowDatabaseRecoveryDialog` | J13,J15 | diagnosis/safe recovery; Close without changes default | health/data action | fix future-schema safe default/focus |
| `workflow.backup.settings` `WorkflowBackupSettingsDialog` | J13 | first field; Save/Cancel | data menu/settings action | adapt labels/resize |
| `workflow.health` `SystemHealthCenterDialog` | J13,J15 | health summary/table; Close | health badge/data menu | adapt safe actions/return/layout |
| `workflow.backups` `WorkflowBackupCenterDialog` | J13,J15 | backup table/empty action; Close; restore/delete safe default | exact backup row, else table/status | fix exact return and small viewport |

## Message-box rules

Existing `QMessageBox.question/warning` confirmations remain with their owner. Tests inspect
archive/delete/restore/import/recovery/credential cases and require:

- validated exact target in safe text where necessary;
- destructive button not default and Escape result non-destructive;
- no keyboard shortcut bypass;
- stale revision/identity returns safe failure without mutation;
- safe summary contains no secret/path/query/raw exception;
- focus returns to logical action/container after response.

Information/error message boxes do not become an operation-notification transport. RM-151
in-surface/status/notification routing remains authoritative.

## Representative baseline evidence

The credential dialog with synthetic state focuses `ProviderCredentialInput`; Qt creates the
correct form-label buddy; Save is default, Delete is not; Escape rejects and clears input. The
offscreen parent has no focused return control after rejection. Expected-red freezes that missing
return behavior and implementation must return to `CredentialOrigin` or its stable fallback.

## Nested and modeless dialogs

- Capture a new child origin inside the parent, not the shell origin.
- Closing child restores parent action if parent remains current/valid.
- Closing parent invalidates all child origins before late callbacks.
- A modeless dialog whose route/subject is stale cannot restore into a different current entity.
- Table/detail nested actions use RM-150 row and RM-149 action focus tokens.
- No nested close selects first/next/previous entity as convenience.

## DPI/native evidence

At every required scale, dialogs keep title, content, primary/safe cancel/recovery controls,
validation text, and focus ring reachable. Tables/text areas scroll; dialogs with growing content
are resizable. Narrator announces title, role, summary, initial control, default/safe action,
validation, and close result without confidential data. Native cells remain `NOT_EXECUTED` until
actually observed.
