# RM-130 — implementation plan сохранённых поисковых профилей

Дата: 16 июля 2026 года.
Baseline: `9dd8e9cde2768840066e024dc607cc980570d048`.
Ветка: `feat/rm-130-saved-search-profiles`.

План основан на `docs/RM-130_AUDIT.md`, D-02/D-06/D-09 из RM-126, завершённых RM-128/RM-129 и
canonical Definition of Done. Scope RM-131+ не включён.

## 1. Обязательный порядок

1. Зафиксировать audit и этот plan отдельным docs-only commit.
2. Добавить пять ownership-focused expected-red modules без production changes.
3. Запустить exact red contour; failures допустимы только по отсутствующим RM-130 symbols/behavior.
4. Добавить exact failure evidence в audit и зафиксировать отдельным test commit.
5. Реализовать pure schema/domain contract.
6. Реализовать repository load/migration/rollback внутри existing owner.
7. Формализовать current unified execution modes.
8. Адаптировать existing editor/dialog без второго UI workflow.
9. Запустить focused, neighbor и full workflow-equivalent gates; записать exact evidence.
10. Подготовить feature PR; не объявлять RM-130 `DONE` до merge, exact merge-SHA Windows gate и
    отдельного docs-only closeout.

## 2. Pure domain/schema changes

`app/tenders/search_profiles.py`:

- add frozen string enum `SearchProfileRuntimeQueryPolicy` with the sole current value
  `REPLACE_KEYWORDS_IF_PRESENT`;
- add `runtime_query_policy` to frozen/slotted `TenderSearchProfile`;
- normalize string collections and provider IDs deterministically, preserving first-seen display text;
- keep finite non-negative `Decimal`, min/max, explicit currency, page and period guards;
- validate nonempty timestamps as aware ISO and never assign UTC to naive caller input;
- keep flat `to_dict()` shape and add the policy field;
- add pure optional Decimal text parser/formatter for UI reuse without Qt/float;
- keep legacy fields and exact query/filter semantics unchanged.

Repository strict decoders, rather than a second model, enforce persisted v1/v2 field shapes. Direct
compatibility construction remains available where it does not undermine persisted safety.

## 3. Typed load and repository compatibility

`app/tenders/search_profile_repository.py` adds:

- `SearchProfileCatalogLoadStatus`;
- frozen `SearchProfileCatalogLoadResult`;
- bounded `SearchProfileCatalogMutationError`;
- public `load_result()`;
- internal strict envelope/profile decoders and pure v1 migration;
- a current-v2 atomic writer.

Compatibility API behavior:

| API | Missing | Valid v1 | Current v2 | Corrupt | Future |
|---|---|---|---|---|---|
| `load_result()` | built-ins, `MISSING`, no write | profiles, `MIGRATED_V1`, no write | profiles, `CURRENT`, no write | empty + quarantine path, no target rewrite | empty, no write |
| `initialize()` | explicit v2 built-in write | no write | no write | no rewrite | no rewrite |
| `list/get` | in-memory built-ins | migrated in memory | current | empty/not found | empty/not found |
| mutation | creates v2 | backup + mutation + v2 replace | atomic v2 replace | blocked | blocked |

Mutation reads and validates again while holding the existing `RLock`. It never applies a mutation to
stale in-memory state.

## 4. V1 → v2 migration and rollback

For a valid v1 mutation:

1. capture exact source bytes;
2. decode the exact snapshot as v1;
3. create a sibling timestamped byte-for-byte backup using exclusive creation;
4. apply mutation to the full canonical in-memory catalog;
5. serialize schema v2 entirely in memory;
6. write sibling `.tmp` UTF-8 JSON;
7. atomically `Path.replace()` the target;
8. remove temp in `finally`;
9. on failure keep original and backup and surface bounded error.

V1 decimal strings remain exact. V1 numeric money uses `Decimal(str(value))` with warning; v2 numeric
money fails closed. Missing v1 currency defaults to existing `RUB`; missing policy gets the exact
RM-128 behavior. Naive v1 timestamps become unknown with warning, not guessed UTC. Invalid known
fields, duplicates, NaN/infinity/negative/range errors make the whole catalog corrupt.

Corrupt data is copied byte-for-byte to a unique sibling quarantine path without deleting or replacing
the target. Future bytes are never touched. Repeated load reuses an existing identical quarantine when
practical and must not create unbounded user-visible warnings.

## 5. Built-in/custom behavior

- derive built-in identity solely from canonical built-in ID membership;
- ignore persisted `is_builtin` as authority while retaining the field for old-reader shape;
- preserve valid edits/disabled state for canonical built-in IDs;
- force every noncanonical ID to custom/deletable;
- reject custom save that targets a canonical ID;
- fail closed on duplicate/casefold collision;
- merge missing built-ins in memory;
- restore only canonical built-ins and preserve custom payloads;
- sort canonical built-ins first, custom profiles deterministically.

## 6. Universal execution mode

`app/tenders/unified_search.py` adds frozen `SearchProfileExecutionMode` and exposes it on
`ResolvedUnifiedTenderSearch`:

- blank normalized runtime text → `SAVED_PROFILE` and exact profile query;
- nonblank normalized text → `KEYWORD_OVERRIDE` and only `keywords` replacement;
- profile policy must equal `REPLACE_KEYWORDS_IF_PRESENT`;
- provider/profile stale/disabled validation remains before worker/network;
- resolver remains pure and never persists runtime text.

Legacy `TenderSearchProfileRunner` remains unchanged and sync. Unified/controller/scheduler remain on
their existing async Collector seams.

## 7. Existing UI adaptation

`TenderSearchProfileEditor` replaces only two `QDoubleSpinBox` price controls with Decimal-safe line
inputs. Pure helpers parse/format exact text; empty is `None`; no float, rounding or guessed currency.
Existing field attributes and stable signals remain reachable where practical.

`TenderSearchProfilesPanel/Dialog`:

- reads one typed `load_result()` snapshot;
- shows bounded migrated/corrupt/future messages;
- migrated v1 remains editable and explicit save performs repository migration;
- corrupt/future disables create/save/delete/toggle/restore/run honestly;
- missing/current behavior and existing signals/actions remain;
- refresh after save/delete still reaches the existing unified panel through controller;
- transient unified text is never passed into editor.

No migration, built-in identity or execution policy decision is implemented in QWidget.

## 8. Expected-red contract

Add before production implementation:

- `tests/test_rm130_search_profile_schema.py` — statuses, strict v1/v2, money/time/policy round-trip;
- `tests/test_rm130_search_profile_repository.py` — no-write load, backup/quarantine, atomic rollback,
  duplicates and built-in/custom protection;
- `tests/test_rm130_search_profile_modes.py` — SAVED_PROFILE/KEYWORD_OVERRIDE and transient bytes;
- `tests/test_rm130_search_profile_ui.py` — bounded status, blocked mutation, exact Decimal editor;
- `tests/test_rm130_search_profile_composition.py` — one path/owner, legacy/unified/scheduler compatibility,
  no network and decision invariants.

Existing tests are extended instead of copied when they already own a behavior. Expected-red does not
weaken old assertions merely to pass.

## 9. Verification

Environment:

```powershell
$env:PYTHONUTF8 = "1"
$env:QT_QPA_PLATFORM = "offscreen"
$python = "C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe"
New-Item -ItemType Directory -Force .tmp | Out-Null
```

Focused:

```powershell
& $python -m pytest -q --basetemp .tmp/rm130-focused `
  tests/test_rm130_search_profile_schema.py `
  tests/test_rm130_search_profile_repository.py `
  tests/test_rm130_search_profile_modes.py `
  tests/test_rm130_search_profile_ui.py `
  tests/test_rm130_search_profile_composition.py `
  tests/test_tender_search_profiles.py `
  tests/test_tender_search_profile_repository.py `
  tests/test_tender_search_profile_editor.py `
  tests/test_tender_search_profiles_dialog.py `
  tests/test_tender_search_profile_runner.py `
  tests/test_tender_search_runtime.py `
  tests/test_rm128_unified_search_contract.py `
  tests/test_rm128_unified_search_panel.py `
  tests/test_rm128_unified_search_composition.py `
  tests/test_tender_search_ui_controller.py `
  tests/test_bootstrap_tender_search_integration.py
```

Neighbor:

```powershell
& $python -m pytest -q --basetemp .tmp/rm130-neighbor `
  tests/test_tender_search_engine.py `
  tests/test_tender_registry_runner_integration.py `
  tests/test_tender_collector_dialog.py `
  tests/test_tender_collector_ui_controller.py `
  tests/test_collector_scheduler.py `
  tests/test_tender_collector_schedule_dialog.py `
  tests/test_tender_collector_scheduler_controller.py `
  tests/test_collector_provider_control.py `
  tests/test_rm129_business_profile_composition.py `
  tests/test_collector_stop_factor.py `
  tests/test_participation_decision.py `
  tests/test_participation_decision_policy.py `
  tests/test_participation_decision_service.py `
  tests/test_participation_decision_persistence.py
```

Workflow-equivalent gate follows `.github/workflows/quality-gate.yml` exactly: secret scan, Ruff
check/format, configured mypy, offline credential smoke, migration/schema smoke, public import,
composition, build/release, full pytest and `pip_audit --skip-editable`, followed by `git diff --check`
and tracked status. No live provider call runs automatically.

## 10. Commit and release sequence

1. `docs(rm-130): audit saved search profile contracts`
2. `test(rm-130): define saved search profile schema v2`
3. `feat(rm-130): add typed search profile catalog loading`
4. `feat(rm-130): migrate saved profiles to schema v2`
5. `feat(rm-130): define universal profile execution modes`
6. `feat(rm-130): update saved profile editor and status`
7. `test(rm-130): cover migration rollback and composition`
8. `docs(rm-130): record saved profile acceptance evidence`

Inseparable implementation commits may be combined, but docs-only audit, expected-red contract and
post-merge closeout remain separate.

## 11. Stop and rollback

Stop implementation if a second repository/file/table/UI workflow/engine/Collector is required, or if
provider settings/credentials, normalization/ranking, scheduler redesign, sync retirement, decision/
critical stop/AI or RM-131+ would change.

Application rollback is scoped revert of RM-130 feature commits. Data rollback uses the byte-for-byte
v1 backup; failed replace keeps previous valid target; corrupt/future original remains untouched; temp
is removed. No DB rollback exists because no database/schema/migration changes are allowed.
