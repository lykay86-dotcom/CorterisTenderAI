# RM-156 — аудит модели контрагента

Дата: 23 июля 2026 года.

Статус: `AUDIT COMPLETE / IMPLEMENTATION NOT STARTED`.

Audit base: `e2eeac22497ec90b108fc02765089a92c6fdfc55`
(`Merge pull request #156 ... pre-rm156-collector-closeout`).

## 1. Решение

RM-156 должен создать модель **проверяемого контрагента**, не расширяя модель собственной
организации ООО «КОРТЕРИС» и не начиная RM-157–RM-168.

В текущем коде модели контрагента нет. Существующие сущности `Company`, `CompanyProfile` и
`CompanyCapabilityProfile` принадлежат собственной компании; `TenderCustomer` и поля
`customer_*` являются наблюдениями из закупок, а не master-record контрагента.

Разрешён узкий новый bounded context `app.contractors` с канонической идентичностью по ИНН,
переиспользующий существующие SQLAlchemy `Base`, `UUIDAuditMixin`, repository/UoW, migration,
backup и audit owners. Поиск, внешние источники, регистрационные/финансовые/судебные данные,
оценка, графики, замечания и отчёт остаются в RM-157–RM-168.

## 2. Entry gate

Collector prerequisite принят:

- closeout PR #156 head `e105b202b342da975c61fc430d713f385f180be8`;
- PR-head run `30003448590`, jobs `89193776310`/`89193776412`, оба successful;
- merge `e2eeac22497ec90b108fc02765089a92c6fdfc55`;
- exact merge-SHA run `30004268816`, jobs `89196436206`/`89196436327`, оба successful;
- dependency audit successful в обеих exact jobs.

RM-156 остаётся единственным `IN PROGRESS`; RM-157–RM-200 остаются `PLANNED`.

Локальный неизменённый baseline:

```text
tests/test_database_core.py
tests/test_database_migrations_121.py
tests/test_database_reliability_121.py
tests/test_company_capability_profile.py
tests/test_collector_normalizer.py
tests/test_tender_registry.py

31 passed in 11.19s
```

## 3. Инвентаризация владельцев

| Surface | Фактический смысл | Решение RM-156 |
|---|---|---|
| `app.database.models.company.Company` | собственная организация, банковские и коммерческие настройки | `KEEP`; не переименовывать и не использовать как контрагента |
| `CompanyRepository`, `UnitOfWork.companies` | persistence owner собственной организации | `KEEP`; переиспользовать generic repository/UoW pattern, не семантику |
| `app.company.profile.CompanyProfile` | projection пользовательских настроек для генерации документов | `KEEP` |
| `CompanyCapabilityProfile` | подтверждённые возможности ООО «КОРТЕРИС» для участия/скоринга | `KEEP`; не связывать с контрагентом |
| `TenderCustomer` | immutable provider observation: имя, ИНН, КПП, регион, адрес | `REUSE AS EVIDENCE INPUT LATER`; не master-record |
| `NormalizedTender.normalized_customer_inn` | нормализованный ключ наблюдения Collector | `KEEP`; не создавать из него контрагента автоматически |
| `tender_records.customer_name/customer_inn` | денормализованная закупочная история | `KEEP`; RM-156 не меняет Collector schema |
| `TenderVerificationService` | provenance/conflict owner закупочных полей | `KEEP`; не переносить в contractor context |
| `Base`, `UUIDAuditMixin`, `Repository`, `UnitOfWork` | общий ORM/audit/transaction owner | `REUSE AND HARDEN` |
| `MigrationManager`, `BackupManager`, `SchemaInspector` | единственный owner локальной schema migration/backup | `REUSE`; schema 3→4 |

## 4. Обнаруженные gaps

1. Нет отдельной contractor identity, таблицы, repository или UoW access path.
2. Нет единого валидатора ИНН 10/12 цифр с контрольными разрядами.
3. `companies` нельзя переиспользовать:
   - seed и `get_active()` предполагают собственную организацию;
   - таблица содержит банковские реквизиты, маржинальность и assets собственной компании;
   - смешение сделает ownership и удаление неоднозначными.
4. `TenderCustomer` не имеет lifecycle/audit/persistence и допускает пустой ИНН; автоматическое
   создание master-record из него выдало бы непроверенное наблюдение за подтверждённый факт.
5. Локально доказано, что SQLite round-trip существующего `DateTime(timezone=True)` снимает
   timezone: до flush `+00:00`, после нового чтения `tzinfo=None`. RM-156 обязан исправить общий
   audit timestamp type fail-closed и доказать aware UTC round-trip.
6. `MigrationManager` не имеет явного шага 3→4 и сейчас не должен молча принимать/downgrade
   future schema. Новый шаг обязан иметь backup, integrity/readback и future/corrupt guards.
7. Нет contractor-specific unit/integration/schema/rollback tests.

## 5. Границы этапа

RM-156 включает только:

- каноническое значение ИНН;
- contractor persistence model и repository;
- schema migration 3→4 с backup/rollback evidence;
- audit timestamps, soft delete/restore и optimistic row version;
- публичный domain import и headless tests.

RM-156 не включает:

- поиск по ИНН или сеть (`RM-157`);
- source adapters/provenance architecture (`RM-158`);
- КПП, ОГРН, адреса, руководителя и официальный статус (`RM-159`);
- финансовые, судебные, ФССП, госконтрактные и affiliate данные (`RM-160–RM-164`);
- score/recommendation (`RM-165`);
- charts, notes/manual conclusion и report (`RM-166–RM-168`);
- UI page, AI, ключи, telemetry или изменение Collector/provider readiness.

## 6. Stop conditions

Остановить implementation, если для модели требуется угадать внешний источник, смешать
собственную компанию и контрагента, автоматически доверить `TenderCustomer`, изменить
RM-107 score/recommendation/critical stop-factor, начать RM-157+ или ослабить migration/UTC
contract ради green gate.

Следующий пакет после merge/exact этого аудита — отдельный tests-first expected-red package.
