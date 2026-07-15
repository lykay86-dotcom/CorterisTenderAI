# RM-123 — план реализации полноты документации

Baseline: `8e5947e993a3d61cc6697abe4f410cb0771d2697`.

## Последовательность

1. Зафиксировать entry gate, architecture/data/persistence/RM-107 audit и baseline без
   application-изменений.
2. Зафиксировать exact inventory/issue/assessment/payload contract и написать RED tests.
3. Добавить immutable documentation types в existing schema и один pure
   `app/core/ai/documentation_completeness.py`.
4. Расширить existing context builder optional document-store protocol, объединить catalog с
   latest extraction, сохранить archive members и stable safe inventory.
5. Включить inventory в fingerprint и передать existing `TenderDocumentStore` через composition
   root без нового service.
6. Прикреплять inventory и пересчитывать assessment в existing service для каждого provider
   outcome без второго provider call/RUNNING_AI stage.
7. Повысить только payload `9 -> 10`, analyzer `10 -> 11`, context `5 -> 6`; current v10
   валидировать/exact-recompute, legacy/future/corrupt обрабатывать fail-closed без DB migration.
8. Расширить existing AI tab и JSON/HTML exporter; отделить provider `missing_documents` от
   local issues и сохранить escaping/citation navigation.
9. Подтвердить неизменность RM-107 score/recommendation/actions/evidence/stop-factor priority.
10. Выполнить target/full quality/security/static acceptance и записать точные результаты.
11. Открыть feature PR; после merge и post-merge gate выполнить отдельный docs-only closeout.

## Commit checkpoints

```text
docs(rm-123): audit documentation completeness
test(rm-123): define documentation completeness contract
feat(rm-123): add deterministic documentation completeness
docs(rm-123): record feature acceptance
```

## Не входит в пакет

- второй classifier, AI call, prompt, analyzer/service/orchestrator/repository/stage;
- новый provider root, table, column, migration, UI tab или export format;
- юридический completeness score/percentage/probability;
- provider statements или `missing_documents` как local source-of-truth;
- raw text/metadata/errors/paths/URLs/credentials в persisted snapshot или presentation;
- network/DB/filesystem/regex/money/company/legacy dependencies в pure policy;
- изменение RM-107 score, recommendation, actions, evidence или stop-factor policy;
- RM-124.
