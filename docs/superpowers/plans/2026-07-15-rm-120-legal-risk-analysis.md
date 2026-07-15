# RM-120 — план реализации legal-risk assessment

Baseline: `7f21be719277314dc244a1e22d158be9d5c207ea`.

## Последовательность

1. Зафиксировать отдельный architecture/persistence/RM-107 audit без application-кода.
2. Зафиксировать стабильный legal domain/policy/payload contract и RED-тесты.
3. Добавить immutable legal types в существующий domain schema и один pure
   `app/core/ai/legal_risk.py`.
4. Интегрировать assessor после current provenance и после context completeness без нового
   provider call/workflow/stage.
5. Повысить только persisted payload `6 → 7` и analyzer `7 → 8`; provider schema/format,
   prompt/context/citation resolver оставить без изменения.
6. Валидировать и безопасно пересчитывать current v7 legal section при cache load; legacy
   v1–v6 и future/corrupt data обрабатывать fail-closed без SQLite migration.
7. Расширить существующие UI/export section с internal citations, escaping и disclaimer.
8. Подтвердить неизменность RM-107, generic AI findings и deterministic stop-factor priority.
9. Выполнить target/full/quality/security/adversarial acceptance и записать точные результаты.
10. Открыть feature PR; после merge и post-merge gate выполнить отдельный docs-only closeout.

## Commit checkpoints

```text
docs(rm-120): audit legal risk analysis
test(rm-120): define legal risk assessment contract
feat(rm-120): add explainable legal risk assessment
docs(rm-120): record feature acceptance
```

## Не входит в пакет

- новый/повторный AI call, provider output fields, prompt/context changes;
- network legal verification;
- новый repository/table/migration;
- regex-копия legacy/deterministic legal rules;
- legal/financial score, stop factor или participation recommendation;
- новая вкладка либо новый export format;
- RM-121 financial analysis.
