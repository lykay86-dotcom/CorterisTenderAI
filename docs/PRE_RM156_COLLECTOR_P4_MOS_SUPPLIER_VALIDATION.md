# PRE-RM-156 Collector P4 — Mos Supplier reference adapter validation

Дата: 22 июля 2026 года.

Статус: `ACCEPTED`; PR-head и exact merge-SHA Windows gates успешны.

## 1. Scope и baseline

- Exact baseline: P4 EIS merge `300385108082746ac8818dad19104f57618366a9` с успешным exact
  merge-SHA run `29943599187`.
- Ветка: `codex/pre-rm156-collector-mos-reference`.
- Test-first commit: `31bc13c`; implementation commit: `e3fedb6`.
- Scope ограничен вторым P4 provider package: существующим `mos_supplier` official bearer API
  adapter. Provider identity/catalog P5, schema/dependencies, RM-107 deterministic score,
  recommendation и critical stop-factor priority не изменены.
- Live request не выполнялся: lawful token и отдельное разрешение отсутствуют. Readiness остаётся
  честным `IMPLEMENTED_OFFLINE`; offline fixture не выдаётся за live acceptance.

## 2. Реализованный contract

- Explicit `mos-supplier-api-v1` фиксирует только подтверждённую поверхность: один
  документированный API response, максимум 500 элементов локальной выборки и 50 MiB response.
  Параметры серверной пагинации не документированы и не угаданы; adapter возвращает terminal page
  без cursor и публикует безопасное предупреждение.
- Bearer token загружается существующим config/keyring/environment path. Без токена provider
  возвращает `NOT_CONFIGURED` до сетевого запроса; token и remote body не попадают в public
  error/warnings/artifact metadata.
- Existing `AsyncProviderSearchEngine` остаётся единственным owner concurrency, timeout,
  cancellation и page acceptance. Provider больше не продвигает checkpoint из `search()`;
  accepted page, raw artifact reference и typed checkpoint атомарно фиксируются existing
  `CollectorStateRepository`.
- Resume принимается только при совпадении provider/fingerprint/contract/parser. Legacy cursor не
  применяется, поскольку серверная пагинация не подтверждена. Incremental watermark использует
  существующие watermark/committed/updated timestamps и conservative overlap policy.
- Search/card/document responses и rejected JSON/structure/API bodies сохраняются existing
  content-addressed `RawArtifactStore` с SHA-256, sanitized URL, media type/encoding,
  contract/parser versions, parse outcome и retention class. Search artifact commit-coupled с
  accepted page; detail/card artifact является evidence для `get_tender()` и `list_documents()`.
- Cancellation проверяется до запроса; factory/construction остаются no-network. Новый parser,
  HTTP runtime, engine, repository, DB owner или migration не создавались.

## 3. Test-first и локальные gates

- До implementation новый P4 contour дал `9 failed`; все failures относились к отсутствующим
  contract/artifact/atomic-checkpoint/redaction boundaries, setup/import/network failures не было.
- После implementation target contract: `9 passed`; Mos/EIS/parser/config/checkpoint/factory
  regression contour: `37 passed`; финальный target/factory повтор: `11 passed`.
- Full pytest: `2458 passed, 2 warnings in 259.43s`; warnings — существующие openpyxl notices,
  xfail отсутствуют.
- Repository secret scan, Ruff check, Ruff format (`802 files`), mypy (`20 source files`) и
  diff-check успешны.
- Mandatory offline pair: `2 passed`; migrations: `5 passed`; public import успешен; bootstrap:
  `1 passed`; build/frozen: `9 passed`; RM-155 compatibility guard успешен.
- Локальный `pip-audit` сначала заблокирован sandbox socket policy, затем escalation отклонён без
  отдельного разрешения на экспорт dependency inventory в публичный PyPI. Обход не выполнялся;
  dependencies не менялись, обязательный audit остаётся частью PR-head/exact Windows Quality Gate.

## 4. Performance и resource evidence

Benchmark path (`scripts.benchmark_pre_rm156_collector_p3`, deduplicator, normalizer, engine и
fixture) byte-identical exact EIS baseline. Нормативы P1/P3 и controlled high-priority command не
изменялись.

- Первый Mos diagnostic: p50 `9 609.453 ms`, p95 `9 956.968 ms`, regression `22.9806%`, RSS
  `65 744 896`; absolute p95/RSS/resource gates прошли, baseline delta не прошёл.
- Второй diagnostic: p50 `9 571.376 ms`, p95 `9 880.700 ms`, regression `22.0386%`, RSS
  `71 299 072`; time delta и RSS не прошли. Пороги не ослаблялись.
- Same-host immutable EIS control сразу после stop-line прошёл: p50 `7 127.757 ms`, p95
  `7 272.147 ms`, regression `-10.1802%`, RSS `47 316 992`.
- Немедленный Mos reproduction в тех же условиях прошёл все gates: p50 `6 962.190 ms`, p95
  `7 117.944 ms`, regression `-12.0848%`, RSS `62 406 656`, exact 10 000 raw / 5 000 merged.
- 25 cycles: tasks `1/1`, threads `1/1`, handle growth `0`, temp files `0`; cancellation
  `16.407 ms`. Неуспешные diagnostics сохранены как host-load variance evidence, а не удалены и не
  превращены в проход ослаблением benchmark/thresholds.

## 5. Merge evidence и rollback

- PR #126 head `1943d57dc944490d1fd30051be289624b22d7f4b`; PR-head run `29946701032`
  успешен, jobs `89013783563` (Python 3.12) и `89013783542` (Python 3.13).
- Merge commit `b4704480010a363e02ad80fe579d5c836cd04509`; exact merge-SHA push-run
  `29947263908` успешен, jobs `89015703288` (Python 3.12) и `89015703371` (Python 3.13).
  Dependency audit успешен в обоих PR-head и exact matrix jobs.
- Только после exact success создан отдельный `codex/pre-rm156-collector-provider-identity`.

Rollback — отключить provider existing manager policy и revert Mos feature merge. Schema downgrade,
удаление accepted pages/artifacts/checkpoints или user data не выполняются. Token/keyring data не
входят в repository и rollback не затрагивает credential owner.
