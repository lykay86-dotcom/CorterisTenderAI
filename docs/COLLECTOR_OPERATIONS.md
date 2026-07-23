# Collector operations and support runbook

Дата проверки: 23 июля 2026 года.

## Offline stabilization diagnostic

Из project root:

```powershell
python scripts/check_pre_rm156_collector_offline.py
python scripts/check_pre_rm156_collector_offline.py --output .\p9-offline-report.json
```

Команда не требует credentials и не делает external requests. Успех означает:

- `catalog_count=13`;
- `network_calls=0`;
- два approved reference samples parsed;
- schema-15 migration/backup/restore drill passed;
- matrix не содержит неподтверждённого `WORKING`;
- top-level `passed=true`.

Report можно приложить к support case: в нём нет response bodies, auth headers, cookies, tokens,
private query и DB records. Не заменяйте approved fixtures live payload и не добавляйте secrets в
command line/output.

## Performance and resource diagnostic

Supported invocation:

```powershell
python -m scripts.benchmark_pre_rm156_collector_p3
```

Acceptance: exact `10,000/5,000`, p95 ≤10,000 ms, P1 regression ≤20%, RSS delta ≤64 MiB,
25-cycle task/thread/handle/temp growth zero, cancellation ≤1 second. При host-load variance
сохранить failed result, повторить на том же immutable SHA и не ослаблять thresholds.

## Provider interpretation

- `WORKING` требует offline contract, accepted real redacted fixture, approved live verification,
  health mapping и rollback evidence.
- `BLOCKED_EXTERNAL` означает честный внешний blocker, а не runtime success.
- `DISABLED` означает только user choice.
- Health HTTP success, hostname, token или settings сами по себе не дают `WORKING`.

Emergency disable выполняется existing Provider Manager. Не удаляйте history, checkpoints,
artifacts, provider IDs или credentials для отключения.

## Database backup and restore

- Migration owner: `CollectorSchemaMigrator`.
- Перед schema mutation migrator создаёт verified backup и readback.
- Explicit restore: `CollectorSchemaMigrator.restore_verified_backup(backup, target)`.
- Restore выполнять только при остановленном приложении, после отдельной копии current target и
  проверки отсутствия `-wal`/`-shm`.
- Не восстанавливать schema-15 backup поверх production schema-16, если после migration появились
  новые данные; предпочтителен roll-forward.
- Не удалять backup автоматически и не выполнять automatic downgrade.

P9 offline report проверяет restore только на isolated temporary database и никогда не открывает
user database.

## Failure and support handling

1. Сохранить exact commit SHA, command, exit code и sanitized report.
2. Не прикладывать DB, raw artifacts, credentials, cookies, headers или private URLs.
3. Для provider failure указать canonical provider ID и reason code.
4. Unexpected health exception отображается fixed message; подробный raw exception не должен
   попадать в persisted health JSON.
5. Live diagnostic запускается только отдельной opt-in процедурой с lawful access и credentials из
   keyring/environment; обычный pytest/CI остаётся offline.

## Rollback

Diagnostic script и health-message hardening revert-ятся независимо. Rollback не меняет schema,
user settings, credentials, tenders, scores, recommendation, critical stop-factor, artifacts,
checkpoints или history. Provider отключается существующим manager без удаления данных.
