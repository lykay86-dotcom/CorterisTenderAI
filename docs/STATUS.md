# Текущее состояние CorterisTenderAI

Обновлено: 15 июля 2026 года.

## Активный этап

**RM-126 — аудит раздела Тендеры**

Статус: `IN PROGRESS`

Этап назначается только после merge реализации RM-125, успешного post-merge Windows Quality
Gate на merge-коммите и merged docs-only closeout. До изменения application-кода RM-126
требуется отдельный аудит существующих Tender UI, search/runtime, adapters, repositories,
collectors и deterministic decision boundaries.

## Предыдущий этап

**RM-125 — стабилизация AI-платформы**

Статус: `DONE`

Подтверждение:

- feature PR #53 слит в `main` коммитом `bdceb70`;
- post-merge Quality Gate run `29450245855` успешен на Python 3.12 и 3.13;
- полный Windows suite: Python 3.12 — `1496 passed in 95.46s`, Python 3.13 —
  `1496 passed in 61.69s`;
- единый immutable execution contract v1 exact-связывает provider, model и все версии анализа;
- typed cache lookup пропускает corrupt/future/mismatched rows и может найти более старую exact
  current-compatible запись без mutable repository warning state;
- empty-source, provider-error и cacheability paths имеют bounded deterministic semantics без
  retry, raw provider errors или stale fallback;
- per-key coordinator сериализует одинаковые run/recheck и не блокирует разные ключи;
- participation decision получает AI-анализ только явно, без implicit latest fallback;
- сохранены один provider call site, analyzer/service/Orchestrator/repository, одна
  `RUNNING_AI` stage и существующий runtime graph;
- provider schema/format v4, prompt v6, payload v10, context v6, citation resolver v1 и recheck
  policy v1 не изменены; analyzer повышен до v12;
- RM-107 score/recommendation/actions/evidence/confidence, commercial estimate и абсолютный
  приоритет critical stop-factor не изменены;
- новая AI-stage, provider call, repository, БД, таблица или migration не добавлены;
- локально: target `315 passed in 7.15s`, full `1496 passed in 58.68s`, Ruff (`523 files`),
  mypy (20 файлов), secret scan, dependency audit и diff-check успешны;
- post-merge gate подтвердил Ruff (`523 files`), mypy (20 файлов), secret scan, offline,
  migration, composition и build smoke tests, а также dependency audit на обеих версиях Python.

## Ранее завершённый этап

**RM-124 — повторная проверка AI**

Статус: `DONE`

Подтверждение:

- feature PR #51 слит в `main` коммитом `cfd044e`;
- post-merge Quality Gate run `29437124384` успешен на Python 3.12 и 3.13;
- полный Windows suite: Python 3.12 — `1466 passed in 108.68s`, Python 3.13 —
  `1466 passed in 80.07s`;
- pure comparator использует exact provenance/fingerprint/version contract и только locally
  verified findings;
- RM-107 score/recommendation и critical stop-factor policy не изменены.

## Текущее действие

Провести отдельный аудит RM-126 до изменения раздела Тендеры, search/runtime, adapters,
repositories, collectors или deterministic decision boundary.
