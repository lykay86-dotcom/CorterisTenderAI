# RM-148 surface parity matrix

Owner symbols are implementation targets derived from the audit; test references are the required
acceptance contour.

| Surface | Read | Edit | Aggregate | Format/sort | Export | Missing/currency/evidence | Test |
|---|---|---|---|---|---|---|---|
| Workflow table | repository snapshot | shared parser | none | financial formatter / Decimal key | selected snapshot | typed state, RUB, record ID | `test_workflow_financial_model.py` |
| Workflow detail | same record projection | none | none | full exact formatter | copy canonical | exact accessible state | model/UI parity |
| Edit dialog | canonical text | total/profit only | derived margin owner | inline validator | none | empty≠zero, RUB label | `test_workflow_financial_dialog.py` |
| Audit history | canonical event strings | none | none | formatter | XLSX history | actor/time/currency/unit | history regression |
| Dashboard KPI | financial snapshot | none | metric service | compact + exact text | snapshot JSON | contributors/fingerprint/state | `test_dashboard_financial_parity.py` |
| RM-147 analytics | coordinated query | none | financial service | shared formatter | same snapshot | RM-147 provenance/time | `test_financial_analytics_page.py` |
| RM-146 chart | adapter projection | none | none | chart Decimal | RM-146 exporter | unit/currency/contributors | `test_financial_chart_adapter.py` |
| Accessible table | chart model | none | none | exact text | same model | missing/state text | chart adapter test |
| JSON | immutable snapshot | none | none | canonical fixed point | financial exporter | full evidence/fingerprint | export contract |
| CSV | immutable snapshot | none | none | locale-free fixed point | financial exporter | separate columns | export contract |
| XLSX | immutable snapshot | importer parser | none | numeric display + exact text | reporting exporter | RUB/unit/fingerprint metadata | `test_workflow_financial_excel.py` |
| JSON/XLSX import | shared parser | transaction | margin validation | issue ordering | dry-run report | row state/currency | import contract |
| Backup/restore | repository payload | atomic replace | none | none | zip exact bytes | schema/Decimal/RUB/hash | backup integration |
| Database health | raw payload | recovery action | none | typed issues | report | schema/state/currency | health integration |

## Exact invariant

For one immutable snapshot:

```text
table canonical amount == KPI canonical amount == chart Decimal == accessible table amount
== JSON value == CSV value == XLSX exact metadata value
```

Contributor IDs, unit, currency, state and fingerprint are identical across tooltip, drill-down and
exports. Display strings may differ only by named projection. No consumer re-queries or recalculates.

