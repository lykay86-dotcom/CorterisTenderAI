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
