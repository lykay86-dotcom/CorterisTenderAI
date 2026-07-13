# Повторный аудит RM-001–RM-106

Дата: 13 июля 2026 года.

## Проверенная исходная точка

- репозиторий: `lykay86-dotcom/CorterisTenderAI`;
- ветка аудита: `docs/rm-111-audit-baseline`;
- `origin/main`: `b4c1cc79be605394e646f0741eeb1a832d261350`;
- цели RM-001–RM-106 восстановлены из первого канонического roadmap в
  `6031e1d`;
- локальные пользовательские изменения сохранены отдельно и не переносились в
  аудиторскую рабочую копию.

## Воспроизводимость baseline

Обычный запуск `python -m pytest -q` в пользовательском окружении дал
`719 passed, 2 failed`. Оба отказа вызваны чтением сохранённого токена Портала
поставщиков из Windows Credential Manager:

- `test_manager_exposes_all_sources_without_network` получил `unknown` вместо
  ожидаемого `not_configured`;
- `test_mos_diagnostic_runs_from_scripts_path_without_app_error` выполнил
  реальный API-запрос и вернул `0` вместо ожидаемого `2`.

С временным `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring` полный набор
дал `721 passed`. Отдельный повтор двух отказавших тестов также дал `2 passed`.
Следовательно, кодовая база проходит изолированный набор, но стандартный
offline baseline не герметичен. Исправление назначено обязательным prerequisite
RM-111 и не считается выполненным этим docs-only аудитом.

Дополнительные результаты:

- `python -m ruff check .` — успешно;
- `python -m ruff format . --check` — успешно, 490 файлов;
- публичный импорт `DashboardController` — успешно;
- опубликованного workflow в `.github/workflows` нет;
- обязательной mypy-конфигурации нет.

Серверная сверка PR:

- PR #19 (`fdd57b1`) объединён с `main`; описание заявляет `701 passed`, Ruff
  check/format и прямо отмечает отсутствие mypy-конфигурации;
- PR #20 (`b4c1cc7`) объединён с `main`; описание заявляет `721 passed`, Ruff
  check/format и сохраняет C19 в `UNVERIFIED`;
- эти заявления согласуются с локальным изолированным прогоном, но не заменяют
  независимый GitHub Actions gate, поскольку workflow отсутствует.

## Повторная классификация замечаний

| Область | Статус | Проверенное основание |
|---|---|---|
| Decimal на Collector/API/JSON-границах | `FIXED_ON_MAIN` | `app/core/json_serialization.py`, `tests/test_json_serialization.py`, `tests/test_collector_money_contract.py`; Decimal сериализуется строкой, запрет float покрыт тестом. |
| Неизвестный timezone и mixed naive/aware datetime | `FIXED_ON_MAIN` | Исправления `629c23a`; регрессия в `tests/test_collector_freshness.py` и `tests/test_collector_stop_factor.py` проходит в изолированном baseline. |
| C20 official identity matching | `FIXED_ON_MAIN` | Исправления `7e5636e`; `tests/test_aggregator_discovery.py` покрывает подтверждение и отклонение официальной карточки. |
| Единый `SourceTrustLevel` и владелец Collector DDL | `FIXED_ON_MAIN` | Исправления `96c6cf1`; контракт централизован в `app/tenders/collector/verification.py`, DDL — в `schema.py`. |
| Redaction приватных crash-report путей | `FIXED_ON_MAIN` | `adcd0a0`; `tests/test_crash_reporting.py` проходит. |
| Публичный `DashboardController` | `FIXED_ON_MAIN` | Импорт из `app.ui.controllers` успешен; экспорт находится в `app/ui/controllers/__init__.py`. |
| Ruff baseline | `FIXED_ON_MAIN` | Check и format check успешны на `b4c1cc7`. |
| C17 canonicalization | `OPEN` | `canonical_term` сохраняется, но `MatchingCatalog.to_search_profile()` строит профиль из `term`; отдельный пакет должен быть назначен RM-137 или RM-140. |
| C19 live verification | `UNVERIFIED_EXTERNAL` | Offline gate и запрет fixture→`WORKING` покрыты `tests/test_vertical_source_verification.py`; разрешённого end-to-end live-артефакта нет. |
| Offline credential isolation | `OPEN` | Стандартный baseline зависит от Windows Credential Manager и может обратиться к сети; назначено prerequisite RM-111. |
| `.gitignore` и generated artifacts | `OPEN` | `.gitignore` всё ещё содержит PowerShell-обёртку; `.worktrees/` и `.pytest_tmp*/` не описаны корректно. |
| Обязательный mypy-контур | `OPEN` | `mypy` есть в dev-зависимостях, но конфигурация и фиксированный проверяемый список отсутствуют. |
| GitHub Actions quality gate | `OPEN` | Каталог `.github/workflows` отсутствует; серверный gate для Python 3.12/3.13 не опубликован. |
| Branch protection | `UNVERIFIED_EXTERNAL` | Настройки GitHub не доказаны локальным репозиторием и не изменялись. |
| C17/C19 бизнес-исправления в RM-111 | `OUT_OF_SCOPE_FOR_RM_111` | Решением владельца RM-111 включает только credential hermeticity и quality-gate prerequisite; C17/C19 остаются отдельными пакетами. |

## Вывод по RM-001–RM-106

Первый канонический roadmap позволяет восстановить индивидуальные цели всех 106
пунктов, но не исходные acceptance criteria и не историческую связь каждого
номера с отдельным коммитом или PR. Поэтому наличие современной реализации не
автоматически повышает пункт до `DONE`.

Индивидуальная оценка приведена в `docs/RM_001_106_TRACEABILITY.md`. Статус
`DONE` используется только там, где одновременно восстановлена цель, задан
проверяемый текущий критерий, найден код, существует целевой тест и его результат
подтверждён изолированным baseline. В остальных строках оставлены `PARTIAL`,
`NOT_DONE` или `UNVERIFIED` с явным пробелом.

## Разрешённые следующие пакеты

1. Docs-only PR: принять повторный аудит и матрицу трассируемости.
2. RM-111 quality-gate prerequisite: герметизировать credentials, исправить
   `.gitignore`, добавить mypy-контур и Windows CI без изменений AI/C17/C19.
3. C17: отдельный RM-137 или RM-140 после явного назначения.
4. C19: отдельный RM-136 или RM-139 и только разрешённый live-run.
