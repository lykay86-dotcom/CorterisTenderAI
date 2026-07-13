# RM-111 — аудит и бизнес-границы AI Orchestrator

Дата: 13 июля 2026 года. Статус: `IN PROGRESS`.

## Цель

RM-111 должен определить единый orchestration contract для уже существующих
AI-возможностей без создания второго analyzer, repository, decision engine или
параллельного full-analysis flow.

Orchestrator должен координировать существующие детерминированные и AI-сервисы,
сохраняя следующие инварианты:

- критический стоп-фактор имеет приоритет над score и AI;
- AI не изменяет подтверждённое решение RM-107;
- отсутствующие факты не создаются;
- вывод без проверяемого evidence не повышает уверенность решения;
- offline/fallback режим остаётся рабочим без API;
- ошибки provider, schema, cache и SQLite деградируют безопасно.

## Переиспользуемые компоненты

- `app/core/ai/analyzer.py` и `app/core/ai/schemas.py`;
- `app/core/ai/document_context.py`;
- `app/core/ai/repository.py`;
- `app/tenders/full_analysis.py`;
- `app/tenders/participation_decision_service.py`;
- `app/tenders/participation_decision_policy.py`;
- `app/tenders/tender_summary.py`;
- текущие UI и HTML/JSON exporters.

До отдельного design-аудита не допускается создание параллельного механизма с
той же ответственностью.

## Обязательный prerequisite

По решению владельца к RM-111 назначен отдельный технический work package:

1. offline-тесты не читают Windows Credential Manager;
2. offline-тесты не выполняют сетевые обращения;
3. сохранённые пользовательские credentials не меняют результат тестов;
4. полный pytest проходит в обычном и изолированном окружении;
5. добавлен фиксированный mypy-контур без глобального `ignore_errors`;
6. опубликован Windows GitHub Actions gate для Python 3.12 и 3.13;
7. Ruff check и format check входят в обязательные проверки;
8. C19 live-run вынесен в отдельную ручную/разрешённую операцию.

Фактическое основание назначения: на чистом `b4c1cc7` обычный baseline дал
`719 passed, 2 failed`, потому что два offline-теста прочитали системный keyring,
а один из них выполнил реальный запрос. При временно пустом keyring получено
`721 passed`.

До закрытия prerequisite реализация AI Orchestrator не начинается.

### Результат реализации prerequisite

В отдельном quality-gate пакете подготовлены:

- явная изоляция конфигурации providers от Windows Credential Manager при
  передаче тестового environment;
- безопасный диагностический режим `--no-keyring` без вывода токена;
- проверка отслеживаемых файлов на секреты и очистка отслеживаемых generated
  artifacts;
- фиксированный mypy-контур для четырёх критичных модулей без `ignore_errors`;
- Windows GitHub Actions matrix для Python 3.12 и 3.13 с Ruff, pytest,
  migration/build/import smoke checks и аудитом зависимостей;
- обновление уязвимых версий `cryptography`, `Pillow` и `py7zr`.

Локальная приёмка 13 июля 2026 года:

- обычный Windows Credential Manager: `725 passed`;
- принудительно пустой keyring: `725 passed`;
- Ruff check и format check: успешно;
- mypy: успешно для 4 файлов;
- security scan: успешно;
- dependency audit: известных уязвимостей нет;
- migration, composition-root, public-import и build/release smoke checks:
  успешно.

Окончательное закрытие prerequisite требует зелёного выполнения опубликованной
GitHub Actions matrix на Python 3.12 и 3.13. До этого статус остаётся
`IN PROGRESS`.

## Вне области RM-111

- выбор конкретного AI-провайдера — RM-112;
- локальная AI-модель — RM-113;
- OpenAI-compatible API — RM-114;
- новая строгая схема ответа — RM-115;
- новый механизм citations/provenance — RM-116;
- анализ ТЗ/договора/заявки и отдельных рисков — RM-117–RM-123;
- C17 canonicalization — будущий RM-137 или RM-140;
- C19 connection/live verification — будущий RM-136 или RM-139;
- изменение БД без отдельной миграции;
- исправление `.gitignore`, mypy и CI вне назначенного prerequisite.

## Acceptance аудита RM-111

- описана одна ответственность Orchestrator;
- перечислены существующие компоненты для переиспользования;
- зафиксированы детерминированные инварианты;
- отсутствует реализация функций следующих RM;
- назначенный quality-gate prerequisite имеет воспроизводимый исходный baseline;
- открытые C17/C19 пробелы не объявлены закрытыми;
- бизнес-код и БД в docs-only PR не изменены.

## Следующий разрешённый шаг

Принять отдельный PR RM-111 quality-gate prerequisite после зелёной Windows
matrix на Python 3.12 и 3.13. Только после этого разрешён design/implementation
этап самого AI Orchestrator.
