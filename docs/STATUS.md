# Текущее состояние CorterisTenderAI

Обновлено: 17 июля 2026 года.

## Активный этап

**RM-131 — настройки площадок**

Статус: `IN PROGRESS`

RM-130 завершён после audit-first реализации, feature merge и успешного exact merge-SHA Windows
Quality Gate. RM-131 назначен единственным активным этапом; RM-132–RM-200 остаются `PLANNED` и не
выполняются параллельно.

## Завершённый этап

**RM-130 — сохранённые поисковые профили**

Статус: `DONE`

Подтверждение:

- audit/plan зафиксированы docs-only commit `09d60cc`, expected-red contract — `f206c0d`;
- один existing `TenderSearchProfileRepository` и один `<data_directory>/search_profiles.json`
  поддерживают schema v2 и typed missing/current/migrated-v1/corrupt/future состояния;
- valid v1 мигрирует при первой explicit mutation с byte-for-byte backup и atomic replace;
  corrupt/future original не перезаписывается, invalid catalog fail-closed блокирует mutation;
- built-in identity определяется canonical ID membership, а custom payload, disabled state и
  deterministic ordering сохраняются;
- `SAVED_PROFILE` и `KEYWORD_OVERRIDE` формализуют существующую RM-128 семантику; transient text не
  изменяет profile/repository bytes;
- profile money проходит exact Decimal-safe editor boundary без float; currency explicit, nonempty
  timestamps aware UTC, legacy naive timestamps становятся явно unknown без guessed timezone;
- один profiles dialog/editor, один unified panel и один Collector worker seam сохранены; legacy sync
  runner и async Collector path не заменены;
- локально: focused `82 passed in 9.68s`, neighbor `64 passed in 6.33s`, full pytest
  `1656 passed in 60.73s`; все workflow-equivalent gates успешны;
- feature PR #66 слит в `main` коммитом `3a4d530`
  (`3a4d53067b7b0f8eaf0b5969c139284c9d5ed987`);
- PR Quality Gate run `29533900495` успешен: Python 3.12 — `1656 passed in 101.17s`,
  Python 3.13 — `1656 passed in 150.85s`;
- exact merge-SHA run `29534568925` успешен: Python 3.12 — `1656 passed in 141.74s`,
  Python 3.13 — `1656 passed in 66.21s`;
- на обеих версиях прошли secret scan, Ruff check/format (`554 files`), mypy (20 файлов),
  offline/migration/import/composition/build smoke и dependency audit;
- DB/schema/migrations, dependencies, provider settings/credentials, normalization/ranking,
  scheduler, score/recommendation/critical stop-factor и AI contracts не изменены.

## Ранее завершённый этап

**RM-129 — универсальные бизнес-профили**

Статус: `DONE`

Подтверждение:

- feature PR #64 слит в `main` коммитом `f9b43c3`;
- post-merge Quality Gate run `29522737754` успешен на Python 3.12/3.13;
- confirmed business projection, deterministic score и critical stop-factor priority сохранены.

## Текущее действие

Начать RM-131 только с обязательного аудита existing provider settings/catalog/credentials ownership
и call sites по `docs/RM-126_REQUIREMENTS.md`. Не создавать второй provider catalog/settings owner и
не смешивать RM-131 с credentials UI RM-132 или adapter builder RM-133–RM-135.
