# RM-156 — нормативный контракт модели контрагента

Contract version: `rm156-contractor-model-v1`.

## 1. Identity

Контрагент имеет одну каноническую identity `inn`.

- input обязан быть строкой;
- допускается только 10 или 12 ASCII-цифр после удаления внешних пробелов;
- внутренние пробелы, дефисы, знаки, Unicode digits, bool/int/float запрещены;
- 10- и 12-значные контрольные разряды проверяются по алгоритму ФНС;
- 10 цифр означают ИНН организации;
- 12 цифр означают ИНН физического лица; статус ИП без отдельного evidence не утверждается;
- невалидный или пустой ИНН не сохраняется и не превращается в placeholder.

Канонический ИНН уникален на весь lifecycle записи. Soft-deleted запись восстанавливается, а не
заменяется новой записью с тем же ИНН.

## 2. Domain и persistence

Единственный новый domain owner — `app.contractors`.

Минимальная production surface:

- immutable validated contractor-INN value object;
- SQLAlchemy `Contractor` в таблице `contractors`;
- `ContractorRepository`;
- `UnitOfWork.contractors`;
- canonical public imports из `app.contractors` и `app.database.models/repositories`.

Таблица хранит только:

- UUID `id`;
- canonical `inn`;
- `created_at`, `updated_at`, `deleted_at` в aware UTC;
- `is_deleted`;
- positive integer `row_version`.

Имя, КПП, ОГРН, адрес, статус, финансы, риски, score и source payload в RM-156 не хранятся. Их
отсутствие не заменяется встроенными значениями.

## 3. Repository semantics

- lookup валидирует и канонизирует ИНН тем же domain owner;
- обычный lookup не возвращает soft-deleted запись;
- explicit include-deleted lookup доступен для restore;
- duplicate create завершается typed conflict, не возвращает случайную запись;
- add/restore/update выполняются внутри существующего `UnitOfWork`;
- audit log не содержит внешних payloads или секретов;
- list остаётся bounded existing repository limit;
- UI не открывает собственную session и не содержит identity rules.

## 4. Time contract

Все audit timestamps:

- создаются как aware UTC;
- после SQLite commit/new-session round-trip остаются aware UTC;
- naive assignment/input отвергается либо нормализуется только для legacy значений, доказуемо
  созданных прежним UTC writer;
- JSON/read-model serialization содержит явный `+00:00`;
- soft delete/restore/update сохраняют aware UTC и монотонно увеличивают `row_version`.

Исправление выполняется в существующем общем audit type owner, без второго timestamp mixin.

## 5. Migration contract

Application schema повышается ровно `3 → 4`.

- существующая непустая SQLite DB получает verified backup до изменения;
- создаётся `contractors` с unique/index contract;
- существующие `companies`, settings, tenders, documents, analyses и audit rows сохраняются;
- fresh DB сразу создаётся как schema 4;
- current schema 4 idempotent;
- future schema `>4` блокируется без downgrade/write;
- отсутствующая/нечисловая/corrupt version блокируется с sanitized `MigrationError`;
- failure восстанавливает backup и не оставляет schema version 4 без verified table/index;
- integrity, foreign keys и readback проверяются;
- rollback — restore verified pre-migration backup; автоматический destructive downgrade запрещён.

Collector schema 16 и tender registry schema не меняются.

## 6. Source and decision isolation

- `TenderCustomer` может стать input будущего candidate/provenance flow, но RM-156 не создаёт
  контрагента автоматически;
- нет network, provider, keyring, credential, AI или scraping path;
- нет official-data claim;
- RM-107 score, recommendation и абсолютный приоритет critical stop-factor не меняются;
- RM-165 остаётся единственным будущим этапом contractor reliability scoring.

## 7. Acceptance

До feature implementation должны существовать strict expected-red tests для:

- 10/12 INN checksum и invalid-type/character/length matrix;
- canonical uniqueness и duplicate conflict;
- repository lookup, soft delete, restore и row version;
- aware UTC SQLite round-trip;
- fresh/3→4/current/future/corrupt migration;
- backup/restore и preservation existing rows;
- exact schema/index/UoW/public-import contract;
- no Collector/search/UI/AI coupling;
- unchanged application composition and RM-107 decision guards.

Feature принимается только после focused/full/Ruff/format/mypy/secret/migration/build/frozen/
Windows Python 3.12/3.13 gates, feature merge и successful exact merge-SHA run.
