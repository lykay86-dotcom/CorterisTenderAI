# RM-123 — контракт полноты документации

Baseline: `8e5947e993a3d61cc6697abe4f410cb0771d2697`.

Architecture audit: `docs/RM-123_AUDIT.md`.

## Назначение и граница результата

RM-123 добавляет к existing `AiDocumentAnalysis` локальную, воспроизводимую и объяснимую оценку
технической полноты известного CorterisTenderAI комплекта. Оценка не утверждает юридическую
полноту публикации и не использует provider answer как источник status/issues.

Обязательный disclaimer:

> Оценка отражает полноту локально известного комплекта и его пригодность для текущего анализа
> CorterisTenderAI. Она не подтверждает юридическую полноту документации закупки и не
> гарантирует, что площадка опубликовала все обязательные материалы.

## Canonical inventory

`AiDocumentContext` получает поле `documentation_inventory` — stable tuple frozen/slots
`AiDocumentationDocumentSnapshot`:

```text
document_id
display_name
document_kind
origin
download_status
extraction_status
checksum_sha256
available_locally
text_available
included_in_context
context_truncated
```

Exact `origin`: `catalog`, `archive_member`, `local_extraction`.

Exact `download_status`: `downloaded`, `reused`, `deduplicated`, `failed`, `not_recorded`.

Exact `extraction_status`: `extracted`, `reused`, `partial`, `unsupported`, `failed`,
`not_recorded`.

`document_kind` — value единственного existing `DocumentKind`. Checksum — empty string для
локально неизвестного checksum либо canonical 64 lowercase hex. Display name очищается от path,
control/unsafe characters, whitespace и ограничивается 500 символами. Snapshot не содержит URL,
path, raw error/warning, credentials, provider data или document text.

Builder объединяет `TenderDocumentStore.list_documents()` и latest
`TenderDocumentTextService.list_results()` по `document_key`. Text-only record получает origin
`archive_member` для prefix `archive-member:`, иначе `local_extraction`. Stable ordering:
`DocumentKind` priority, casefold document ID, origin, checksum. Перестановка входных records не
меняет inventory или fingerprint.

## Domain contract

`AiDocumentationCompletenessStatus`:

```text
complete
partial
no_documents
unavailable
```

`AiDocumentationIssueCode`:

```text
download_failed
extraction_failed
extraction_partial
unsupported_format
empty_text
context_truncated
context_omitted
required_analysis_scope_not_found
inventory_mismatch
duplicate_content
unclassified_document
```

Последние два кода informational и сами по себе не переводят assessment в `partial`.

`AiDocumentationScope`:

```text
package
technical_specification
application_requirements
draft_contract
procurement_notice
estimate
application_form
instructions
other
```

`AiDocumentationIssue` exact keys:

```text
issue_id
code
scope
document_ids
title
recommended_action
```

`issue_id` соответствует `documentation_[0-9a-f]{32}` и вычисляется как первые 32 hex SHA-256
canonical JSON от policy version, issue code, scope и sorted document IDs. IDs unique, sorted,
не более 200, каждый не более 500 символов. Title — до 500, action — до 1000 символов. Тексты
берутся только из fixed local policy.

`AiDocumentationCompletenessAssessment` exact keys:

```text
status
policy_version
known_document_count
locally_available_count
text_available_count
included_document_count
issues
warnings
```

Counts — non-negative integers и exact-согласованы с inventory. Issues unique и stable sorted;
warnings unique, bounded до 100 элементов по 1000 символов. Score, percentage, probability,
confidence, severity, stop factor и participation recommendation отсутствуют.

## Pure policy

Один модуль `app/core/ai/documentation_completeness.py` предоставляет:

```text
AI_DOCUMENTATION_COMPLETENESS_POLICY_VERSION = "1"
assess_documentation_completeness(
    analysis: AiDocumentAnalysis,
) -> AiDocumentationCompletenessAssessment
```

Policy выполняет только pure преобразование immutable analysis/inventory. Запрещены filesystem,
network, provider, DB/repository, UI/exporter, raw text, regex/keyword matching, money/Decimal/
float, company profile, legacy engine и raw metadata.

## Status и issue policy

`NO_DOCUMENTS`: valid current inventory пуст.

`UNAVAILABLE`: inventory невозможно безопасно построить/валидировать, current snapshot повреждён,
current persisted assessment нельзя безопасно пересчитать либо payload future/corrupt.

`PARTIAL`: есть хотя бы один blocking issue:

- catalog document failed или недоступен локально — `download_failed`;
- extraction `failed` — `extraction_failed`;
- extraction `unsupported` — `unsupported_format`;
- extraction `partial` — `extraction_partial`;
- доступный документ не имеет извлечённого текста — `empty_text`;
- snapshot усечён — `context_truncated`;
- рабочий non-duplicate text snapshot не включён — `context_omitted`;
- ТЗ или application-requirements scope не представлены —
  `required_analysis_scope_not_found` с нейтральной формулировкой;
- scoped found/included IDs противоречат inventory — `inventory_mismatch`;
- присутствующий draft contract недоступен, неполон, omitted или truncated — соответствующий
  blocking issue.

Отсутствующий draft contract, notice, estimate, application form или instructions сам по себе не
является blocking issue. Coverage для них отображается информационно.

Одинаковый checksum формирует informational `duplicate_content`; если одна рабочая копия
включена, duplicate не создаёт ложный blocking omission. `DocumentKind.OTHER` может формировать
informational `unclassified_document`, но не означает отсутствующий документ.

`COMPLETE`: inventory valid и non-empty, ТЗ и application requirements представлены, все
нужные текущему анализу known documents доступны и обработаны, присутствующий contract полон,
blocking issues и relevant context omission/truncation отсутствуют. Значение означает только
техническую готовность локального комплекта.

## Analyzer/service/cache

Порядок existing graph сохраняется:

1. store + text service;
2. один context builder строит documents/statistics/inventory;
3. inventory/statistics входят в context fingerprint;
4. один provider call и strict normalize/provenance;
5. service применяет scoped context;
6. service прикрепляет canonical inventory;
7. service пересчитывает documentation completeness;
8. existing legal/financial/competition assessors пересчитываются;
9. один analysis сохраняется existing repository.

Analyzer возвращает default `unavailable`; service пересчитывает assessment для complete,
partial, no_documents, provider_disabled, provider_error и invalid_response. Provider failure не
уничтожает local assessment, stale successful AI result не используется как fallback. Safe cache
policy не меняется.

Fingerprint содержит exact serialized inventory. Изменение checksum, kind, download/extraction
status, availability, text availability, inclusion или truncation инвалидирует cache.

## Persistence и версии

```text
provider output schema: 4 (без изменения)
response format: corteris_tender_analysis_v4 (без изменения)
prompt: 6 (без изменения)
citation resolver: 1 (без изменения)
legal/financial/competition policy: 1 (без изменения)
persisted payload: 9 -> 10
analyzer: 10 -> 11
context: 5 -> 6
documentation completeness policy: 1
```

Current v10 добавляет ровно два root key:

```text
documentation_inventory
documentation_completeness_assessment
```

Inventory item и assessment/issue nested keys должны exact совпадать с контрактом выше.
Current v10 строго валидирует inventory, восстанавливает scoped sections, локально пересчитывает
assessment и exact-сравнивает saved section. Mismatch возвращает canonical recalculation со
status `partial` либо `unavailable` и bounded fixed warning.

Legacy v1–v9 получает empty inventory и unavailable assessment; legacy facts не повышаются до
verified, строки не переписываются. Future/corrupt payload fail-closed. Duplicate JSON keys
остаются запрещены. Physical SQLite schema и migrations не меняются.

## UI/export

Existing AI tab и JSON/HTML exporter получают секцию «Полнота документации» перед ТЗ,
requirements, contract и risk registries. Секция показывает русский status, disclaimer, policy
version, четыре counts, coverage всех `DocumentKind`, safe inventory identity, issues/actions и
warnings.

Provider list показывается отдельно под заголовком «Возможные отсутствующие документы по ответу
AI — не подтверждено локальной проверкой». Он не объединяется с local issues.

Все external values escaped/bounded. Запрещены source URL, private path, raw errors/tracebacks,
credentials, raw provider response и full document text. Existing citation navigation не
меняется.

## RM-107 и acceptance

Documentation inventory/assessment не входят в `_current_verified_ai_findings()`, score,
recommendation, actions, confidence, decision evidence, stop factors, commercial completeness
или company projection. `participation_decision_policy.py` и
`collector/participation_score.py` не изменяются. Critical stop factor остаётся абсолютным при
score 100.

Обязательны pure policy, inventory/context, provider/offline, persistence tamper, duplicate-key,
UI/export/security, RM-107 regression и static architecture tests из ТЗ. RED должен доказать
отсутствие нового module/contract до production implementation.
