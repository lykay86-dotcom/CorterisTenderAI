# RM-121 — план реализации financial-risk assessment

Baseline: `32510874291da502d6a588e32e633c01e736c274`.

## Последовательность

1. Зафиксировать отдельный architecture/commercial/persistence/RM-107 audit без application-кода.
2. Зафиксировать stable domain/source/priority/payload contract и RED-тесты.
3. Добавить immutable financial types в существующий schema и один pure
   `app/core/ai/financial_risk.py`.
4. Интегрировать assessor после current provenance и после context completeness, сохранив один
   provider call и legal assessment.
5. Повысить только persisted payload `7 -> 8` и analyzer `8 -> 9`.
6. Локально пересчитывать current v8 financial section; legacy/future/corrupt cache обрабатывать
   fail-closed без SQLite migration.
7. Расширить только существующие AI tab и JSON/HTML exporter с internal citations и escaping.
8. Подтвердить неизменность RM-107, CommercialEstimator, CompanyCapabilityProfile и critical
   stop-factor priority.
9. Выполнить target/full/quality/security/adversarial acceptance и записать точные результаты.
10. Открыть feature PR; после merge и post-merge gate выполнить отдельный docs-only closeout.

## Commit checkpoints

```text
docs(rm-121): audit existing financial risk contours
test(rm-121): define financial risk assessment contract
feat(rm-121): add explainable financial risk assessment
docs(rm-121): record feature acceptance
```

## Не входит в пакет

- второй AI call/workflow/stage/provider root;
- новый calculator/repository/table/migration/classifier;
- чтение company profile или commercial estimate из financial policy;
- parsing денег/процентов из statements, regex или I/O;
- автоматическое заполнение сметы, прогноз убытка или сравнение лимитов;
- изменение RM-107 score/recommendation/actions/evidence/stop-factor policy;
- legacy float `AnalysisEngine.financial_risk`;
- новая вкладка или export format;
- RM-122 competition analysis.
