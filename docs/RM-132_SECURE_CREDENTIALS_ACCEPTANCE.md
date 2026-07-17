# RM-132 — acceptance безопасного ввода API и credentials

Дата локальной feature acceptance: 17 июля 2026 года.

## 1. Идентичность пакета

- Baseline: `d86b8867b298203e550074037e0c3a09f5bf2aa1`.
- Ветка: `feat/rm-132-secure-credentials-input`.
- Audit commit: `25b2eed` (`docs(rm-132): audit credential input boundaries`).
- Expected-red commit: `131f9a8` (`test(rm-132): define secure credential input contract`).
- Implementation commits: `5876bc9` и `f9365ea`.
- Regression commit: `3b26d15`.
- Acceptance commit: `3112021` (`docs(rm-132): record secure credentials acceptance`).
- Feature PR: #70 (`feat(rm-132): secure API and credential input`).
- Feature merge SHA: `1ae9c36605043e35333dffc60a6077c16fbd19f4`.

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

- PR Quality Gate run `29565942602` успешен: Python 3.12 —
  `1707 passed, 2 warnings in 186.83s`, Python 3.13 —
  `1707 passed, 2 warnings in 76.36s`.
- PR job IDs: Python 3.12 — `87838466168`, Python 3.13 — `87838466211`.
- PR #70 слит в `main` merge commit
  `1ae9c36605043e35333dffc60a6077c16fbd19f4`.
- Exact merge-SHA Quality Gate run `29567132554` успешен: Python 3.12 —
  `1707 passed, 2 warnings in 121.29s`, Python 3.13 —
  `1707 passed, 2 warnings in 79.55s`.
- Exact-SHA job IDs: Python 3.12 — `87842163233`, Python 3.13 — `87842163130`.
- В обоих runs прошли secret scan, Ruff check/format (`570 files`), mypy
  (20 файлов), offline/migration/import/composition/build smoke и dependency audit.
- Неблокирующее GitHub annotation о Node.js 20/24 относится к закреплённым
  official actions и не повлияло на зелёные jobs.
- Docs-only closeout branch: `docs/rm-132-completion`; closeout PR и final main gate
  выполняются после этого evidence commit.

## 6. Ограничения и rollback

RM-132 не проверяет реальные credentials и не запускает live provider I/O. Commercial API contracts
по-прежнему требуют отдельной верификации. Environment override может быть удалён только владельцем
процесса/environment; UI удаляет лишь protected-store запись и явно сообщает, что override остаётся.

Rollback — scoped revert feature commits. Service/account names, JSON schema и SQLite schema не
менялись, поэтому data migration не требуется. Legacy arbitrary keyring entries намеренно не
угадывались, не копировались и не удалялись.

RM-133–RM-200 production scope не затронут; decision/scoring/AI semantics не изменены.
