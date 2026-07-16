# RM-129 — implementation plan универсального бизнес-профиля

Дата: 16 июля 2026 года.
Baseline: `a4bd2271bf062db1c5a3771adb27db809a7ac748`.
Ветка: `feat/rm-129-universal-business-profiles`.

План основан на `docs/RM-129_AUDIT.md`, `docs/RM-126_REQUIREMENTS.md` и canonical Definition of Done.
Работа RM-130–RM-200 не входит в пакет.

## 1. Docs-only gate

1. Зафиксировать audit и этот план отдельным commit.
2. Убедиться, что commit не содержит production/tests changes.
3. Не начинать реализацию до clean status этого gate.

## 2. Expected-red characterization

Добавить до production implementation:

- `tests/test_rm129_business_profile_schema.py`:
  - `MISSING`, v1 `MIGRATED_V1`, v2 `CURRENT`, corrupt и future statuses;
  - exact fact/Decimal/aware timestamp migration и no rewrite on load;
  - content-bound confirmation, every fact edit invalidation и metadata-only stability;
  - invalid known value, float money, naive datetime fail closed;
  - atomic replace failure/original preservation/temp cleanup/old-reader shape.
- `tests/test_rm129_business_profile_projection.py`:
  - immutable projection and raw-policy separation/delegation;
  - v1/v2 golden score components, explanations and recommendation equivalence;
  - empty/unconfirmed manual-review cap and no built-in capabilities;
  - one projection for stop licenses/SRO/experience/security with `Decimal`/currency;
  - critical stop and RM-107 decision invariants.
- `tests/test_rm129_business_profile_composition.py`:
  - automatic Collector and manual recalculation build one shared projection;
  - same repository path, no startup network, no second owner;
  - one QAction/dialog and typed load status presentation.

Expected red должен падать только на отсутствующих RM-129 symbols/contracts. Сохранить exact command и
failure summary отдельным test commit до production changes.

## 3. Domain schema and confirmation

Изменить `app/tenders/collector/company_capability.py` минимально совместимым образом:

1. Добавить schema v2 constants, explicit normalized `base_currency`, confirmation version,
   fingerprint и source.
2. Реализовать pure canonical facts payload/fingerprint и `confirm()`.
3. Сохранить frozen model, public `to_dict()`/`from_dict()` и imports.
4. Добавить `CompanyCapabilityLoadStatus` и frozen `CompanyCapabilityLoadResult`.
5. Реализовать strict persisted decoder и pure v1→v2 migrator.
6. `load_result()` различает missing/current/migrated/corrupt/future; `load()` остаётся wrapper.
7. Load никогда не пишет; save принимает только exact confirmed profile и пишет schema v2.
8. Сохранить temp+replace atomicity, cleanup и original on failure.

## 4. Pure business projection

Добавить `app/tenders/business_profile.py` как непersisted pure module:

- frozen `BusinessCapabilityProjection` содержит только normalized snapshot существующих facts и
  derived confirmation/configuration/missing-data values;
- factory принимает только `CompanyCapabilityProfile` и не делает I/O;
- current eight-section Corteris participation completeness policy находится здесь, а raw
  compatibility properties делегируют projection;
- никакого repository, UI, SQLite, network, classifier или score algorithm в module нет.
- current partial-profile `is_configured` predicate переносится без ужесточения; при этом projection
  fail-closed скрывает все capability facts от decision consumers, если content confirmation invalid.

Экспортировать value object через существующий collector public surface только при необходимости;
отдельный persisted `BusinessProfile` не создавать.

## 5. One projection for scoring and hard gates

1. В `participation_score.py` добавить `CorterisCompanyProfile.from_business_profile()`.
2. Сохранить `from_capability()` как thin compatibility wrapper.
3. Не менять component keys/maxima/weights/explanations/thresholds/score payload.
4. В `stop_factor.py` приводить raw compatibility input к той же
   `BusinessCapabilityProjection`; не менять kinds/status/evidence/aggregation.
   License/SRO/experience/security facts учитываются только из content-confirmed projection.
5. В `participation_score_service.py` один раз строить projection после repository load и передавать
   её ranker и stop engine.
6. В `async_provider_factory.py` сделать тот же single-projection composition.
7. `search_runtime.py` сохраняет один repository owner/path; менять только если tests докажут
   необходимый injection seam.
8. Matching catalog/classifier и `ParticipationDecisionService` production code не менять.

## 6. Existing UI adaptation

В `app/ui/company_capability_dialog.py`:

- читать `load_result()` и показывать bounded status для migrated/corrupt/future;
- собирать draft facts и вызывать domain `confirm()` вместо ручного fingerprint/metadata;
- сбрасывать checkbox после edit decision-relevant facts, требуя нового explicit confirmation;
- не вычислять completeness, score, stop или fingerprint в UI;
- не выполнять auto-save при load/migration и не менять existing repository path;
- сохранить stable interactions, signal, один QAction и один dialog owner.

Controller изменять только при доказанном тестом call-site requirement; текущий refresh уже вызывает
`load_profile()` существующего dialog.

## 7. Verification order

Окружение:

```powershell
$env:PYTHONUTF8 = "1"
$env:QT_QPA_PLATFORM = "offscreen"
$python = "C:\\CorterisTenderAI_1_5_1\\.venv\\Scripts\\python.exe"
```

1. Single expected-red test, затем весь RM-129 trio.
2. Existing profile/dialog tests.
3. Neighbor score/service/stop/collector/decision/runtime/controller/bootstrap contour.
4. Focused RM-129 command из ТЗ с repository-local `--basetemp`.
5. Full workflow-equivalent gate:
   - repository secret scan;
   - Ruff check and format check;
   - configured mypy contour;
   - offline/migration/import/composition/build smokes;
   - full pytest;
   - `pip_audit --skip-editable`;
   - `git diff --check` и clean tracked status.

Каждый result/timing записать в audit acceptance section и roadmap feature evidence без объявления
RM-129 `DONE` до merge и exact-SHA Windows gate.

## 8. Commit and release sequence

1. `docs(rm-129): audit business profile contracts`
2. `test(rm-129): define business profile schema and confirmation`
3. `feat(rm-129): add universal business profile projection`
4. `feat(rm-129): migrate company capability profile to schema v2`
5. `feat(rm-129): use one profile projection for score and stop factors`
6. `feat(rm-129): update confirmed company capability editor`
7. `test(rm-129): cover migration rollback composition and decision guards`
8. `docs(rm-129): record business profile acceptance evidence`

Неразделимые implementation commits можно объединить, но docs-only и expected-red evidence остаются
отдельными. Затем feature PR → merge → exact merge-SHA Windows Quality Gate 3.12/3.13 → отдельный
docs-only closeout, который переводит RM-129 в `DONE` и только тогда активирует RM-130.

## 9. Rollback boundary

- Application rollback: scoped revert RM-129 feature commits.
- Data rollback: v2 сохраняет все v1-known keys в `profile`; prior reader игнорирует additions.
- Load не переписывает v1/corrupt/future payload.
- Atomic replace failure сохраняет previous valid file; temp удаляется.
- DB rollback отсутствует, потому что DB/schema/migrations не меняются.
- Saved search, matching, provider, AI и final decision data не затрагиваются.

## 10. Completion gate

Feature готова к PR только когда:

- schema/migration/confirmation/projection/UI/composition acceptance tests зелёные;
- equivalent v1/v2 score, stop и decision semantics exact-сопоставлены;
- единственный repository/file/dialog owner доказан tests и diff audit;
- focused/neighbor/full gate зелёный;
- audit содержит точные результаты и remaining limits строго RM-129;
- tracked worktree clean после commit.

Статус `DONE` допустим только после feature merge, successful exact-SHA Windows gate на Python
3.12/3.13 и отдельного merged docs-only closeout.
