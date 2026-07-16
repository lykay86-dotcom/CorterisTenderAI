# RM-129 — аудит универсального бизнес-профиля

Дата аудита: 16 июля 2026 года.
Baseline: `a4bd2271bf062db1c5a3771adb27db809a7ac748`.
Ветка: `feat/rm-129-universal-business-profiles`.

## Решение entry gate

- `docs/STATUS.md` и `docs/ROADMAP.md` назначают RM-129 единственным `IN PROGRESS`; RM-130–RM-200
  остаются `PLANNED`.
- RM-128 закрыт feature merge, exact-SHA Windows gate и отдельным docs-only closeout.
- Открытых GitHub PR на момент аудита нет; локальная/remote ветка RM-129 до начала работы отсутствовала.
- Работа начата в отдельном worktree от точного `origin/main`; пользовательские untracked
  `.agents/` и `skills-lock.json` основного checkout не затронуты.
- Stop conditions ТЗ не обнаружены: новый repository, DB migration, network/provider call,
  scoring formula, matching change или RM-130+ scope не требуются.

## Канонические владельцы и фактические пути

| Область | Канонический владелец | Фактическое состояние |
|---|---|---|
| Persisted capability facts | `CompanyCapabilityProfileRepository` | Один файл `company_capability_profile.json`, один repository class, schema marker v1 |
| Raw facts | `CompanyCapabilityProfile` | Frozen value object с `Decimal` и aware timestamp validation |
| Редактирование | `CompanyCapabilityDialog` | Один QAction/кэшируемый dialog в `TenderSearchUiController` |
| Scoring projection | `CorterisCompanyProfile.from_capability()` | Самостоятельно выводит regions, limits, licenses, equipment и completeness |
| Ranker | `CorterisParticipationRanker` | Утверждённые 9 component keys, maxima, explanations и recommendation bands |
| Hard gates | `StopFactorEngine` | Самостоятельно читает raw profile и его completeness; critical status агрегируется первым |
| Manual score | `CorterisParticipationScoreService` | Загружает capability перед пересчётом и отдельно строит ranker/stop engine |
| Automatic Collector | `create_default_collector_service()` | Один load, но две независимые projections из одного raw object |
| Matching | `MatchingCatalogRepository` + `CorterisTenderClassifier` | Отдельный SQLite owner; RM-129 не меняет catalog/`canonical_term` |
| Final decision | `ParticipationDecisionService` + `ParticipationDecisionPolicy` | `BLOCKED_BY_REQUIREMENT` возвращает `DO_NOT_PARTICIPATE` до score/AI |

Поиск всех production/test call sites подтвердил единственный JSON path:

```text
<data_directory>/company_capability_profile.json
```

Второго capability/business-profile repository, файла или SQLite owner нет и для RM-129 не нужен.

## Текущий persisted contract v1

```json
{
  "schema_version": 1,
  "profile": {
    "company_name": "...",
    "max_project_amount": "30000000.00",
    "confirmed_at": "2026-07-12T12:00:00+00:00",
    "confirmed_by": "..."
  }
}
```

Сильные стороны текущего контура:

- money нормализуется в finite non-negative `Decimal` и сохраняется строками;
- tuple facts deduplicate case-insensitively с first-seen ordering;
- `confirmed_at`/`updated_at` требуют timezone и нормализуются в UTC;
- save использует sibling `.tmp` и `Path.replace()` под `RLock`, cleanup выполняется в `finally`;
- save запрещает пустое company name и профиль без `confirmed_at`/`confirmed_by`;
- missing facts не заменяются встроенными production defaults.

Подтверждённые gaps:

1. `load()` игнорирует `schema_version`; missing, corrupt, invalid и future payload сворачиваются в
   одинаковый пустой profile без typed diagnostics.
2. Invalid known values могут тихо нормализоваться в empty tuple; JSON numeric money превращается через
   `str`, хотя persisted contract должен допускать только decimal strings.
3. Confirmation определяется только непустыми `confirmed_at`/`confirmed_by`; изменение facts с прежней
   metadata сохраняет видимость подтверждения.
4. Explicit currency отсутствует; scoring projection неявно оставляет `RUB` default.
5. `is_configured` и восемь русских `missing_sections` находятся в raw facts model, хотя это текущая
   Corteris participation policy.
6. UI вручную создаёт confirmation timestamp/metadata и не владеет content fingerprint.
7. Открытие corrupt/future payload не может честно показать причину; original не переписывается при
   load, но оператор не получает status.
8. После добавления `COMPANY_PROFILE_INCOMPLETE` stop engine продолжает читать raw license/SRO,
   experience и security facts. Поэтому неподтверждённый draft теоретически способен снять
   requirement block; scoring projection также копирует raw facts до своих completeness guards.

## Текущая семантика scoring/stop/decision

`CorterisCompanyProfile.from_capability()` создаёт strict production projection:

- `priority_regions = self_install_regions + partner_regions`, `nationwide_regions = ()`;
- price range `0..max_project_amount`, currency фактически `RUB`;
- licenses = licenses + license work types + SRO;
- equipment terms = equipment + brands + suppliers + stock;
- no OKPD2 defaults;
- configured/missing fields берутся из raw model;
- financial confirmed только при наличии `max_project_amount` и `working_capital`;
- пустой/неполный profile ограничивает total score значением `64`.

Текущий `is_configured` означает подтверждённое имя и наличие хотя бы одного из перечисленных
capability-направлений, а не отсутствие всех восьми `missing_sections`. RM-129 сохраняет этот predicate
буквально, чтобы не вносить новую scoring/stop policy; отдельный safe guard запрещает использовать
какие-либо capability facts неподтверждённого profile.

Неизменяемый component contract ranker:

| Key | Maximum |
|---|---:|
| `direction` | 30 |
| `region` | 10 |
| `price` | 10 |
| `equipment` | 15 |
| `experience` | 10 |
| `licenses` | 10 |
| `financial` | 10 |
| `preparation` | 5 |
| `risks` | 0 |

`StopFactorEngine` отдельно читает directions, license/SRO/experience и security limits. Status ordering
сейчас: `BLOCKED_BY_REQUIREMENT` → `DATA_INSUFFICIENT` → `CONDITIONAL` → `CLEAR`. Security calculations
используют `Decimal`. `ParticipationDecisionService` проверяет structured stop до score и AI, поэтому
critical block остаётся абсолютным.

Characterization baseline для существующих fixtures: empty production projection — score `20`,
`not_recommended`; complete confirmed fixture — score `66`, `manual_review`, component scores
`23, 10, 10, 3, 7, 7, 6, 4, -4`. Ranker bands остаются `<45`, `45–64`, `65–79`, `>=80`.

Вывод: алгоритмы не требуют переработки. Нужна одна pure immutable application projection, которую
получат и `CorterisCompanyProfile`, и `StopFactorEngine`; ranker/stop/decision rules остаются прежними.

## Принятый target contract

1. `CompanyCapabilityProfile` остаётся public raw fact model и получает explicit `base_currency` плюс
   versioned content-bound confirmation metadata.
2. Pure `BusinessCapabilityProjection` создаётся только из raw profile, не делает I/O и не
   persistится. Текущая Corteris completeness policy переносится в эту boundary; compatibility
   properties raw model делегируют ей.
3. `CorterisCompanyProfile.from_business_profile()` становится production path;
   `from_capability()` остаётся compatibility wrapper.
4. `StopFactorEngine` принимает ту же projection или compatibility raw profile и сразу приводит raw
   input к projection.
   Неподтверждённая projection не предоставляет decision consumers направления, licenses/SRO,
   experience, equipment или financial/security limits.
5. Manual и automatic composition создают projection один раз и передают её обоим потребителям.
6. Matching catalog, classifier inputs, score persistence, final decision и AI contracts не меняются.

## Schema v1 → v2 mapping

| v1 | v2 | Правило |
|---|---|---|
| все известные fact keys | те же keys внутри `profile` | exact fact-preserving in-memory migration |
| implicit RUB | `base_currency = "RUB"` | единственный разрешённый migration default |
| `confirmed_at`/`confirmed_by` | те же metadata | сохраняются после aware/non-empty validation |
| отсутствует | `confirmation_version = 1` | добавляется только валидному confirmation |
| отсутствует | `confirmation_fingerprint = sha256(canonical facts)` | детерминированно вычисляется локально |
| отсутствует | `confirmation_source = "migrated_v1"` | auditable migration origin |
| `schema_version = 1` | typed `MIGRATED_V1` result | load не переписывает файл |
| отсутствует/2/future/corrupt | `MISSING`/`CURRENT`/`UNSUPPORTED_FUTURE`/`CORRUPT` | fail-closed typed result |

Explicit user save пишет только top-level schema v2. Старые keys остаются на прежнем уровне `profile`,
поэтому v1 reader может прочитать известные факты и проигнорировать additions.

## Confirmation и validation decisions

- Fingerprint включает все decision-relevant facts и `base_currency`, но не включает timestamps,
  confirmer, evidence note, fingerprint или transient load status.
- Tuple facts canonicalize для fingerprint независимо от UI order; persisted first-seen order остаётся.
- `confirm()` принимает non-empty confirmer и aware datetime, нормализует UTC и возвращает новый frozen
  profile с version/fingerprint/source.
- `is_confirmed` true только при supported confirmation version/source и exact fingerprint match.
- Любое изменение fact автоматически делает старую metadata невалидной до нового explicit confirm.
- v1 confirmation переносится только если timestamp aware и confirmer non-empty; новые capability facts,
  кроме `RUB`, не добавляются.
- Current/v1 persisted money принимает только decimal strings; float/infinite/negative values fail closed.
- Unknown fields игнорируются, invalid known field делает весь load `CORRUPT`, без частичного confirmed
  profile и без изменения original.

## Baseline evidence

Среда: Windows, Python `3.12.7`, `PYTHONUTF8=1`, `QT_QPA_PLATFORM=offscreen`.

- Первый запуск profile/dialog contour без local basetemp: `3 passed, 2 errors in 6.40s`; обе ошибки —
  environment-only `PermissionError [WinError 5]` при обходе stale global
  `%LOCALAPPDATA%\\Temp\\pytest-of-сooocorteris`.
- Повтор exact contour с существующим gitignored repository-local `--basetemp`:
  `5 passed in 3.49s`.
- Neighbor score/stop/decision/runtime/controller/bootstrap contour: `38 passed in 7.79s`.
- Полный pytest: `1552 passed in 74.92s (0:01:14)`.
- `git diff --check`: success; tracked worktree clean.

Проблема global Temp не воспроизводит application defect; дальнейшие локальные тесты используют только
repository-local ignored basetemp и сохраняют точные результаты.

## Риски и guards

| Риск | Guard |
|---|---|
| v1 facts или Decimal precision потеряны | fixture migration + v1/v2 golden equivalence |
| stale confirmation survives edit | every-fact fingerprint invalidation tests |
| corrupt/future file уничтожен | original-byte preservation + no-write-on-load tests |
| score explanation/threshold drift | exact components/scores/explanations/recommendation golden fixture |
| score и stop получают разные facts | identity/equality composition tests одной projection |
| critical block ослаблен | existing and RM-129 decision priority tests |
| default capabilities leak | empty/unconfirmed score/stop tests |
| UI становится policy owner | domain `confirm()` spy/behavior tests and status-only UI assertions |
| matching scope случайно изменён | catalog/classifier characterization and no touched matching files |

## Audit conclusion

RM-129 реализуем инкрементально в существующем repository/file/dialog/composition. Production edits
разрешены только после отдельного docs-only commit этого аудита и implementation plan, затем после
expected-red characterization. DB/schema migration, network, dependencies и RM-130+ изменения не нужны.

## Feature acceptance evidence

Реализация проверена на feature HEAD `a99252b32d818dd6d07f9aaa818cbeb1cdbafb00`, Windows,
Python `3.12.7` из project `.venv`, `PYTHONUTF8=1`, `QT_QPA_PLATFORM=offscreen`.

Порядок и commits:

- docs-only audit gate: `ddb8427`;
- expected-red characterization: `3331131`; точный RM-129 trio завершился тремя ожидаемыми
  collection errors за `3.05s` только из-за отсутствующих typed load/projection symbols;
- schema/confirmation/projection: `b79f8a6`;
- shared composition и existing editor: `f654ac4`;
- расширенные migration/composition/decision guards: `a99252b`.

Реализованный contract:

- один `CompanyCapabilityProfileRepository`, один прежний JSON path и schema v2; v1 мигрируется
  только в памяти, corrupt/future payload не переписывается;
- `confirm()` exact-связывает все decision facts с SHA-256 fingerprint; metadata/`updated_at` и
  semantic tuple order fingerprint не меняют;
- pure frozen `BusinessCapabilityProjection` fail-closed скрывает неподтверждённые capabilities и
  является общей boundary manual score, automatic Collector и stop-factor engine;
- `CorterisCompanyProfile.from_business_profile()` сохраняет прежние keys/maxima/explanations/bands,
  а `from_capability()` остаётся compatibility wrapper;
- explicit currency передаётся scoring; security в другой валюте остаётся `DATA_INSUFFICIENT` без
  курса и без нового stop kind;
- runtime, controller и один cached dialog разделяют тот же repository instance; UI вызывает domain
  confirmation, честно показывает migrated/corrupt/future status и не сохраняет при load;
- matching catalog/`canonical_term`, saved search profiles, DB/schema/migrations, providers/network,
  AI и `ParticipationDecisionService` production code не изменены.

Точные локальные результаты:

- focused RM-129/profile/dialog: `76 passed in 5.25s`;
- neighbor score/stop/decision/runtime/controller/bootstrap: `38 passed in 6.85s`;
- adjacent summary/full-analysis: `51 passed in 3.53s`;
- full pytest: `1623 passed in 70.35s (0:01:10)`;
- repository secret scan: `Repository secret scan passed.`;
- Ruff check: `All checks passed!`;
- Ruff format: `549 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- offline credential isolation: `2 passed in 5.11s`;
- legacy migration/schema smoke: `5 passed in 3.25s`;
- public import: `DashboardController`;
- headless composition: `1 passed in 0.22s`;
- release/build contract: `6 passed in 4.22s`;
- dependency audit: `No known vulnerabilities found`; editable project skipped;
- `git diff --check`: success; tracked worktree clean before this evidence update.

Первый sandboxed `pip-audit` attempt получил environment-only Windows `WinError 10013`/cache access
failure. Повтор exact command с разрешённым external/cache access завершился успешно за `8.495s`; код,
dependencies и lock files между attempts не менялись.

Feature acceptance не закрывает RM-129: обязательны feature PR/merge, exact merge-SHA Windows Quality
Gate на Python 3.12/3.13 и отдельный docs-only closeout. RM-130 остаётся `PLANNED`.
