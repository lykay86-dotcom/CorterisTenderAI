# Текущее состояние CorterisTenderAI

Обновлено: 17 июля 2026 года.

## Активный этап

**RM-132 — безопасный ввод API и credentials**

Статус: `IN PROGRESS`

RM-131 завершён после audit-first реализации, feature merge и успешного exact merge-SHA Windows
Quality Gate. RM-132 назначен единственным активным этапом; RM-133–RM-200 остаются `PLANNED` и не
выполняются параллельно.

## Завершённый этап

**RM-131 — настройки площадок**

Статус: `DONE`

Подтверждение:

- audit/plan зафиксированы docs-only commit `243ab56`, expected-red contract — `4c13913`;
- existing `ProviderEnablementRepository` и один
  `<data_directory>/collector_provider_settings.json` schema v2 стали canonical non-secret settings
  boundary с typed missing/current/migrated-split-v1/corrupt/future состояниями;
- split-v1 migration сохраняет byte-for-byte backups, использует atomic replace, general enablement
  precedence и не удаляет legacy commercial source; corrupt/future fail closed;
- pure canonical provider identities и только явные aliases используются manager, profiles,
  scheduler, session и factory; generic `commercial` отклоняется;
- persisted non-secret settings, runtime-only environment origins и read-only overrides проходят через
  один immutable snapshot; credential/keyring values не попадают в JSON или display snapshot;
- provider manager, unified panel, Collector dialog, scheduler и фактический run используют один
  settings owner; legacy manual platform UI явно отделён как compatibility tester;
- локально: focused `30 passed in 4.37s`, neighbor `76 passed in 12.01s`, full pytest
  `1686 passed in 63.19s`; все workflow-equivalent gates успешны;
- feature PR #68 слит в `main` коммитом `bbfd8e3`
  (`bbfd8e3b858a29f07d7b55fde5fdb5a80a1d9cf2`);
- PR Quality Gate run `29538903447` успешен: Python 3.12 — `1686 passed in 90.24s`,
  Python 3.13 — `1686 passed in 101.46s`;
- exact merge-SHA run `29562019173` успешен: Python 3.12 — `1686 passed in 105.77s`,
  Python 3.13 — `1686 passed in 69.02s`;
- на обеих версиях прошли secret scan, Ruff check/format (`562 files`), mypy (20 файлов),
  offline/migration/import/composition/build smoke и dependency audit;
- DB/schema/migrations, health/C19 state, credentials, normalization/ranking,
  score/recommendation/critical stop-factor и AI contracts не изменены.

## Ранее завершённый этап

**RM-130 — сохранённые поисковые профили**

Статус: `DONE`

Подтверждение:

- feature PR #66 слит в `main` коммитом `3a4d530`;
- exact merge-SHA Quality Gate run `29534568925` успешен на Python 3.12/3.13;
- schema-v2 saved profiles и deterministic decision/critical stop-factor contracts сохранены.

## Текущее действие

Начать RM-132 только с обязательного аудита existing credential boundaries, environment/keyring
resolution и replacement-only UI. Не сохранять и не отображать secrets, не дублировать vault/resolver
и не смешивать RM-132 с manual provider registration или adapter builder RM-133–RM-135.
