# PRE-RM-156 Collector P4 — EIS reference adapter validation

Дата: 22 июля 2026 года.

Статус: `ACCEPTED`; PR-head и exact merge-SHA Windows gates успешны.

## 1. Scope и baseline

- Exact baseline: P3 merge `cfc473e8a11c6c2c7bc201bbac45aa38404d7cc2`.
- Ветка: `codex/pre-rm156-collector-eis-reference`.
- Test-first commit: `a0842a2`; implementation commit: `c4a4c7a`.
- Scope ограничен первым P4 provider package: публичным EIS adapter. `mos_supplier`, provider
  identity/catalog P5, schema/dependencies и deterministic decision/scoring не изменены.
- Live network canary не запускался: P4 не является разрешением на внешний scraping. Readiness
  остаётся честным `IMPLEMENTED_OFFLINE` до отдельной разрешённой live verification.

## 2. Реализованный contract

- `AsyncEisTenderProvider` использует explicit `eis-public-html-v1` и существующий
  `eis-search-v3`; новый parser, HTTP runtime, engine, repository или checkpoint owner не создан.
- Shared `ProviderCollectionPage` выполняет bounded pagination: максимум 20 EIS pages, 500 items
  на page и 50 MiB response; пустая страница завершает неизвестный-total cursor без loop.
- Resume использует только совместимый typed fingerprint/contract/parser checkpoint. Cursor
  продолжает незавершённый run без изменения date window; завершённый checkpoint применяет
  conservative sliding overlap от committed timestamp.
- Provider больше не записывает checkpoint из `search()`. Engine атомарно сохраняет accepted page,
  raw artifact metadata и checkpoint до запроса следующей страницы; `C-CP-001` снят.
- Search/detail/document responses сохраняются существующим content-addressed `RawArtifactStore` с
  sanitized URL, SHA-256, media type/encoding, contract/parser versions, parse outcome и retention.
  Search artifact references commit-coupled с accepted page в существующей Collector DB.
- CAPTCHA/access denied/structure drift остаются fail closed; rejected body не попадает в public
  error. Connection mode остаётся truthful `public_html_async`, а descriptor не заявляет official
  API.
- Cancellation проверяется до каждой следующей страницы; construction/factory не выполняют сеть.

## 3. Test-first и локальные gates

- До implementation новый P4 contour дал `7 failed`: отсутствовали versioned contract,
  EIS iterator/resume/artifacts, а legacy provider checkpoint опережал acceptance.
- После implementation target contract: `7 passed`; расширенный EIS/P3/P2/factory contour:
  `82 passed in 15.51s` (финальный повтор `82 passed in 16.26s`).
- Full pytest: `2449 passed, 2 warnings in 258.23s`; xfail отсутствуют.
- Secret scan, Ruff check, Ruff format (`800 files`), mypy (`20 source files`) и diff-check успешны.
- Mandatory offline pair: `2 passed`; migrations: `5 passed`; bootstrap: `1 passed`;
  build/frozen: `9 passed`; RM-155 compatibility guard успешен.
- Локальный `pip-audit` не выполнен: sandbox запретил отправку dependency inventory в PyPI.
  Dependencies не менялись; обязательный audit остаётся частью PR-head/exact Windows Quality Gate.

## 4. Performance и resource evidence

Benchmark path (`deduplicator`, `normalizer`, engine и fixture) byte-identical P3 baseline. Exact
controlled command и нормативы P3 не изменялись.

- Первый P4 diagnostic: p50 `9 700.388 ms`, p95 `9 800.204 ms`, regression `21.0443%`, RSS
  `48 140 288`; time regression превысил 20% примерно на 85 ms, остальные gates прошли.
- Same-host immutable P3 control показал независимую variance: p95 `9 138.539 ms` прошёл, но RSS
  `75 063 296` превысил 64 MiB, хотя код benchmark path идентичен.
- Focused P4 reproduction прошла все gates: p50 `8 939.589 ms`, p95 `9 040.632 ms`, regression
  `11.6627%`, RSS `53 055 488`, exact 10 000 raw / 5 000 merged.
- 25 cycles: tasks `1/1`, threads `1/1`, handle growth `0`, temp files `0`; cancellation
  `16.427 ms`. Root cause первого near-threshold результата классифицирован как host measurement
  variance; production thresholds, fixture и code не ослаблялись.

## 5. Merge evidence и rollback

- PR #125 head `db69f47891e2ea71187d26ad84e084c7de45d440`; PR-head run `29943116366` успешен,
  jobs `89001709249` (Python 3.12) и `89001709307` (Python 3.13).
- Merge commit `300385108082746ac8818dad19104f57618366a9`; exact merge-SHA push-run
  `29943599187` успешен, jobs `89003335120` (Python 3.12) и `89003335026` (Python 3.13).
- Только после exact success создан отдельный `codex/pre-rm156-collector-mos-reference`.

Rollback — отключить provider existing manager policy и revert EIS feature merge. Schema downgrade,
удаление accepted pages/artifacts/checkpoints или user data не выполняются. Старый parser owner и
legacy sync compatibility path не переписывались.
