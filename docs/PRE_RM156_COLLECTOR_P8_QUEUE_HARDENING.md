# PRE-RM-156 Collector P8 — discovery queue hardening

Дата: 23 июля 2026 года.

Статус: `ACCEPTED`; implementation опубликована и принята fresh exact merge-SHA Quality Gate.
Это закрывает hardening scope P8, но не Collector prerequisite closeout.

## 1. Entry gate

- Baseline: accepted P8 access-audit merge
  `29aba93a4cdb24ba526dbbe265f51e859ba9754a`.
- PR #151 head `205d223f67da8ca0fd84732b4b14aeb1c7402662`; PR-head run
  `29992310890` успешен: jobs `89157719548` (3.12), `89157719632` (3.13).
- Exact run `29992951951` успешен: jobs `89159721376` (3.12), `89159721509` (3.13),
  включая dependency audit.
- TenderGuru остаётся
  `BLOCKED_EXTERNAL / ENTITLEMENT_AND_LICENSE_REQUIRED`; producer, credentials, endpoint
  configuration, fixture и live request не создаются.

## 2. Expected-red characterization

До application changes focused discovery tests дали `5 failed, 8 passed in 14.74s`:

- repository не принимал `max_records`, `max_attempts_per_discovery`, `max_payload_bytes`;
- raw exception text с bearer/token/private URL сохранялся в record/attempt history;
- arbitrary `api_code`, raw metadata, description и manual note сохранялись в queue.

Failures возникли на отсутствующих boundary contracts и secret-leak assertions, а не на
import/fixture/network setup.

После первого green implementation diff отдельный decision-path capacity guard дал ожидаемый
`1 failed, 1 passed in 7.46s`: full protected queue прерывала `CollectorService` до обработки
официального record. Минимальный fix ловит только fixed capacity error, считает rejection и
продолжает authoritative path; остальные repository ошибки не скрываются.

## 3. Accepted local contracts

Один existing `AggregatorDiscoveryRepository` получает deterministic constructor bounds:

- `max_records=10_000`;
- `max_attempts_per_discovery=100`;
- `max_payload_bytes=64 KiB`.

Overrides предназначены для tests/composition injection и не создают второй settings owner.
Persisted schema/version не меняются.

### Queue capacity

- New distinct enqueue выполняет `BEGIN IMMEDIATE`, поэтому несколько repository instances не
  могут одновременно превысить limit.
- При capacity сначала удаляются только oldest terminal rows:
  `official_match_found`, `official_match_not_found`, `failed`.
- `pending_official_verification` и `manual_review_required` никогда не вытесняются.
- Attempts evicted terminal row удаляются в той же transaction.
- Если безопасных terminal rows недостаточно, enqueue fail-closed с fixed
  `AggregatorDiscoveryCapacityError`; raw candidate/error в exception не попадает.
- `CollectorService` учитывает такой item в `aggregator_discovery_rejected_count`, но продолжает
  normalization/verification/persistence authoritative items. Aggregator capacity не блокирует
  официальный decision path.

### Payload minimization and sanitization

- Stored candidate сохраняет только необходимые для official match поля и explicit discovery
  markers.
- Description, documents, classification codes, tags, customer KPP/region/address и arbitrary
  `raw_metadata` не сохраняются.
- Existing shared URL sanitizer расширен только для secret names `api_code` и `refresh_code`;
  userinfo и fragment удаляются из discovery card URL.
- Minimized UTF-8 payload сверх bound отвергается fixed capacity error.

### Retry, notes and attempt retention

- Processor выполняет не более одного official lookup на pending record за invocation.
- Failure переводит record в `failed`; автоматического tight-loop retry нет.
- Retry становится explicit только после повторного discovery enqueue того же identity.
- Caught exception проходит existing `classify_search_error`; raw exception type/text/URL/secret
  не сохраняются.
- Legacy string failure input сохраняет только fixed safe message/code.
- Manual note проходит existing bounded `safe_provider_warnings` boundary; rendered note не
  превышает 300 characters.
- После каждой записи transaction сохраняет только latest
  `max_attempts_per_discovery` rows в deterministic insertion order.

## 4. Preserved boundaries

- Discovery gate до normalization/dedup на final и partial snapshots не меняется.
- Aggregator values не входят в verification field candidates, persistence, score,
  recommendation или critical stop-factor path.
- Official identity может подтвердить только EIS/Mos Supplier record.
- Catalog/factory/settings/readiness сохраняют ровно 13 built-ins; `tenderguru_discovery` не
  добавляется.
- DB schema/version/migrations, dependencies, scheduler, artifacts/checkpoints, credentials/
  keyring и RM-107 deterministic decision не меняются.

## 5. Tests

Добавлены negative/atomic contracts:

- terminal-only eviction и protected pending capacity;
- cross-repository atomic capacity;
- full protected queue не блокирует authoritative service path;
- bounded latest attempt retention и cascade cleanup;
- explicit single-attempt retry;
- raw exception/manual note/candidate payload secret rejection;
- minimized payload size rejection;
- shared `api_code`/`refresh_code` URL redaction.

Финальная локальная валидация:

- focused discovery/transport/service/isolation/catalog/schema/migration contour:
  `51 passed in 16.06s`;
- full baseline: `2474 passed, 2 warnings in 309.67s`; обе warnings — прежние
  `openpyxl` notices;
- cross-repository atomic capacity race: `5/5` successful fresh pytest processes;
- Ruff: `All checks passed`; format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan и `git diff --check` успешны.

Pytest использовал workflow-compatible `QT_QPA_PLATFORM=offscreen` и отдельные короткие unique
command-scoped `--basetemp`.

## 6. Rollback

Rollback — revert hardening commit. Schema downgrade и data rewrite не требуются. Existing rows
остаются читаемыми; constructor defaults, fixed retry behavior и minimization возвращаются к
предыдущему поведению без удаления user settings, credentials, decisions или official tender
records.

## 7. Publication acceptance

- Commits:
  - tests `16829e7`;
  - implementation `864862c`;
  - documentation `df91a4c`.
- PR #152 head `df91a4cdcb5923f31b7be4501e85cd25e7329485`.
- PR-head run `29996521546` успешен:
  - Python 3.12 job `89171378944`;
  - Python 3.13 job `89171378841`.
- Merge commit `593ea5c7d3657e881fad985933444a44aa12b0f1`.
- Fresh exact merge-SHA run `29996926693` успешен:
  - Python 3.12 job `89172697592`;
  - Python 3.13 job `89172697637`.
- Обе Windows-матрицы включили full suite и dependency audit.
