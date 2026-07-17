# RM-134 — implementation plan выбора протокола

Дата: 17 июля 2026 года  
Audit baseline: `38be7babdd0532ef88a1fbeff0acaed75737ea24`

План зафиксирован после `docs/RM-134_PROTOCOL_SELECTION_AUDIT.md` и до изменения
application-кода.

## 1. Цель

Дать пользователю возможность явно выбрать для созданной вручную площадки одно из
семейств API/RSS/FTP/FTPS, сохранить только проверенную declarative metadata и увидеть
следующий честный lifecycle: «протокол выбран — требуется создание адаптера».

Выбор не делает provider runnable, не создаёт adapter, не проверяет соединение и не
добавляет credentials.

## 2. Domain model

Добавить pure module `manual_provider_protocol.py`:

- closed enums family, payload format, authentication kind и TLS policy;
- immutable `ManualProviderProtocolPolicy`;
- immutable validated draft/selection;
- code-defined policy registry для API/RSS/FTP/FTPS;
- safe endpoint canonicalization и readiness gaps;
- safe public payload без endpoint и secret-like metadata.

Политики:

- API: только HTTPS, payload JSON/XML, auth none/API key;
- RSS: только HTTPS, payload RSS/Atom, auth none;
- FTP: только FTP, auth none/username-password, явное предупреждение о plaintext;
- FTPS: только FTPS без downgrade, auth none/username-password.

Никаких произвольных protocol names, headers, parser code, scripts или transport options.

## 3. Registration lifecycle

Расширить `ManualProviderLifecycle` состоянием `ADAPTER_REQUIRED` и добавить nullable
`protocol_selection` в `ManualProviderRegistration`.

Инварианты:

- selection отсутствует -> `PROTOCOL_REQUIRED`;
- selection присутствует -> `ADAPTER_REQUIRED`;
- metadata edit сохраняет существующий selection;
- clear selection возвращает `PROTOCOL_REQUIRED`;
- public payload показывает только family/auth/payload/lifecycle, но не endpoint;
- registration всегда остаётся disabled/registration-only/non-runnable.

## 4. Persistence и concurrency

Поднять `ProviderEnablementRepository` schema `3 -> 4`:

- decode/encode nested protocol selection;
- v3 читается как `MIGRATED_V3` с отсутствующим selection;
- v2 и split-v1 продолжают поддерживаться;
- future/corrupt schema fail closed;
- первая mutation предыдущей v3 создаёт `.v3-*` backup;
- write остаётся atomic;
- unknown fields и invalid selection отклоняются.

Добавить compare-and-replace mutation под существующим repository lock. Manager command
передаёт expected registration `updated_at`; stale edit возвращает безопасный conflict и
не перезаписывает более новое состояние.

## 5. Manager и catalog projection

Расширить `CollectorProviderManager` typed commands:

- получить policies/текущий selection;
- save/change selection;
- clear selection;
- получить readiness gaps.

Ошибки должны быть типизированы: invalid input, not found, unsupported target, stale edit,
persistence failure. Message не содержит endpoint или exception details.

`resolved_provider_catalog()` проецирует:

- selected family и `protocol_configured=True` после save;
- lifecycle `adapter_required`;
- `registration_only=True`, `runnable=False`, `factory_available=False`,
  `credential_available=False`, `health_check_available=False` всегда.

## 6. UI

В `TenderProviderManagerDialog` добавить кнопку «Настроить протокол», активную только для
manual registration. Отдельный `ManualProviderProtocolDialog`:

- controlled family combo API/RSS/FTP/FTPS;
- только family-allowed payload/auth options;
- endpoint field без secret/username/password/header inputs;
- видимый TLS/plaintext warning;
- readiness text «адаптер ещё не создан»;
- save/change и отдельное clear с подтверждением.

Controller использует только manager commands, передаёт expected `updated_at`, обновляет
states после успеха и показывает безопасную ошибку при stale/invalid operation.

## 7. Expected-red tests до implementation

Добавить acceptance tests, которые сначала должны падать из-за отсутствия RM-134 API:

- policy matrix и closed enums;
- URL/host/port/path/security rejection matrix;
- safe repr/public payload;
- schema v4 roundtrip и v3 migration/backup;
- corrupt/future/unknown-field fail closed;
- save/change/clear lifecycle;
- stale edit rejection;
- catalog/manager projection;
- UI controlled inputs and wiring;
- unchanged factory/run/search/scheduler/profile/health/credentials guards;
- legacy store/tester isolation and no network on dialog/save.

Expected-red команда и причина будут записаны в acceptance evidence.

## 8. Validation

После implementation выполнить:

1. focused RM-134 tests;
2. neighboring RM-131/RM-132/RM-133 provider/settings/UI/runtime tests;
3. full `pytest`;
4. repository secret scan;
5. Ruff check и format check;
6. mypy workflow contour;
7. offline smoke, DB/schema, composition, build/import gates;
8. pip-audit по workflow policy;
9. `git diff --check` и clean/status review.

Точные команды и результаты записываются в
`docs/RM-134_PROTOCOL_SELECTION_ACCEPTANCE.md`, а итоговые
feature/exact merge-SHA evidence — в canonical roadmap documents при closeout.

## 9. Out of scope

- executable adapters, parsers, normalization и connection tests;
- DNS/network access при выборе или сохранении;
- произвольный user code/configuration;
- secrets/credentials или изменение credential descriptors;
- legacy migration/synchronization;
- scheduler/background execution manual providers;
- изменение deterministic decision logic;
- начало RM-135+.

## 10. Rollback

Rollback application-кода возвращает чтение schema v3. До merge проверяется наличие
однократного v3 backup при первой mutation, поэтому локальный v3 payload восстанавливаем.
Feature не включает network/external side effects, secrets или database migration.
