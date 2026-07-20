# Техническое задание на полную пересборку интерфейса CorterisTenderAI

Версия: `draft-2`

Дата: 21 июля 2026 года

Roadmap-контур: `RM-143–RM-155`

## 1. Назначение

Документ определяет целевой дизайн всего Windows-приложения CorterisTenderAI на базе
подключённого Figma-референса large-screen visualization и переводит визуальное направление в
проверяемые требования для PySide6.

ТЗ охватывает дизайн-систему, production shell, Dashboard, тендерные и финансовые аналитические
экраны, карточку тендера, таблицы, диалоги, формы, фоновые операции, accessibility,
производительность и visual QA.

Документ не разрешает выполнять RM параллельно. Каждый пакет начинается только после выполнения
Definition of Done предыдущего этапа и обновления канонических `STATUS`, `ROADMAP` и
`ROADMAP_HISTORY`.

## 2. Figma-источник

- Файл: [200 sets of large screen visualization](https://www.figma.com/design/om0Q6O8L8LUkM1CBnzeTKN/大屏可视化200-套免费分享-200-sets-of-large-screen-visualization-for-free-sharing--Community---Community-?node-id=1-38)
- File key: `om0Q6O8L8LUkM1CBnzeTKN`.
- Страница: `1:38` (`页面-Content`).
- Канонический экран: `41:35` (`综合治理`).
- Размер канонического экрана: `1920×1080`.

Figma MCP подтвердил, что `41:35` содержит редактируемую структуру из frame, vector, text и image
assets. Design context успешно извлечён для целевого screen node. В screen используются Inter,
светлый текст `#E6F7FF`, cyan accent `#18B8FF`, глубокий почти чёрный фон, технические контуры,
графики, gauges, центральная карта и трёхзонная композиция.

Figma variables для узла отсутствуют. Следовательно, общие токены и component variants не
считаются готовой библиотекой: их необходимо формализовать в проекте, проверить на контраст и
привязать к PySide6. Временные MCP asset URLs не используются в production, потому что истекают.

## 3. Нормативные источники проекта

Требования применяются совместно с:

- `docs/STATUS.md`;
- `docs/ROADMAP.md`;
- `docs/DEFINITION_OF_DONE.md`;
- `docs/ROADMAP_HISTORY.md`;
- `docs/RM-141_UI_AUDIT.md`;
- `docs/RM-141_UI_INVENTORY.md`;
- `docs/RM-141_USER_JOURNEYS.md`;
- `docs/RM-141_REDESIGN_HANDOFF.md`;
- `docs/RM-142_INFORMATION_ARCHITECTURE_CONTRACT.md`.

При конфликте визуального референса и детерминированного продукта приоритет имеют business,
security, accessibility, data ownership и navigation contracts репозитория.

## 4. Продуктовая цель

Пересобрать интерфейс как профессиональный командно-аналитический центр для управления тендерами:

- оператор за несколько секунд понимает состояние закупок, риски и требуемые действия;
- критические stop-факторы и неподтверждённые данные видны раньше декоративной аналитики;
- данные можно исследовать от общей картины до точного tender/workflow ID;
- поиск, анализ, документы, расчёты и workflow остаются единым рабочим процессом;
- плотная визуализация не ухудшает читаемость форм, таблиц и длинного русского текста;
- внешний вид консистентен во всех production pages и dialogs;
- приложение остаётся offline-capable и не получает сетевую зависимость от Figma.

## 5. Основной принцип адаптации

Figma задаёт язык визуализации, но не предметные данные и не структуру бизнес-логики.

Переносится:

- глубокая тёмная основа;
- холодный cyan/blue accent;
- тонкие технические рамки и направляющие;
- модульная трёхзонная композиция;
- центральный смысловой фокус;
- плотные KPI, charts, gauges, timelines и status indicators;
- геометрический header и компактная служебная информация;
- визуальное разделение overview, context и action zones.

Не переносится автоматически:

- китайский текст и демонстрационные значения;
- карта как обязательный центр каждого экрана;
- случайные KPI без владельца формулы;
- абсолютное позиционирование из 1920×1080 frame;
- web/Tailwind-код;
- декоративное свечение на каждом control;
- очень мелкий текст, непригодный для desktop accessibility;
- маски, сотни SVG-фрагментов и эффекты, ухудшающие Qt performance;
- публичные Figma assets как runtime dependency.

## 6. Неизменяемые архитектурные границы

1. Приложение остаётся Windows desktop на Python и PySide6.
2. Существующие adapters, analyzers, orchestrators, repositories и DI paths переиспользуются.
3. `DashboardLayout` остаётся единственным navigation owner.
4. Существует один `ModernMainWindow`, один page stack и один route registry.
5. Канонические route IDs, hierarchy, aliases, availability и closed context RM-142 сохраняются.
6. Сохраняются object names, QAction identities, shortcuts и публичные импорты.
7. AI не изменяет approved score, recommendation или critical stop-factor priority.
8. UI не вычисляет domain decisions и не создаёт второй источник KPI.
9. DB/schema/migrations изменяются только в отдельном аудированном пакете, если это необходимо.
10. Нельзя добавлять runtime dependency без dependency/licence/security audit.
11. Theme/design layer не выполняет network, DB, filesystem или keyring I/O.
12. Навигация и возвращение сохраняют stable record ID, filters, selection и focus origin.

## 7. Целевая визуальная система

### 7.1. Общий характер

Целевой образ — `Corteris Command Center`: точный, холодный, технологичный и информационно
плотный. Основная тема тёмная. Light theme сохраняется как полноценная рабочая тема с тем же
контрактом данных и состояний, но без имитации glow на светлом фоне.

Интерфейс не должен выглядеть как игровая HUD-панель. Техническая стилистика подчинена данным:
декоративные линии не конкурируют с labels, statuses и primary actions.

### 7.2. Предварительная палитра

Два значения подтверждены design context Figma; остальные являются целевыми кандидатами и должны
пройти contrast/visual audit до фиксации в `ThemePalette`.

| Семантическая роль | Dark candidate | Light candidate | Статус |
|---|---|---|---|
| app background | `#02070D` | `#F2F7FA` | candidate |
| canvas background | `#04111B` | `#FFFFFF` | candidate |
| panel background | `#071A28` | `#F7FBFD` | candidate |
| elevated panel | `#0B2233` | `#FFFFFF` | candidate |
| border subtle | `#12354A` | `#C8DCE6` | candidate |
| border active | `#18B8FF` | `#007DB8` | Figma/candidate |
| brand primary | `#18B8FF` | `#007DB8` | Figma/candidate |
| brand secondary | `#00E6D7` | `#007F79` | candidate |
| text primary | `#E6F7FF` | `#102A3A` | Figma/candidate |
| text secondary | `#8EB8CA` | `#45697A` | candidate |
| success | `#2FD88F` | `#167A50` | candidate |
| warning | `#F4D35E` | `#8A6500` | candidate |
| danger | `#FF4D5A` | `#B42331` | candidate |
| neutral | `#7296A8` | `#5B7380` | candidate |

Требования:

- normal text — целевой contrast не ниже 4.5:1;
- large text, focus и значимые graphics — не ниже 3:1;
- semantic status имеет текст/иконку и не кодируется только цветом;
- danger зарезервирован для ошибки/критического состояния;
- cyan не используется как универсальный цвет любого числа;
- glow создаётся ограниченным theme-aware эффектом, а не размытой копией каждого элемента.

### 7.3. Типографика

- Figma reference использует Inter; production primary font остаётся локальным Windows font chain
  с Segoe UI, если лицензированный Inter не поставляется как repository-owned asset.
- Роли: display, screen title, section title, KPI value, body, caption, button, table, code/data.
- Числа KPI используют tabular figures, если это поддерживается выбранным font path.
- Единицы измерения визуально слабее значения, но остаются читаемыми.
- Минимальный production text size определяется DPI-тестом, а не мелкими значениями Figma.
- Русские labels проверяются на 30–50% более длинных строках.

### 7.4. Spacing, grid и рамки

- Базовая сетка: 4 px.
- Spacing scale: 4, 8, 12, 16, 20, 24, 32, 40, 48.
- Outer screen margin: 16–24 px в зависимости от viewport.
- Section gap: 12–16 px.
- Panel padding: 12–20 px.
- Border: 1 px; active/focus emphasis: 2 px.
- Radius: 0–4 px для HUD panels, 6–8 px для forms/dialogs; большие pill cards запрещены.
- Угловые технические accents допускаются только через reusable panel primitive.
- Layout реализуется Qt layouts/size policies, а не абсолютными координатами.

### 7.5. Elevation и glow

- Иерархия строится в первую очередь background/border/spacing.
- Glow допускается для active navigation, focus, selected data point и critical alert.
- Shadow/glow tokens должны быть bounded и отключаемыми в performance/high-contrast mode.
- Нельзя использовать animation или blur как носитель обязательной информации.

## 8. Целевой каркас приложения

Production shell должен адаптировать трёхзонную композицию референса:

1. `Command header` — название текущего раздела, global search, freshness, operation status,
   notifications, theme и profile.
2. `Navigation rail` — Dashboard, Tenders и Business Workflow из RM-142; secondary destinations
   показываются контекстно и не становятся false peer routes.
3. `Primary canvas` — главный рабочий контент и выбранная сущность.
4. `Context rail` — filters, provenance, risk/status, pending actions; скрывается или переносится
   на узких размерах.
5. `System strip` — безопасные operation/background states и diagnostic correlation без raw error.

Точный shell реализуется только в RM-144. RM-143 создаёт только tokens/components. Sidebar может
стать компактным navigation rail, но route taxonomy и navigation owner не меняются.

## 9. Адаптивность и размеры

Канонический Figma frame 1920×1080 используется как reference composition, но не как единственный
поддерживаемый размер.

Обязательная матрица:

- 1366×768;
- 1600×900;
- 1920×1080;
- 2560×1440;
- 3840×2160;
- Windows scaling 100%, 125%, 150%, 175%, 200%;
- перенос окна между мониторами с разным DPI.

Правила перестройки:

- wide: left context + center canvas + right context;
- standard: compact navigation + center + один context rail;
- narrow: context rails становятся tabs/drawers, primary action и critical state остаются видимы;
- таблица не ужимается до нечитаемости — включаются column priority и controlled horizontal scroll;
- charts имеют минимальный размер и textual equivalent;
- fixed dimensions допускаются только для audited icons, separators и bounded indicators.

## 10. Библиотека компонентов

Используются и расширяются текущие `app.ui.theme` и `app.ui.widgets`; параллельный `theme_v2` или
`new_ui` запрещён.

### 10.1. Foundation

- semantic color tokens;
- typography tokens;
- spacing, sizing, border, radius, elevation, glow и motion tokens;
- chart series/grid/axis tokens;
- density modes: compact и standard;
- semantic icon registry и deterministic fallback;
- единый global QSS builder и audited local component styles.

### 10.2. Controls

- primary/secondary/ghost/danger/icon buttons;
- search/input/password/numeric fields;
- combo/filter combo;
- checkbox/radio/switch;
- tabs, segmented control и filter chips;
- tooltip, menu и context action;
- progress, spinner и cancellable operation indicator.

Каждый control поддерживает normal, hover, pressed, focus, selected/checked, disabled, read-only,
loading и error там, где состояние применимо.

### 10.3. Data primitives

- `TechnicalPanel` — базовая рамка command-center;
- `SectionHeader` — title, subtitle, freshness, action;
- `KpiTile` — значение, единица, trend, freshness, provenance и drill-down;
- `StatusBadge` и `CriticalAlert`;
- `DataStatePanel` — loading/empty/partial/stale/error/disabled;
- `ChartPanel` — chart, legend, filters, textual equivalent и export;
- `GaugePanel` — только для метрики с диапазоном и объяснимыми thresholds;
- `TimelinePanel` — события с stable identity;
- `EvidencePanel` — source, citation, conflict и freshness;
- `ActionQueue` — приоритетные действия без собственного business ranking;
- `DataTable` — model/view, stable selection, row actions и state overlay;
- `DetailInspector` — выбранная запись, provenance и safe actions.

### 10.4. Forms и dialogs

Формы и dialogs получают стиль reference, но остаются спокойнее аналитических экранов:

- сплошная читаемая поверхность без фоновой сетки за текстом;
- label/buddy/help/error для каждого поля;
- явные default/cancel/destructive actions;
- безопасная обработка длинных paths/IDs без утечки private data;
- focus trap только в modal dialog и корректный focus return;
- подтверждение destructive target по точной identity;
- no raw exception/HTML/user secret.

## 11. Карта экранов всего проекта

### 11.1. Dashboard

Цель — главный command center, а не коллекция случайных карточек.

Композиция:

- header: период, freshness и global operation state;
- верхний KPI belt: только определённые метрики с владельцем формулы;
- центральный focus: tender pipeline/opportunity-risk landscape;
- слева: sources, search coverage, readiness и incoming tenders;
- справа: critical risks, deadlines, verification conflicts и required actions;
- снизу: activity timeline, recent tenders и background operations.

Географическая карта используется только при наличии точных региональных данных и meaningful
drill-down. Иначе центральный образ заменяется pipeline, risk matrix или time-based overview.

### 11.2. Tenders workspace

- primary identity: tender ID, customer, deadline, value, source и freshness;
- approved decision и critical stop-factor видны до AI summary;
- analysis/readiness/estimate/documents/equipment/settings остаются доступными;
- evidence и provenance располагаются рядом с выводом;
- tabs и actions сохраняют RM-127/RM-142 identities;
- deep link открывает ту же запись и возвращает к исходному focus/selection.

### 11.3. Search, registry и collector

- единый search command area;
- sources/coverage/verification показываются как operational telemetry;
- results table сохраняет stable tender ID и selection при refresh/filter;
- running/cancelled/partial/offline/closed states единообразны;
- scheduler и notifications используют один operation feedback contract;
- no network вызов из presentation primitives.

### 11.4. Tender analysis и decision dialogs

Охватываются documents, requirements, full analysis, verification, participation score и related
dialogs.

- вывод строится от critical evidence к recommendation и supporting details;
- AI facts маркируются verified/unverified/stale/conflicted;
- score и recommendation только отображаются из утверждённого владельца;
- риск не скрывается положительным KPI или cyan decoration;
- каждый finding связан с источником или честной пометкой отсутствия evidence;
- actions используют exact tender ID.

### 11.5. Business Workflow

- одна область proposal/estimate/project с typed child intents;
- header показывает active filter и selected stable record;
- center — table/board/timeline согласно текущему owner contract;
- right inspector — status, amounts, history, actions и audit trail;
- money использует Decimal/currency/rounding owner;
- import/export/backup/recovery показывают operation lifecycle;
- archive/restore и destructive actions требуют exact target confirmation.

### 11.6. Analytics

- tender analytics: volume, sources, regions, deadlines, competition, decision outcomes;
- financial analytics: amount, margin, cost, probability и portfolio exposure;
- каждый chart имеет definition, source, interval, unit, freshness и textual equivalent;
- selection/drill-down передаёт stable tender/workflow ID;
- chart/export/table используют один набор исходных значений и ordering;
- missing/partial/stale/conflicted данные остаются видимыми.

### 11.7. AI/settings/providers

- provider status, local/offline mode и recheck доступны в реальном embedded owner;
- credentials никогда не читаются обратно и не попадают в telemetry;
- AI status не выглядит как domain approval;
- configuration forms используют спокойный panel style без dashboard noise;
- diagnostics показывают safe reason и correlation ID.

### 11.8. Backup, recovery, health и safe mode

- severity и target видны текстом и иконкой;
- recovery никогда не предлагается как декоративная quick action;
- safety backup и irreversible consequences перечислены до подтверждения;
- failed/partial/retry states унифицированы;
- private paths и raw exceptions не отображаются пользователю.

### 11.9. Notifications и background operations

- единый operation episode: idle/running/partial/success/failure/cancelled/closed;
- compact system strip для текущей работы;
- notification center для завершённых событий;
- retry/cancel доступны только если поддержаны текущим owner;
- поздние сигналы после close не должны менять UI.

## 12. Data visualization contract

1. Визуализация не создаёт или агрегирует business values внутри QWidget.
2. Chart получает typed series с stable identity, unit, interval и provenance.
3. Одинаковые входные данные дают одинаковый ordering, labels и export.
4. Color scale документирована и доступна при нарушении цветового восприятия.
5. Legend обязательна для multi-series; series различаются также stroke/marker/label.
6. Tooltip не является единственным способом получить значение.
7. Keyboard selection и textual data table обязательны.
8. Zero/negative/missing/partial/stale values различаются.
9. Gauge применяется только для bounded metric с утверждёнными thresholds.
10. 3D, perspective и decorative particles не используются для количественных данных.
11. Map применяется только при наличии meaningful spatial dimension.
12. Export содержит те же данные, units, ordering и filters, что отображённый chart.

## 13. Состояния данных и безопасность

Обязательные presentation states:

- `idle`;
- `loading`;
- `empty`;
- `ready`;
- `partial`;
- `stale`;
- `conflicted`;
- `success`;
- `error`;
- `disabled/unavailable`;
- `cancelled`;
- `closed`.

Каждое состояние содержит stable semantic ID, title, safe explanation, tone/icon и только
разрешённое recovery action. Нельзя показывать credentials, raw exception, unrestricted user
input, private path или URL query.

## 14. Accessibility и keyboard

- полный Tab/Shift+Tab order;
- Enter/Space для activation, Escape для cancel/close;
- видимый focus в dark/light/high-contrast;
- accessible name и description для icon-only и data visualization controls;
- label/buddy для forms;
- status не только цветом;
- textual equivalent для charts/gauges/map summaries;
- screen reader объявляет operation state без бесконечного повторения;
- dialog возвращает focus к origin;
- нет keyboard traps;
- touch не является обязательным, но hit areas не должны быть меньше component contract;
- `NOT_EXECUTED` manual case не считается pass.

Полный application-wide acceptance выполняется в RM-152, но каждый предыдущий компонент должен
сразу иметь доступную семантику.

## 15. Performance требования

- технические рамки не строятся сотнями QWidget, если их можно безопасно отрисовать одним owner;
- glow/blur/animation имеют feature flag или reduced mode;
- chart rendering не блокирует UI thread на больших series;
- table contract измеряется на 0/100/1k/10k rows;
- repeated theme switch не увеличивает timers/effects/widgets;
- page switch не запускает повторно business operation;
- resize и DPI change не создают unbounded render loop;
- профилируются startup, first paint, page switch, refresh, table filter, chart update и shutdown;
- бюджеты p50/p95 фиксируются в RM-153 только после measurement.

## 16. Темы и режимы отображения

### Dark

Основная тема reference: deep black/navy surfaces, cyan focus/selection, high-contrast text,
bounded glow, dark chart grid.

### Light

Сохраняет ту же структуру и semantic roles. Glow заменяется border/background emphasis. Charts
используют контрастные series и не выглядят как инвертированный screenshot.

### High contrast / reduced effects

- повышенные border/text contrasts;
- отключён decorative glow/animation;
- сохранены focus, selection, critical status и chart distinction;
- system setting и ручной fallback не меняют business state.

Существующий QSettings key `ui/theme` и values `dark`/`light` сохраняются.

## 17. Roadmap реализации

### RM-143 — дизайн-система

- адаптация semantic tokens к cyan command-center language;
- component states, icon registry, technical panels и data primitives;
- dark/light component gallery;
- migration/exception matrix для local QSS;
- запрет raw literals и unowned styles.

Не входит: production shell, charts, массовая миграция экранов.

### RM-144 — production shell

- command header, compact navigation rail, primary canvas, context rail, system strip;
- один composition/lifecycle owner;
- сохранение RM-142 routes/history/focus;
- staged extraction legacy tender page без второго shell.

### RM-145 — Dashboard

- jobs-to-be-done и KPI definitions;
- command-center layout;
- 0/partial/stale/error/success fixtures;
- exact drill-down в tender/workflow routes.

### RM-146 — interactive chart layer

- reusable chart/gauge/timeline primitives;
- keyboard, textual equivalent, tooltip, selection, resize и export;
- deterministic render fixtures;
- audited dependency decision.

### RM-147 — tender analytics

- time/source/region/status series;
- provenance/confidence/freshness;
- stable tender drill-down;
- visible partial/conflicted sources.

### RM-148 — financial analytics

- Decimal/currency/unit/rounding contract;
- portfolio exposure и margin views;
- identical table/chart/export values.

### RM-149 — tender card/detail hierarchy

- reusable identity/status/provenance/decision/action structure;
- consistent feed/registry/results/detail behavior;
- critical stop-factor priority and exact action identity.

### RM-150 — modern tables

- common model/view/delegate/state contract;
- sorting/filtering/stable selection/keyboard/export;
- measured 0/100/1k/10k behavior;
- migrate/keep rationale for legacy tables.

### RM-151 — notifications and operations

- one operation episode contract;
- safe summaries, retry/cancel и diagnostic correlation;
- notification routing and closed-state safety.

### RM-152 — DPI and accessibility

- full focus traversal;
- screen reader/high contrast;
- Windows DPI/multi-monitor matrix;
- no clipping/overlap/keyboard traps.

### RM-153 — UI performance

- profiles and p50/p95 budgets;
- render/update/shutdown resource ownership;
- no unbounded QObject/thread/timer/memory growth.

### RM-154 — visual QA

- deterministic fonts/backend/DPI;
- representative shell, Dashboard, tender, workflow и dialogs;
- dark/light and state goldens;
- tolerance/masking/privacy/retention policy.

### RM-155 — final redesign acceptance

- consumer/history/runtime audit;
- removal of approved legacy compatibility only;
- J01–J16 end-to-end acceptance;
- one production composition and complete rollback record.

## 18. Обязательные артефакты каждого RM

Каждый пакет содержит:

1. audit текущего owner/consumer/data/lifecycle состояния;
2. requirements/contract;
3. implementation plan;
4. expected-red tests;
5. implementation с минимальным scope;
6. focused и neighboring regression results;
7. full Quality Gate results;
8. accessibility/security/privacy notes;
9. migration/compatibility decisions;
10. rollback plan;
11. acceptance report и exact SHAs;
12. canonical status update только после DoD.

## 19. Критерии визуальной приёмки всего проекта

1. Все production pages/dialogs используют одну semantic token system.
2. Визуальный язык узнаваемо соответствует Figma node `41:35` без копирования sample data.
3. Dark theme передаёт deep navy/cyan command-center character.
4. Light/high-contrast modes сохраняют структуру, смысл и доступность.
5. Shell, Dashboard, tenders, workflow, analytics, tables и dialogs выглядят частью одного продукта.
6. Critical states визуально доминируют над positive/decorative signals.
7. Нет emoji/glyph-only actions без semantic icon, tooltip и accessible name.
8. Нет unregistered literal colors, raw font sizes или unowned local QSS.
9. Layout не ломается на mandatory resolution/DPI matrix.
10. Charts имеют provenance, units, freshness, keyboard и textual equivalent.
11. Tables сохраняют stable selection и deterministic ordering.
12. Forms остаются читаемыми и не перегружены HUD-decoration.
13. Empty/loading/partial/stale/conflicted/error/disabled состояния различимы.
14. Не отображаются secrets, raw exceptions или private paths.
15. Theme switch не меняет route/data/filter/selection и не создаёт resource growth.

## 20. Функциональные критерии приёмки

- все J01–J16 остаются достижимыми;
- Dashboard quick actions и tender-ID deep links сохраняют identity;
- workflow filters и selected stable ID переживают navigation/refresh;
- search admission/cancel/closed lifecycle RM-140 не нарушен;
- settings/AI/notifications/scheduler сходятся в существующих owners;
- import/export/history/archive/restore contracts сохранены;
- score/recommendation/critical stop-factor остаются service-owned;
- DB/schema/data compatibility подтверждена;
- один shell/router/stack/service owner там, где contract требует один;
- offline tests не читают credentials и не выполняют network.

## 21. Проверки качества

Команды выводятся из `pyproject.toml` и `.github/workflows/quality-gate.yml`:

```powershell
python scripts/check_repository_secrets.py
python -m ruff check .
python -m ruff format . --check
python -m mypy
python -m pytest -q
python -m pip_audit --skip-editable
```

Обязательные дополнительные контуры:

- token/contrast/component state tests;
- route/shell composition regression;
- theme propagation and resource lifecycle;
- chart deterministic/textual/export parity;
- tender/workflow stable identity;
- table 0/100/1k/10k behavior;
- background close/late-signal safety;
- manual DPI/accessibility matrix;
- deterministic visual regression matrix;
- build/frozen resource smoke.

Точные команды, duration, passed/failed/skipped/warnings и environment записываются в acceptance
каждого RM.

## 22. Stop conditions

Работа останавливается и возвращается на аудит, если:

- Figma требует второй router, shell, repository, service или controller;
- sample metric используется как реальное product value;
- карта/график создаются без данных, definition или owner;
- UI начинает вычислять score, recommendation, money или stop-factor priority;
- critical state скрывается декоративной визуализацией;
- теряется stable tender/workflow identity, selection, filter или focus origin;
- требуется DB/schema migration без отдельного решения;
- новая dependency не прошла audit;
- asset требует runtime network/Figma access;
- raw exception, secret, private path или uncontrolled HTML попадает в UI;
- accessibility/DPI case объявлен успешным без выполнения;
- performance оптимизируется без profile;
- visual golden использует production/user data;
- следующий RM начинается до закрытия текущего по DoD.

## 23. Rollback

Каждый RM должен откатываться собственным feature merge/revert без отката данных, если пакет не
содержал отдельно утверждённую migration. Theme settings сохраняют совместимые значения. Missing
assets используют deterministic fallback. Route IDs и legacy aliases остаются совместимыми до
RM-155 consumer audit.

Полный редизайн считается завершённым только после RM-155, успешного exact merge-SHA Windows
Quality Gate и обновления канонических документов.
