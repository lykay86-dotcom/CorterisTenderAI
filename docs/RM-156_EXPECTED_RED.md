# RM-156 — expected-red evidence модели контрагента

Дата: 23 июля 2026 года.

Baseline: audit merge `cf7f6681a1555bd38ea0ae68990518a3acf38455`.

Scope: strict tests и test documentation only. `app/`, database schema, dependencies, UI,
Collector и production data не изменены.

## 1. Entry gate

- Audit commit `3b32431`.
- PR #157 head `3b32431afe58d25f6b9eddb989505e80a0278d31`.
- PR-head run `30005475267`, jobs `89200323932`/`89200324018`, successful, включая dependency
  audit.
- Merge `cf7f6681a1555bd38ea0ae68990518a3acf38455`.
- Exact merge-SHA run `30006037737`, jobs `89202141374`/`89202141383`, successful, включая
  dependency audit.

## 2. Метод

Отсутствующие RM-156 boundaries помечены `pytest.mark.xfail(strict=True)`. Regular pytest
mergeable, но unexpected XPASS блокирует package. Тот же файл запускается с `--runxfail`, чтобы
доказать реальный red до implementation.

Три существующих isolation guards остаются обычными passing tests:

- `Company` остаётся owner собственной ООО «КОРТЕРИС»;
- `TenderCustomer` остаётся observation без master-record lifecycle;
- Collector schema остаётся 16.

## 3. Contract matrix

| Boundary | Cases | Baseline |
|---|---:|---|
| valid 10/12 INN identity, kind, immutable value | 1 | expected-red |
| invalid type/shape/ASCII/checksum matrix | 15 | expected-red |
| minimal ORM schema and direct validation | 1 | expected-red |
| repository/UoW unique soft-delete/restore lifecycle | 1 | expected-red |
| aware UTC SQLite round-trip | 1 | expected-red |
| fresh schema 4 and unique INN index | 1 | expected-red |
| schema 3→4 row preservation and verified backup | 1 | expected-red |
| future schema fail-closed without downgrade | 1 | expected-red |
| corrupt schema version sanitized/no rewrite | 1 | expected-red |
| public context isolation from future stages/UI/network/AI | 1 | expected-red |
| existing owner/observation/Collector guards | 3 | passing |

## 4. Direct red evidence

```text
python -m pytest -q tests/test_rm156_contractor_model_expected_red.py --runxfail
24 failed, 3 passed in 11.88s
```

Все 24 failures относятся к целевым assertions:

- public `app.contractors` и identity отсутствуют;
- ORM `Contractor` и `UnitOfWork.contractors` отсутствуют;
- SQLite audit timestamp теряет timezone после new-session read;
- application schema остаётся 3, таблицы `contractors` нет;
- schema 3→4/backup boundary отсутствует;
- future schema молча downgraded;
- corrupt version выбрасывает raw `ValueError`, а не sanitized `MigrationError`.

Collection/setup/network failures отсутствуют. Missing public API преобразован test helper в
явный target failure, а не collection error.

## 5. Regular green evidence

| Gate | Результат |
|---|---|
| expected-red file | `3 passed, 24 xfailed in 13.24s` |
| focused neighbors + expected-red | `34 passed, 24 xfailed in 18.20s` |
| full suite | `2484 passed, 24 xfailed, 2 warnings in 292.43s` |
| offline credential isolation | `2 passed in 22.91s` |
| migration/Collector schema | `5 passed in 17.85s` |
| bootstrap/build/frozen | `10 passed in 19.86s` |
| Ruff check/format | passed; `807 files already formatted` |
| mypy | `20 source files` passed |
| secret scan | passed |
| RM-155 compatibility | passed |
| `git diff --check` | passed |

Два warning — принятые openpyxl unsupported-extension/conditional-formatting warnings. Pytest
использовал `QT_QPA_PLATFORM=offscreen` и отдельные короткие command-scoped TEMP/basetemp paths.
Dependency audit подтверждён в обеих audit exact jobs; новый PR-head/exact CI повторяет его.

## 6. Exit

Этот package не исправляет expected-red boundaries. После его merge и successful exact merge-SHA
gate создаётся отдельный feature worktree от точного merge SHA. Каждый strict xfail снимается
только implementation, делающей соответствующий test pass; RM-157–RM-168 не начинаются.

## 7. Green transition

- PR #158 head `c3a51913234c6d1864f70817572f3a3f95f2c926`, PR-head run `30008132034`,
  jobs `89209082737`/`89209082678`, successful, включая dependency audit.
- Merge `11d079b1474fa4a384cc35545f412440cf4a168c`; exact run `30008699060`, jobs
  `89211007130`/`89211007201`, successful, включая dependency audit.
- Fixture-only commit `dfd25f4` сделал future-schema source version-independent без изменения
  assertion.
- Feature commit `213b2e2` перевёл direct contract в `27 passed`; после missing-version guard
  final target — `28 passed`.

Expected-red assertions сохранены; сняты только strict xfail markers после их фактического green.
