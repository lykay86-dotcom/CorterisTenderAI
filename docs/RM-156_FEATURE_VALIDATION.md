# RM-156 — validation модели контрагента

Дата: 23 июля 2026 года.

Статус: `LOCALLY VALIDATED / PUBLICATION PENDING`.

Baseline: expected-red merge `11d079b1474fa4a384cc35545f412440cf4a168c`.

## 1. Реализованный scope

- immutable `ContractorInn` с 10/12-digit ASCII/checksum validation;
- отдельный ORM `Contractor`, не смешанный с собственной `Company`;
- `ContractorRepository` и `UnitOfWork.contractors`;
- unique INN lifecycle с typed `DuplicateEntityError`, soft delete/restore и row version;
- общий `UTCDateTime`, сохраняющий aware UTC после SQLite round-trip;
- application schema `3 → 4`, verified backup и exact contractor schema/index readback;
- future/corrupt/missing version fail-closed без downgrade/rewrite;
- canonical mypy contour расширен с 20 до 26 source files.

Не добавлены UI, search, network/source adapters, external payloads, AI, scoring или поля
RM-157–RM-168. Collector schema остаётся 16; RM-107 decisions не меняются.

## 2. Commits

- `dfd25f4` — version-independent future-schema test fixture;
- `213b2e2` — identity, UTC persistence, ORM/repository/UoW, migration и regression tests.

## 3. Test-first transition

Accepted expected-red:

```text
24 failed, 3 passed
```

Первый implementation с `--runxfail`:

```text
27 passed
```

После снятия только strict xfail markers и добавления missing-version guard:

```text
28 passed in 10.89s
```

Assertions сохранены как постоянные regression tests; contract/tolerance не ослаблялись.

## 4. Local acceptance

| Gate | Результат |
|---|---|
| RM-156 target | `28 passed in 10.89s` |
| database/company/Collector/registry contour | `59 passed in 18.42s` |
| RM-156 + legacy/Collector schema | `33 passed in 12.28s` |
| offline credential isolation | `2 passed in 26.09s` |
| bootstrap/build/frozen | `10 passed in 16.73s` |
| full suite | `2509 passed, 2 warnings in 308.01s` |
| Ruff | passed |
| format | `811 files already formatted` |
| mypy | `26 source files` passed |
| secret scan | passed |
| RM-155 compatibility | passed |
| `git diff --check` | passed |

Два warning — принятые openpyxl unsupported-extension/conditional-formatting warnings. Pytest
использовал `QT_QPA_PLATFORM=offscreen` и отдельные короткие command-scoped TEMP/basetemp paths.
Dependency audit выполняется PR-head и exact Windows Quality Gate.

## 5. Data and rollback

- Migration 3→4 создаёт verified backup до изменения и сохраняет existing company/tender rows.
- Fresh/current schema paths идемпотентны.
- Future, corrupt и missing existing version не переписываются.
- Rollback после merge: revert feature merge и при фактической необходимости restore verified
  pre-migration backup; destructive automatic downgrade запрещён.
- Collector DB/schema/settings/credentials/artifacts и собственная `Company` не мигрируются.

## 6. Publication gate

Ожидаются feature PR-head Windows Python 3.12/3.13 Quality Gate, merge и successful fresh exact
merge-SHA gate. После exact success нужен отдельный docs-only RM-156 closeout; только он может
перевести RM-156 в `DONE` и активировать RM-157.
