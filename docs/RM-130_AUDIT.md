# RM-130 — аудит сохранённых поисковых профилей

Дата аудита: 16 июля 2026 года.
Baseline: `9dd8e9cde2768840066e024dc607cc980570d048`.
Ветка: `feat/rm-130-saved-search-profiles`.
Worktree: `C:\CorterisTenderAI_1_5_1\.worktrees\rm-130-saved-search-profiles`.

## 1. Решение entry gate

Gate пройден до создания feature branch:

- после `git fetch origin --prune` локальные `main`, `origin/main` и `origin/HEAD` совпадают на
  `9dd8e9cde2768840066e024dc607cc980570d048`;
- baseline — merge PR #65 `docs/rm-129-completion`, то есть post-feature docs-only closeout RM-129;
- `docs/ROADMAP.md` и `docs/STATUS.md` назначают RM-129 `DONE`, RM-130 — единственным
  `IN PROGRESS`, RM-131–RM-200 — `PLANNED`;
- `docs/ROADMAP_HISTORY.md` содержит closeout RM-129, feature merge
  `f9b43c37bb5c7e631e4851cde2b39c1178d34239`, PR gate `29522220375` и успешный exact-SHA
  Windows gate `29522737754` на Python 3.12/3.13;
- tracked worktree `main` был чист; известные пользовательские untracked `.agents/` и
  `skills-lock.json` не затронуты и отсутствуют в feature worktree;
- local/remote веток с `rm-130` не было; read-only `gh pr list` подтвердил отсутствие открытых PR;
- feature worktree создан от exact `origin/main`, application/test changes до этого аудита не было.

Среда аудита: Microsoft Windows `10.0.19045`, `Russian Standard Time`/UTC+03:00,
Python `3.12.7`, `PYTHONUTF8=1`, Qt `offscreen`.

## 2. Проверенный контур и история

Полностью прочитаны canonical roadmap/DoD/history, RM-126 requirements/audit, RM-128 и RM-129
audit/plan, актуальный Windows workflow и RM-130 handoff. Проверены domain, repository, runtime,
legacy runner, unified resolver/panel/controller, profiles dialog/editor, Collector dialog,
scheduler consumers, public exports и релевантные tests.

Исторические ownership points:

- `fcf4809` — один `TenderSearchProfile`, один `TenderSearchProfileRepository`, schema v1,
  built-ins/custom, legacy runner;
- `950e873` — один profiles panel/dialog и один editor;
- `a1d8fa0` — единственный runtime path и controller integration;
- `051c45d` — exact `Decimal` persistence/query boundary;
- `6771815` — explicit currency policy;
- `f4cb7cd` — scheduler хранит ссылку на profile ID, а не копию profile payload;
- `39605d0`, `fc015ed`, `777079e`, `60685c6` — RM-128 audit, pure unified resolver, один
  Collector worker seam и сохранение per-run provider selection;
- `f9b43c3` не меняет saved-search contract: RM-129 capability repository остаётся отдельным.

## 3. Канонические владельцы и call sites

| Область | Единственный владелец | Фактические consumers |
|---|---|---|
| Persisted catalog | `TenderSearchProfileRepository` | runtime, profiles dialog, runner, controller, scheduler controller |
| Production path | `<data_directory>/search_profiles.json` | только `create_tender_search_runtime()` |
| Domain payload | frozen/slotted `TenderSearchProfile` | repository, runner, Collector/unified UI, scheduler dialogs |
| Built-ins | `create_builtin_search_profiles()` | repository merge/restore |
| CRUD UI | `TenderSearchProfilesPanel/Dialog` + `TenderSearchProfileEditor` | cached dialog в controller |
| Legacy execution | `TenderSearchProfileRunner.run(profile_id)` | profiles dialog/controller worker |
| Unified execution | `resolve_unified_tender_search()` | panel → controller → one `_CollectorRunWorker` seam |
| Collector dialog | existing `TenderCollectorDialog` | current enabled profile snapshot |
| Scheduler | `CollectorScheduleSettings.profile_id` | scheduler controller resolves current profile at run time |
| Public API | `app.tenders.__init__` | repository/profile/runner/runtime exports |

Production search found exactly one construction:

```text
app/tenders/search_runtime.py: TenderSearchProfileRepository(data_path / "search_profiles.json")
```

No second JSON/SQLite search-profile repository, DB table, profile engine, dialog, panel or worker
owner exists. Test repositories use temporary paths only.

Repository API call behavior:

- `initialize()` currently reads, merges and writes on missing/recovered input;
- `list_profiles()` also mutates when merge/recovery reports changes;
- `get()` delegates to `list_profiles()` and therefore may write;
- `save/update/set_enabled/delete/restore_builtin_profiles` all use the same owner and atomic
  sibling `.tmp` + `Path.replace()`;
- profiles dialog calls the same CRUD API and emits stable `profile_saved`, `profile_deleted`,
  `profile_run_requested` signals;
- profile saved/deleted refreshes existing unified panel through the existing controller;
- legacy runner and scheduler retain profile ID semantics; unified execution retains async Collector.

## 4. Фактический persisted schema-v1 contract

Top-level payload:

```json
{
  "schema_version": 1,
  "updated_at": "aware ISO timestamp",
  "profiles": ["flat TenderSearchProfile payloads"]
}
```

Money is written as decimal strings; currency defaults to `RUB`; timestamps are unvalidated strings;
`runtime_query_policy` and typed load status do not exist. Reader ignores `schema_version` entirely,
trusts persisted `is_builtin`, skips invalid/duplicate entries and then can rewrite the partial catalog.

An isolated reproduction under `.tmp/rm130-audit-behavior` produced:

| Input | Current result |
|---|---|
| missing file | `initialize()` writes schema v1 with 7 built-ins |
| valid v1 with all built-ins + custom | loads 8 profiles; bytes unchanged |
| future schema 99 with custom | bytes changed; rewritten as schema 1 |
| one invalid + one valid custom | invalid profile dropped; remaining catalog rewritten |
| duplicate ID | second item dropped; first item retained and catalog rewritten |
| malformed JSON | original moved byte-for-byte to `search_profiles.corrupt-*.json`; target rebuilt |
| edited/disabled real built-in with persisted `is_builtin=true` | edits and disabled state survive |
| custom ID with forged `is_builtin=true` | treated as built-in; delete incorrectly blocked |
| built-in ID with `is_builtin=false` | canonical built-in replaces the persisted payload |
| naive profile timestamps | accepted unchanged |
| numeric `0.1` | becomes `Decimal('0.1')` |
| numeric `9007199254740993.01` | becomes `Decimal('9007199254740994.0')`; precision already lost |
| string high-precision money | remains exact `Decimal` |

Thus current quarantine avoids destroying malformed bytes, but future/invalid/duplicate data can be
silently rewritten. Built-in protection trusts a user-controlled flag, and numeric JSON money cannot
guarantee exactness.

## 5. Current universal execution behavior — D130-01

Only two existing journeys are approved:

1. `SAVED_PROFILE`: blank/whitespace runtime text uses `profile.to_search_query()` exactly.
2. `KEYWORD_OVERRIDE`: normalized nonblank runtime text replaces only query `keywords`.

The resolver already preserves exclusions, regions, laws, date-only bounds, `Decimal`, currency,
page/page size and validates current provider snapshots before worker/network. It never mutates the
profile or repository. The legacy profiles dialog still executes `TenderSearchProfileRunner`; unified
panel and scheduler use existing Collector seams.

Decision D130-01:

- add frozen `SearchProfileExecutionMode` with only `SAVED_PROFILE` and `KEYWORD_OVERRIDE`;
- add persisted `SearchProfileRuntimeQueryPolicy.REPLACE_KEYWORDS_IF_PRESENT` to schema v2;
- v1 migration receives that policy because it exactly describes RM-128 behavior;
- resolved request exposes the derived execution mode;
- unknown current policy fails closed before worker/network;
- transient text remains request-only and is never supplied to editor/repository.

No additional business mode, query model, filter chain, engine or Collector is justified.

## 6. Typed load contract — D130-02

Decision D130-02 adds immutable public types in the existing repository module:

```python
class SearchProfileCatalogLoadStatus(StrEnum):
    MISSING = "missing"
    CURRENT = "current"
    MIGRATED_V1 = "migrated_v1"
    CORRUPT = "corrupt"
    UNSUPPORTED_FUTURE = "unsupported_future"

@dataclass(frozen=True, slots=True)
class SearchProfileCatalogLoadResult:
    profiles: tuple[TenderSearchProfile, ...]
    status: SearchProfileCatalogLoadStatus
    source_schema_version: int | None
    warnings: tuple[str, ...] = ()
    quarantine_path: Path | None = None
```

`load_result()` performs no network and never rewrites valid v1/current/future bytes. Corrupt/future
return no masquerading successful catalog; mutations fail closed with a bounded typed repository
error. Missing returns canonical built-ins in memory; explicit `initialize()` may create a current-v2
catalog. Compatibility `initialize/list/get` remain, but must preserve the typed safety policy.

## 7. Target schema v2 and migration decisions

Schema v2 keeps the current flat profile fields and adds only
`runtime_query_policy = "replace_keywords_if_present"`. Required rules:

- top-level `schema_version` is an integer and exactly `2` for current data;
- money in v2 is decimal string or `null`; numeric money is rejected;
- `price_currency` is explicit normalized code;
- nonempty catalog/profile timestamps are aware ISO 8601; writer normalizes UTC;
- empty optional profile timestamps stay unknown;
- date-only search bounds remain `date` through `lookback_days`; no timezone is invented;
- known bool/int/array/enum fields are shape-validated; invalid known values corrupt the whole
  catalog rather than dropping an entry;
- duplicate and casefold-colliding IDs fail closed;
- unknown v2 policy fails closed;
- unknown extra fields remain ignored for forward-compatible additions inside schema v2;
- order is canonical built-ins in catalog order, then custom by `(name.casefold(), id)`.

V1 migration is pure and in memory on load. It preserves all valid known fields and custom profiles.
Compatibility exceptions are explicit:

- numeric v1 money uses deterministic `Decimal(str(value))` and adds a bounded warning; precision
  already lost by JSON float parsing cannot be recovered;
- missing currency becomes the existing documented `RUB` default with warning;
- missing runtime policy receives the D130-01 policy;
- naive nonempty v1 timestamps become explicit unknown (`""`) with warning; timezone is not guessed;
- invalid/NaN/infinite/negative/range values make the catalog corrupt.

First explicit mutation of valid v1 revalidates current bytes, creates a byte-for-byte sibling backup,
applies the mutation to a full in-memory catalog, writes sibling temp and atomically replaces the
target. Replace failure preserves original and backup and removes temp. `load_result()` alone does not
migrate on disk.

Malformed/invalid current data receives a byte-for-byte quarantine copy while the original target is
left untouched. Future schema is never quarantined or modified. Both states block save/update/delete/
toggle/restore until the operator restores a supported file.

## 8. Built-in/custom contract

Canonical membership in `create_builtin_search_profiles()` is the only source of built-in identity.
Persisted `is_builtin` remains in v2 only for old-reader shape and is ignored as an authority:

- matching canonical ID loads as protected built-in while valid user edits/disabled state survive;
- custom ID always loads as custom even with forged `is_builtin=true`;
- missing built-ins merge in memory deterministically;
- custom cannot replace a canonical ID through `save()`;
- delete of real built-in remains blocked;
- explicit restore resets only canonical built-ins and preserves custom exact.

## 9. Decimal and UI boundary

No reusable Decimal-safe price control/helper exists in the audited UI contour. The current editor
uses `QDoubleSpinBox`, `float(profile.min_price)` and returns `float`, with a maximum below the required
`9007199254740993.01`. This is a confirmed precision boundary despite exact domain/JSON support.

Decision: replace only profile price inputs with line-edit based presentation, backed by pure
parser/formatter helpers outside `QWidget`. Empty text means `None`; accepted text produces finite
non-negative `Decimal`; no float conversion or automatic rounding occurs. Currency remains the
profile's explicit code. Existing dialog, signals and controller ownership stay unchanged.

## 10. Exact change contour

Production changes are limited to:

- `app/tenders/search_profiles.py` — policy/domain invariants, strict reusable parsing helpers;
- `app/tenders/search_profile_repository.py` — typed load, strict v1/v2 decode, backup/quarantine,
  fail-closed mutations, atomic v2 writer, canonical built-in identity;
- `app/tenders/unified_search.py` — typed execution mode and policy enforcement;
- `app/ui/tender_search_profile_editor.py` — Decimal-safe price input only;
- `app/ui/tender_search_profiles_dialog.py` — typed status and mutation blocking;
- `app/tenders/__init__.py` — public re-exports when required by existing public surface.

`search_runtime.py`, unified panel/controller, bootstrap, legacy runner, scheduler and Collector
dialogs need regression coverage but no production change is currently justified. A red test must
prove any expansion before those files are edited.

New ownership-focused tests:

- `tests/test_rm130_search_profile_schema.py`;
- `tests/test_rm130_search_profile_repository.py`;
- `tests/test_rm130_search_profile_modes.py`;
- `tests/test_rm130_search_profile_ui.py`;
- `tests/test_rm130_search_profile_composition.py`.

Existing tests will be updated only where schema-v1 unsafe behavior or the float widget was the old
asserted contract.

## 11. Baseline evidence

Commands used repository-local ignored basetemp and project `.venv`:

- focused profiles/RM-128/controller/bootstrap contour: `49 passed in 9.75s`;
- full pytest: `1623 passed in 74.97s (0:01:14)`;
- `git status --porcelain=v1 --untracked-files=no`: clean before docs files.

The focused list covered profile domain/repository/editor/dialog/runner/runtime, RM-128 resolver/panel/
composition, tender controller and bootstrap. No live provider call was run.

## 12. Risks, non-scope and audit decision

Guards required before acceptance: future/original byte preservation, whole-catalog fail-closed
validation, v1 backup and replace rollback, built-in membership tests, exact Decimal UI round-trip,
transient query byte preservation, one production repository/path/panel/worker composition, scheduler
ID compatibility and RM-129/RM-107 decision invariants.

DB/schema migrations, dependencies, provider settings/credentials/catalog, matching/normalization/
ranking, scheduler redesign, sync retirement, score/recommendation/critical stop-factor/AI and RM-131+
are out of scope.

**ACCEPTED FOR DOCS-ONLY AUDIT COMMIT.** The work is implementable inside existing owners. Production
changes remain blocked until this audit/plan is committed, then expected-red contract is committed and
its exact failure evidence is added here.

## 13. Expected-red evidence

Pending the isolated second commit. No production implementation may start until exact command and
failure summary are recorded in this section.
