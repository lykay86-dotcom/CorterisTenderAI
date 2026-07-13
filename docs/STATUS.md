# Текущее состояние CorterisTenderAI

Обновлено: 13 июля 2026 года.

## Подтверждение RM-107

RM-107 повторно проверен по расширенному Definition of Done. Decision Engine
возвращает score, recommendation, confidence, explanation, причины с impact,
стоп-факторы, missing data и action plan. Все поля отображаются в UI и входят
в JSON. Полный регресс после доработки: 633 passed.

## Активный этап
**RM-111 — AI Orchestrator**

Статус: `IN PROGRESS`

Обязательный prerequisite RM-111: герметизация offline-тестов и
воспроизводимый Windows quality gate. На чистом `origin/main` (`b4c1cc7`)
baseline дал `719 passed, 2 failed`: два offline-теста прочитали сохранённый
токен из Windows Credential Manager, а диагностический тест выполнил реальный
API-запрос. С временно пустым keyring оба теста проходят (`2 passed`).

Quality-gate пакет реализован локально. Полный регресс даёт `725 passed` как с
обычным Windows Credential Manager, так и с принудительно пустым keyring. Ruff,
фиксированный mypy-контур, security scan, migration/build/import smoke checks и
dependency audit проходят. Добавлена Windows GitHub Actions matrix для Python
3.12 и 3.13; prerequisite остаётся `IN PROGRESS` до её зелёного выполнения в PR.

До закрытия prerequisite запрещено начинать реализацию AI Orchestrator. Пакет
не должен менять AI-бизнес-логику, C17 canonicalization или C19 live verification.

## Предыдущий этап
**RM-110 — стабилизация Tender Intelligence**

Статус: `DONE`

Подтверждение:
- сохранён обязательный аудит текущей цепочки;
- введены безопасные статусы и версия payload;
- структурно неверный ответ AI деградирует без исключения;
- кеш учитывает версии prompt/schema/analyzer/context и лимиты;
- повреждённая история пропускается до предыдущей корректной записи;
- контекст ограничен, дедуплицирован и формируется воспроизводимо;
- ошибки AI/SQLite не блокируют RM-107, summary, UI и экспорт;
- текущий безопасный AI-результат не заменяется устаревшим кешем в RM-107;
- `701 passed`, включая `tests/test_crash_reporting.py`;
- `python -m ruff check .` проходит;
- `python -m ruff format . --check` проходит.

## Ранее завершённый этап
**RM-109 — AI-анализ тендерной документации**

Статус: `DONE`

Подтверждение:
- строгие схемы документов, требований, рисков и доказательств;
- проверка точной цитаты и маркировка неподтверждённых выводов;
- контекст из локально извлечённых документов;
- история и повторное использование по fingerprint;
- интеграция с полным анализом и RM-107;
- отдельная вкладка «AI-анализ» и экспорт HTML/JSON;
- 631 passed (без отдельного теста crash-reporting).

## Текущее действие
Опубликовать и принять отдельный PR ветки `fix/rm-111-quality-gate` после
зелёной Windows matrix. AI Orchestrator, C17 и C19 в пакет не входят.
