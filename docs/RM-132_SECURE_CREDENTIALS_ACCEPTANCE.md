# RM-132 — acceptance безопасного ввода API и credentials

Дата локальной feature acceptance: 17 июля 2026 года.

## 1. Идентичность пакета

- Baseline: `d86b8867b298203e550074037e0c3a09f5bf2aa1`.
- Ветка: `feat/rm-132-secure-credentials-input`.
- Audit commit: `25b2eed` (`docs(rm-132): audit credential input boundaries`).
- Expected-red commit: `131f9a8` (`test(rm-132): define secure credential input contract`).
- Implementation commits: `5876bc9` и `f9365ea`.
- Regression commit: `3b26d15`.
- Feature PR, merge SHA и CI run IDs заполняются после публикации и merge; до этого RM-132
  остаётся `IN PROGRESS`.

## 2. Изменённые owners и call sites

- `app.security.secrets` остался единственным владельцем keyring service/account и получил
  presence-only запрос и bounded ошибки.
- Новый `app.tenders.provider_credentials` — storage-free typed application façade над тем же
  owner; он не хранит значения и не создаёт второй vault.
- `CollectorProviderManager` владеет façade, выполняет explicit save/replace/delete и присоединяет
  к display state только кэшированное безопасное состояние.
- MOS и commercial runtime adapters сохранили существующий explicit runtime load, но больше не
  экспортируют masked fragments и не публикуют raw backend errors.
- Existing provider manager/controller/dialog переведены на application commands для MOS и восьми
  commercial providers; сохранённое значение никогда не читается обратно в UI.
- Legacy manual-platform page больше не создаёт, не читает и не удаляет произвольные
  `platform:<name>` credentials. Неизвестные прежние записи сохранены для rollback.

## 3. Доказательство единственного vault и отсутствия readback

`ProviderCredentialService` не имеет persistence, encryption или файловой схемы. Production backend
делегирует только существующим `save_secret`, `has_secret` и `delete_secret` с неизменным service
`CorterisTenderAI` и каноническими account names. JSON settings, health SQLite и tender registry не
изменяются credential-командами. Replacement выполняет одну запись после явного подтверждения;
delete идемпотентен. Environment остаётся runtime-only override и не копируется в protected store.

Диалог всегда открывается пустым, очищает widget после submit/cancel, отдаёт новое значение ровно
один раз через `take_value()` и получает назад только typed result без поля value. Masked value
properties удалены. Ошибки backend сводятся к фиксированным категориям без `str(exc)`, traceback
cause, путей, header/token fragments или secret sentinel.

## 4. Локальная acceptance Windows/Python 3.12.7

Environment: `PYTHONUTF8=1`, `QT_QPA_PLATFORM=offscreen`, repository-local ignored basetemp.

- Expected-red: семь collection errors только из-за отсутствующих RM-132 symbols; зафиксировано в
  audit evidence перед production implementation.
- Focused RM-132: `21 passed, 2 warnings in 3.52s`.
- RM-131 и соседний provider/UI/support/crash contour: `110 passed in 8.59s`.
- Full pytest: `1707 passed, 2 warnings in 64.89s`.
- Repository secret scan: passed.
- Ruff check: passed.
- Ruff format check: `570 files already formatted`.
- Mypy required contour: `Success: no issues found in 20 source files`.
- Offline credential isolation smoke: `2 passed in 3.85s`.
- Migration/schema smoke: `5 passed in 2.67s`.
- Public API import smoke: `DashboardController` imported successfully.
- Headless composition smoke: `1 passed in 0.19s`.
- Release/build smoke: `6 passed in 3.23s`.
- Dependency audit: `No known vulnerabilities found`; editable project skipped as designed.
- `git diff --check`: passed.

Два warnings focused/full contour исходят от openpyxl при чтении существующего workbook extension;
они не относятся к credential contract и не скрывают failures.

## 5. CI и merge evidence

- Feature PR: pending.
- PR Quality Gate Python 3.12/3.13 run: pending.
- Feature merge SHA: pending.
- Exact merge-SHA Quality Gate run: pending.
- Docs-only closeout PR и final main gate: pending.

Эти пункты обязательны до перевода RM-132 в `DONE` и активации RM-133.

## 6. Ограничения и rollback

RM-132 не проверяет реальные credentials и не запускает live provider I/O. Commercial API contracts
по-прежнему требуют отдельной верификации. Environment override может быть удалён только владельцем
процесса/environment; UI удаляет лишь protected-store запись и явно сообщает, что override остаётся.

Rollback — scoped revert feature commits. Service/account names, JSON schema и SQLite schema не
менялись, поэтому data migration не требуется. Legacy arbitrary keyring entries намеренно не
угадывались, не копировались и не удалялись.

RM-133–RM-200 production scope не затронут; decision/scoring/AI semantics не изменены.
