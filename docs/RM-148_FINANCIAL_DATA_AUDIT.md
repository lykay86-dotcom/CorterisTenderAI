# RM-148 — аудит финансовых данных

Baseline: `origin/main` / `3c9ab31c7b65871e0367374ce084cf033c8a4534`.
Finding: `UI-141-009`. Аудит выполнен до production-кода.

## Source of truth и фактические bytes

Единственный workflow source of truth — `BusinessMetricsRepository` и файл
`business_workflow.json`; отдельного financial store, SQL mirror или chart cache нет.
`BusinessWorkflowRecord` хранит `total`, `profit`, `margin_percent` как `float`, schema — v2.
Запись `Decimal("0.10") / Decimal("0.01") / Decimal("10.00")` дала JSON-лексемы
`0.1 / 0.01 / 10.0`, а прочитанный record — три `float`. Invalid text в `_number()` дал `0.0`.
Это воспроизведено локально 19.07.2026 на baseline; существующий соседний contour —
`62 passed in 20.64s`.

XLSX characterization той же записи: после save/reopen `F2 == 0.1` (`float`), worksheet XML —
`<c r="F2" s="12" t="n"><v>0.1</v></c>`. Следовательно, numeric cell полезна Excel,
но не является exact canonical representation.

## Currency evidence

Выбран вариант A: legacy workflow — RUB. Это не вывод из одного glyph:

- production dialog задаёт suffix `₽` для обоих money fields
  (`app/ui/business_workflow/dialogs.py:230-237`);
- production export и import закрепляют headers `Сумма, ₽` / `Прибыль, ₽`
  (`app/reporting/workflow_excel.py:101-109`,
  `app/reporting/workflow_excel_import.py:498-515`);
- принятый `dashboard-kpi-v1` объявляет `potential_profit` как `Decimal, RUB`
  (`docs/RM-145_KPI_CONTRACT.md`);
- текущий table/detail/Dashboard форматируют только рубли; currency selector отсутствует;
- проверенные workflow tests/templates используют те же рублёвые headers и форматы;
- foreign-currency/FX contracts находятся в tender collector и не являются workflow owner.

В репозитории нет checked-in production `business_workflow.json` и нет workflow fixture с другой
валютой. Mixed/foreign v3 payload поэтому не мигрируется в RUB: он отклоняется как unsupported.

## Surface inventory

| Surface | Field | Current type | Parse | Compute | Round/display | Persist/export | Risk |
|---|---|---|---|---|---|---|---|
| Record | total/profit/margin | `float` | dataclass accepts anything | none | none | `asdict` JSON number | binary round-trip (`business_metrics.py:57-70,737-752`) |
| Repository API | all three | `float \| Decimal` | `_number` | none | none | coerces `float` | invalid→zero (`business_metrics.py:229-250,909-914`) |
| Repository KPI | profit | `float→Decimal(str)` | legacy float already lost | project priority | none | snapshot Decimal | selection correct, precision late (`business_metrics.py:814-851`) |
| Margin | margin | editable `float` | repository accepts independent value | dialog recomputes | Qt two decimals | stored authoritative | duplicate formula/conflict (`dialogs.py:105-108,272-279`) |
| Workflow table | all three | `float` | none | none | money 0 decimals, margin 1 | sort casts float | display/sort divergence (`model.py:338-395`) |
| Workflow detail | total/profit | `float` | `Decimal(str(value or 0))` | none | 0 decimals | none | missing→zero (`business_workflow_page.py:2385-2388`) |
| Edit dialog | all three | `QDoubleSpinBox` | `Decimal(str(value()))` | margin in UI | two decimals | payload Decimal then repo float | widget owns precision (`dialogs.py:102-108,169-180,230-279`) |
| Audit history | all three | string | `str(float)` | field diff | page/Excel format | event strings | lexical scale lost (`business_metrics.py:754-812`) |
| Dashboard | profit | `Decimal` | repo snapshot | repository selector | whole RUB | none | whole-ruble loss (`dashboard_viewmodel.py:201-210`) |
| RM-146 chart | y | `Decimal \| None` | strict contract | no finance formula | generic `str` | JSON/CSV Decimal | compatible, metadata adapter needed (`ui/charts/contracts.py`) |
| RM-147 analytics | count metrics | `int` | typed query | Qt-free service | generic | immutable snapshot export | reuse time/query/provenance; no financial owner (`tenders/analytics`) |
| XLSX export | all three | `float` cells | `Decimal(str(float))` aggregate | duplicate sums | two decimals | numeric XML | no exact metadata (`reporting/workflow_excel.py:238-256,385-413`) |
| XLSX import | all three | `Decimal` then repo float | permissive replace | margin if zero | quantize 0.01 | per-row writes | empty/invalid→zero, no transaction (`workflow_excel_import.py:498-571,729-767`) |
| Backup | all three | JSON primitives | `float()` validation | none | none | zip exact payload bytes | accepts NaN/inf/scale loss (`core/workflow_backup.py:335-402`) |
| Health | all three | JSON primitives | `float()` validation | none | none | report | current/legacy not distinguished (`core/workflow_database_health.py:194-300`) |

## Time, bounds and transactions

New timestamps are naive local ISO strings (`datetime.now().isoformat`) and therefore cannot be
used as truthful interval evidence. RM-147 already supplies aware half-open buckets; legacy naive
workflow timestamps remain unknown for FA-04. Current UI bounds are money `0..10_000_000_000` with
scale 2 and margin `-100..1000`; importer allows the same margin range and non-negative money.

Repository writes use one `RLock`, sibling temp and replace, but no fsync/readback; import applies
rows separately and attempts a payload rollback. Backup restore creates a safety archive and
restores it on exception, while validators currently accept any `float()`-parsable value.

## Audit conclusions

- Keep the existing repository/service path and potential-profit contributor selection.
- Introduce one Qt-free Decimal contract; UI/export/chart are projections only.
- Move workflow persistence to explicit v3 fixed-point strings plus `currency=RUB`.
- Keep margin derived (`profit / total * 100`), never independently authoritative.
- Use a controlled v2→v3 migration with byte backup, hash, dry-run, atomic replace and readback.
- Add an exact XLSX metadata sheet/columns; numeric cells remain usability projections.
- Reuse RM-147 time/query/provenance and RM-146 Decimal chart contracts.

