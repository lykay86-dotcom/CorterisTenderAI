# RM-127 — аудит ownership вкладок раздела «Тендеры»

## 1. Паспорт аудита

- Дата доказательного среза: `2026-07-16T03:56:35+03:00`.
- Baseline SHA: `f34c66b7adf2c175c5a48f17db4f12e154745813` (`origin/main`).
- Ветка: `feat/rm-127-tender-workspace-tabs`; отдельный worktree.
- Среда: Windows 10 `10.0.19045.0`, `Russian Standard Time`/UTC+03:00,
  Python `3.12.7`, Qt offscreen.
- Scope audit gate: docs-only; application code, зависимости, DB schema и сеть не изменялись.

Entry gate пройден: RM-126/RM-126.1 имеют статус `DONE`, RM-127 — единственный
`IN PROGRESS`, RM-128–RM-200 — `PLANNED`; открытых PR и remote-веток RM-127 нет.
Основной checkout с пользовательскими `.agents/` и `skills-lock.json` не изменялся.

## 2. Проверенный baseline

Источники: canonical roadmap/DoD/history, `docs/RM-126_AUDIT.md`,
`docs/RM-126_REQUIREMENTS.md`, bootstrap, modern/legacy shell, Dashboard widgets,
`TenderSearchUiController`, tender dialogs, релевантные тесты и история ключевых файлов.

Проверены исторические точки:

- `a537165` — modern application shell;
- `a1d8fa0` — profile search и controller в main UI;
- `27562ed` — provider/Collector actions;
- `c395f3a` — C11 full-analysis workflow;
- `f09d07e` — RM-126 audit и решения D-01–D-10.

Baseline tests:

| Контур | Результат |
|---|---|
| Focused controller/dialog/bootstrap | `60 passed in 5.38s` |
| Full pytest | `1524 passed in 61.54s` |

Системный `C:\Program Files\Python312\python.exe` не содержит `pytest`; тесты запущены
каноническим проектным `C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe`. Общий
`%TEMP%\pytest-of-*` недоступен (`WinError 5`), поэтому использован изолированный
repository-local `--basetemp`. До выбора `--basetemp` 46 тестов прошли, 14 завершились
на setup, не исполняя application code; это environment-only blocker.

## 3. Текущий ownership UI

| Компонент | Текущий владелец | Фактическая роль |
|---|---|---|
| Production shell | `ModernMainWindow` | единственное показываемое главное окно |
| Workspace/sidebar/topbar | `DashboardLayout` | маршрутизация страниц по строковым keys |
| Tender content | скрытый `app.ui.main_window.MainWindow` | строит tabs, widgets и legacy callbacks |
| Tender page в stack | `centralWidget`, извлечённый через `takeCentralWidget()` | перенесён из скрытого legacy shell |
| Tender runtime/actions/dialogs | один `TenderSearchUiController` из `bootstrap()` | канонический controller и workers |
| Dashboard feed | `DashboardController`/`DashboardPage` | выбирает ID и передаёт его modern shell |

`ModernMainWindow` напрямую:

1. импортирует `MainWindow as LegacyMainWindow`;
2. создаёт `_legacy_window` и вызывает `hide()`;
3. вызывает `takeCentralWidget()` и меняет parent/window flags;
4. вызывает `_legacy_window.refresh()`;
5. читает `_legacy_window.table` и строки ID;
6. устанавливает `_legacy_window.current_id`;
7. вызывает `_legacy_window.select_row(row, 0)`;
8. записывает topbar query в `_legacy_window.catalog_query`;
9. закрывает и удаляет `_legacy_window` в `closeEvent()`.

Это подтверждает RM126-F-001: production показывает один shell, но владеет вторым скрытым
`QMainWindow` как временным builder/lifecycle owner.

## 4. Текущий tab contract

Top-level `QTabWidget` создаётся в `MainWindow._build()` в точном порядке:

| Index | Будущий stable key | Текущий label |
|---:|---|---|
| 0 | `overview` | Панель управления |
| 1 | `analysis` | Анализ тендера |
| 2 | `estimate` | Смета |
| 3 | `catalog` | Оборудование и бренды |
| 4 | `readiness` | Проверка заявки |
| 5 | `tools` | Инструменты 1.4 |
| 6 | `price_monitor` | Мониторинг цен 1.5 |
| 7 | `settings` | Настройки |

Nested settings tabs:

| Index | Будущий stable key | Текущий label |
|---:|---|---|
| 0 | `platforms` | Площадки API/RSS/FTP |
| 1 | `ai` | ChatGPT / ИИ |
| 2 | `company` | Компания и реквизиты |
| 3 | `economics` | Лицензии и экономика |
| 4 | `templates` | Фирменные бланки |
| 5 | `database` | Диагностика БД |

У tabs и tab pages сейчас нет устойчивых RM-127 `objectName`. Начальные индексы обоих
`QTabWidget` равны 0. Sidebar меняет outer `QStackedWidget` и topbar title, но не меняет
inner tab и не передаёт focus. Topbar compatibility search выбирает outer page `tenders`
и заполняет `catalog_query`, но не выбирает tab `catalog` и не запускает поиск. Dashboard
open path выбирает outer page, обновляет таблицу, выбирает найденную строку и вызывает
`select_row`; при отсутствии строки выполняется честный no-op.

## 5. QAction inventory

Один `TenderSearchUiController` создаёт следующие канонические instances:

| Attribute | objectName | Shortcut | Slot |
|---|---|---|---|
| `action` | `actionTenderSearchProfiles` | `Ctrl+Shift+F` | `open_profiles_dialog` |
| `registry_action` | `actionTenderRegistry` | `Ctrl+Shift+R` | `open_registry_dialog` |
| `providers_action` | `actionTenderProviders` | `Ctrl+Shift+S` | `open_provider_manager_dialog` |
| `collector_action` | `actionTenderCollector` | `Ctrl+Shift+C` | `open_collector_dialog` |
| `company_capability_action` | `actionCompanyCapabilityProfile` | — | `open_company_capability_dialog` |
| `matching_catalog_action` | `actionMatchingCatalog` | — | `open_matching_catalog_dialog` |
| `aggregator_discovery_action` | `actionAggregatorDiscoveryQueue` | — | `open_aggregator_discovery_dialog` |

Вложенный единственный `TenderCollectorSchedulerUiController` создаёт и устанавливает в те
же menu/toolbar `actionTenderCollectorSchedule` (`Ctrl+Shift+P`) и
`actionTenderCollectorNotifications` (`Ctrl+Shift+N`). `install_on_main_window()` уже
idempotent по identity и переиспользует `tendersMenu`/`tenderSearchToolBar`; второй controller
или action factory не нужен.

## 6. Входы в tender workflow

- Sidebar `tenders` и Dashboard action «Найти тендеры» выбирают outer page.
- Dashboard tender feed и `BusinessWorkflowPage.tender_open_requested` вызывают
  `ModernMainWindow._open_tender_from_dashboard()`.
- Topbar Enter вызывает compatibility price/equipment query через `_global_search()`.
- Menu, toolbar и shortcuts открывают profiles/search, registry, providers, Collector,
  capability, matching, discovery, schedule и notifications.
- Profiles dialog запускает существующий sync profile runner; Collector dialog/scheduler —
  существующую async Collector session. Их объединение относится к RM-128/RM-138.
- Results/registry открывают documents, verification, requirements, score, commercial estimate
  и full analysis через тот же controller.

Пути открытия legacy tender row: Dashboard feed и две business workflow pages сходятся в
`_open_tender_from_dashboard()`. Registry/results используют canonical `registry_key` и свои
существующие dialogs, а не legacy table selection.

Пути C11 full analysis:

1. `TenderRegistryDialog.full_analysis_requested(str)` →
   `TenderSearchUiController.open_full_analysis`;
2. `TenderSearchResultsDialog.full_analysis_requested(UnifiedTender)` → `tender_registry_key()` →
   тот же `open_full_analysis`;
3. controller создаёт один `TenderFullAnalysisDialog` и использует существующий
   `runtime.full_analysis_service`; repeated request переиспользует dialog/worker guards.

## 7. Composition I/O и lifecycle

`create_tender_search_runtime()` и UI composition создают repositories/services, но provider
network начинается только по явному run/check action. В `MainWindow` коннекторы ЕИС и manual
tester вызываются только button callbacks. Автоматического live network I/O в проверенном
composition path не найдено. UI читает локальные JSON/SQLite/catalog/theme settings;
`QTimer.singleShot` запускает только DB diagnostics refresh.

Закрытие modern shell сейчас останавливает Dashboard и закрывает скрытый legacy shell. Полный
shutdown tender workers остаётся отдельным RM-140 gap; RM-127 не должен расширять lifecycle scope,
но обязан убрать позднее обращение к удалённому `_legacy_window`.

## 8. Риски extraction

1. Legacy class (~1080 строк) совмещает widget assembly и callbacks; big-bang rewrite опасен.
2. Callback `select_row()` ожидает `statusBar()` QMainWindow; reusable page нужен явный status sink.
3. Existing widgets/attributes используются многочисленными callbacks внутри одного owner;
   их массовое переименование создаст скрытые regressions.
4. QAction lifetime принадлежит controller; page не должна reparent или пересоздавать actions.
5. Dashboard refresh выполняется в фоне; extraction не должна создавать второй controller/runtime.
6. Topbar placeholder говорит о tender search, но фактический contract — price catalog; его нельзя
   расширять до RM-128.
7. Legacy wrapper может быть нужен для standalone compatibility; удаление без callers/tests
   необоснованно.

## 9. Выбранный вариант extraction

Выбран incremental ownership extraction без переноса business logic:

- существующий widget/callback owner становится `TenderWorkspacePage(QWidget)`;
- page владеет единственным набором tabs и получает узкий status-bar sink;
- `MainWindow(QMainWindow)` остаётся тонким compatibility wrapper с одним экземпляром page;
- production `ModernMainWindow` создаёт page напрямую и больше не создаёт wrapper;
- stable keys/objectNames добавляются поверх текущего порядка/labels;
- narrow API: `refresh_tenders()`, `open_tender()`,
  `apply_compatibility_search_text()`, `select_section()`, `bind_tender_actions()`;
- один controller передаёт page те же QAction instances idempotently после своей обычной
  установки в menu/toolbar.

Вариант не создаёт второй shell: production создаёт только `ModernMainWindow`, а legacy wrapper
остаётся неиспользуемым compatibility entry point. Он не создаёт второй workflow: repositories,
callbacks, controller, actions, dialogs, workers, search runtime, Collector и C11 service остаются
существующими объектами и путями.

## 10. Audit decision

**ACCEPTED FOR DOCS-ONLY AUDIT COMMIT.** Блокеров scoped extraction не найдено. Production
implementation разрешена только после фиксации этого аудита и
`docs/RM-127_IMPLEMENTATION_PLAN.md` отдельным commit. Search semantics, DB, providers, decision,
AI и lifecycle RM-140 остаются вне scope.
