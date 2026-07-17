# RM-134 — аудит выбора протокола

Дата аудита: 17 июля 2026 года  
Audit baseline: `38be7babdd0532ef88a1fbeff0acaed75737ea24` (`origin/main`)  
Статус: audit завершён до изменения application-кода.

## 1. Entry gate

- `docs/STATUS.md` и `docs/ROADMAP.md` называют RM-134 единственным этапом
  `IN PROGRESS`; RM-133 имеет статус `DONE`, RM-135+ — `PLANNED`.
- На `origin/main` нет открытых PR.
- Последний exact merge-SHA Quality Gate для RM-133 успешен: run `29574218692` на
  `38be7babdd0532ef88a1fbeff0acaed75737ea24`.
- Работа ведётся в отдельной ветке `feat/rm-134-provider-protocol-selection` и worktree
  `.worktrees/rm-134-provider-protocol-selection` от точного audit baseline.
- Корневой checkout и пользовательские untracked-файлы не изменяются.

## 2. Baseline

На точном audit baseline получены следующие результаты:

- focused provider/settings/UI/runtime contour: `120 passed, 2 warnings in 16.47s`;
- full pytest: `1758 passed, 2 warnings in 80.64s`;
- secret scan: `Repository secret scan passed.`;
- Ruff check: `All checks passed!`;
- Ruff format: `578 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- offline smoke: `2 passed in 5.43s`;
- DB/schema gate: `5 passed in 3.54s`;
- composition gate: `1 passed in 0.27s`;
- build gate: `6 passed in 4.45s`;
- `DashboardController` import: success;
- pip-audit: editable project skipped, `No known vulnerabilities found`.

Два предупреждения pytest принадлежат существующему openpyxl compatibility contour и не
связаны с RM-134.

## 3. Канонический owner данных

Единственный owner настроек collector-провайдеров —
`ProviderEnablementRepository` и файл `collector_provider_settings.json`.
Текущая schema version — `3`. Она уже хранит:

- enablement и non-secret конфигурацию известных провайдеров;
- health snapshot;
- созданные RM-133 `manual_registrations`.

Создание второго JSON/SQLite store не требуется. RM-134 должен расширить ту же схему до
version `4`, сохранив fail-closed чтение, atomic replace, backup первого предыдущего schema
и совместимость с v1/v2/v3.

## 4. Модель RM-133

`ManualProviderRegistration` сейчас содержит стабильный `manual_<uuid4hex>`, название,
официальный homepage, необязательный inert endpoint metadata, lifecycle
`protocol_required` и timestamps. Endpoint исключён из public payload/repr.

Текущее состояние manual provider проецируется так:

- `registration_only=True`;
- `runnable=False`;
- `factory_available=False`;
- `protocol_configured=False`;
- `credential_available=False`;
- `health_check_available=False`.

`ProviderSettingsSnapshot.assert_runnable_provider_ids`, run-session, unified search и UI
не допускают manual provider к запуску. Эти свойства обязаны сохраниться после выбора
протокола.

## 5. Каталог, factory и runtime

`resolved_provider_catalog()` уже объединяет статические определения и manual
registrations. Второй каталог не нужен. Для manual entry требуется только безопасная
проекция выбранного семейства и lifecycle.

`AsyncTenderProviderFactory` строит исключительно проверенные built-in adapters. Он не
принимает manual registrations и не должен получать protocol selection в RM-134.
`run_session` загружает snapshot до вызова factory, поэтому существующий fail-closed guard
является правильной точкой защиты.

Вывод: protocol selection — декларативная metadata, а не adapter/configuration object.
Создание адаптера относится к RM-135, connection test — к RM-136.

## 6. UI и application commands

`TenderProviderManagerDialog` уже является каноническим UI для provider states и RM-133
registration editor. Controller вызывает typed manager commands и затем перечитывает
states. Новый выбор протокола должен использовать тот же путь:

`dialog -> TenderSearchUiController -> CollectorProviderManager -> ProviderEnablementRepository`.

В UI нет безопасного способа редактировать manual protocol. Требуются отдельная кнопка и
dialog только для manual provider. Нельзя переиспользовать кнопку commercial API settings,
потому что её контракт и persistence отличаются.

## 7. Legacy-контур

`app.config.user_settings.PlatformConnection`, legacy-вкладка главного окна и
`app.connectors.manual.ManualConnectorTester` хранят свободные строки API/RSS/FTP/FTPS и
могут выполнять live network. Они сохранены исключительно для совместимости и явной
проверки старых записей.

RM-134 не импортирует, не мигрирует, не синхронизирует и не вызывает legacy-контур. Его
байты и поведение должны остаться неизменными. Existing legacy endpoint нельзя автоматически
считать canonical protocol selection.

## 8. Credentials

`ProviderCredentialService` имеет code-defined descriptors только для поддержанных
built-in providers. Manual registration не имеет descriptor/secret slot, а catalog
явно выставляет `credential_available=False`.

RM-134 может хранить только типизированное non-secret требование к аутентификации
(`none`, `api_key`, `username_password`). Значения ключей, токенов, паролей, usernames,
headers, query parameters и secret references не входят в scope. Credential owner и
descriptor registry не меняются.

## 9. Scheduler, profiles, health и diagnostics

- Scheduler UI получает те же `ProviderDisplayState`; manual provider остаётся disabled и
  non-runnable.
- Run-now и saved profile resolution дополнительно проходят canonical runnable guard.
- Health manager отвергает `registration_only`, а factory не создаёт manual adapter.
- Support/crash bundle не экспортирует `collector_provider_settings.json`; добавлять
  endpoint в diagnostics/logging нельзя.
- CLI/debug/live canary для manual provider отсутствует и в RM-134 не создаётся.

## 10. Public contracts и версия

Отдельного public protocol-selection contract сейчас нет. Версионируемый persistence
contract — provider settings schema v3. RM-134 вводит:

- schema v4;
- closed enum семейств `api`, `rss`, `ftp`, `ftps`;
- code-defined policy registry;
- typed selection payload;
- lifecycle `adapter_required` после успешного выбора.

Это additive изменение canonical settings contract. Runtime adapter protocols, provider
factory contract, credential contract и deterministic scoring/recommendation contracts не
изменяются.

## 11. Security findings и принятые границы

Protocol endpoint является private operational metadata. Он хранится локально, но не
попадает в repr, public payload, status message, logs или diagnostics. Валидация выполняется
до persistence и запрещает:

- userinfo, query, fragment, control/bidi characters и malformed percent-encoding;
- localhost, loopback, private, link-local, multicast, unspecified и reserved IP targets;
- неоднозначные numeric host forms;
- protocol/scheme mismatch, unsupported ports и downgrade для FTPS;
- FTP path traversal, backslashes, wildcard/shell-like path characters;
- secret-like parameter names/values в endpoint.

Открытие dialog и сохранение metadata не выполняют DNS или network I/O. Проверка endpoint
не обещает доступность площадки.

## 12. Решение аудита

RM-134 реализуется как малое расширение существующих domain/repository/manager/UI paths:

1. отдельный pure domain module для protocol family, policy, draft и selection;
2. nullable typed selection внутри `ManualProviderRegistration`;
3. schema v4 в существующем repository с migration/backup v3;
4. optimistic concurrency по ожидаемому `updated_at` для save/change/clear;
5. безопасная catalog/UI projection;
6. неизменные non-runnable/factory/credential/health guards.

Новый adapter, parser, transport, DNS resolver, network probe, secret store, scheduler path,
background worker или provider catalog не требуются и запрещены scope RM-134.
