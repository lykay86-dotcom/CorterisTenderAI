# PRE-RM-156 Collector — rollback plan

Дата: 22 июля 2026 года.

Rollback выполняется по package/PR границам. Он не стирает tender data, run history, settings,
profiles, decisions, manual resolutions, credentials или raw artifacts.

## 1. Общий порядок

1. Остановить новые scheduled/manual admissions через existing manager/UI controls.
2. Дождаться bounded shutdown текущего run либо выполнить normal cancellation.
3. Создать/проверить backup существующей `tender_registry.sqlite3` и settings files.
4. Отключить затронутый provider через `ProviderEnablementRepository`.
5. Revert только feature merge соответствующего package.
6. Не выполнять automatic schema downgrade.
7. Запустить migration/read-only compatibility, focused offline и bootstrap gates на старом коде.
8. Проверить сохранность registry keys, aliases, decisions, scores, checkpoints и run history.
9. Зафиксировать rollback evidence и причину; повторное включение — новый audited change.

## 2. P1/P2

P1 — docs-only: revert соответствующих docs commits возвращает governance text, не затрагивая
runtime/data. P2 — tests-only: revert expected-red PR удаляет только contract tests/fixtures. Ни P1,
ни P2 не требуют DB/settings rollback.

## 3. P3 foundation

- feature flag/admission path возвращается к one-page provider adapter;
- новые provider IDs не вводятся P3;
- version 15 DB не понижается: old code использует verified forward-compatible read path либо
  восстановленную pre-migration backup по отдельному подтверждённому runbook;
- versioned checkpoint, непонятный старому code, игнорируется и сохраняется для диагностики;
- content-addressed artifacts остаются на месте; orphan cleanup выполняется только retention job;
- если forward read path не доказан, rollback блокируется до restore drill — silent downgrade
  запрещён.

## 4. Provider package P4/P6/P7

- provider отключается canonical ID, не удаляя его settings/history;
- adapter merge revert не влияет на другие providers;
- parser и contract versions откатываются вместе;
- checkpoint несовместимой версии не применяется старым parser;
- alias/canonical identity не переиспользуется для другой площадки;
- credential остаётся в protected store и удаляется только явной user action;
- `WORKING` возвращается в `BLOCKED_EXTERNAL`/предыдущее доказанное состояние с audit reason;
- raw fixtures/artifacts/evidence сохраняются по retention policy.

## 5. P5 identity/settings migration

- до migration обязателен byte/integrity verified backup;
- compatibility aliases остаются читаемыми в обе стороны утверждённого transition window;
- rollback code не переписывает canonical rows обратно массово;
- при дефекте mapping provider отключается, migration останавливается, DB восстанавливается из
  verified backup только после проверки, что после backup не было новых user writes;
- ambiguous/unknown rows остаются quarantined для manual review, не присваиваются другой площадке;
- manual providers и `custom` records не затрагиваются.

## 6. P8 discovery

- discovery producer отключается без удаления queue/attempt history;
- official tender rows, созданные только из повторного official fetch, сохраняются;
- aggregator raw records не импортируются при rollback;
- очередь может быть прочитана старым UI через forward-compatible projection либо скрыта, но не
  очищена.

## 7. Closeout rollback

Docs-only closeout может быть reverted, если post-merge evidence ошибочно. Это возвращает
prerequisite в `IN PROGRESS` и снова блокирует production RM-156. Он не отменяет уже merged feature
packages автоматически: каждый package оценивается и при необходимости откатывается отдельно.
RM-157/RM-158 не активируются до повторного valid closeout.

## 8. Rollback acceptance

Rollback успешен только если:

- application запускается offline и shutdown bounded;
- current DB проходит `integrity_check` и schema compatibility/readback;
- user settings/profiles и protected credentials не потеряны;
- deterministic score/recommendation/critical stop-factor unchanged;
- disabled provider не выполняет network request;
- focused migration/bootstrap/build/frozen tests и secret scan green;
- точные backup/revert/test/commit IDs записаны в canonical history.
