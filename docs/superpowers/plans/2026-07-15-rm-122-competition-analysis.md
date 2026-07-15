# RM-122 — план реализации competition assessment

Baseline: `554b582eb22d276c00797eaf3b6700c515ab58eb`.

## Последовательность

1. Зафиксировать отдельный architecture/data/persistence/RM-107 audit без application-кода.
2. Зафиксировать stable domain/source/priority/payload contract и RED-тесты.
3. Добавить immutable competition types в существующий schema и один pure
   `app/core/ai/competition_review.py`.
4. Интегрировать assessor после current provenance и после context completeness, сохранив один
   provider call и legal/financial assessments.
5. Повысить только persisted payload `8 -> 9` и analyzer `9 -> 10`.
6. Локально пересчитывать current v9 competition section; legacy/future/corrupt cache
   обрабатывать fail-closed без SQLite migration.
7. Расширить только существующие AI tab и JSON/HTML exporter с internal citations, disclaimer и
   escaping.
8. Подтвердить неизменность RM-107 score/recommendation/actions/evidence/stop-factor policy.
9. Выполнить target/full/quality/security/adversarial acceptance и записать точные результаты.
10. Открыть feature PR; после merge и post-merge gate выполнить отдельный docs-only closeout.

## Commit checkpoints

```text
docs(rm-122): audit existing competition analysis
test(rm-122): define competition assessment contract
feat(rm-122): add explainable competition assessment
docs(rm-122): record feature acceptance
```

## Не входит в пакет

- второй AI call/workflow/stage/provider root;
- новый repository/table/migration/classifier;
- prediction числа конкурентов, победы, скидки, market share или legality;
- `raw_metadata`, внешние company/tender-result data и неподтверждённые протоколы;
- statement keyword/regex matching, legacy `COMP_RULES`/`competition_risk`;
- деньги, `float`, commercial estimate или company profile;
- изменение RM-107 score/recommendation/actions/evidence/stop-factor policy;
- новая вкладка или export format;
- RM-123.
