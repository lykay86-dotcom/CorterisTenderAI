# PRE-RM-156 Collector P3 — validation log

Дата: 22 июля 2026 года.

Статус: `IN PROGRESS`; implementation готов, merge запрещён до зелёного performance gate.

## 1. Scope и baseline

- Exact baseline: P2 merge `83899900fd2913eefd0ad04398e266f4a6b64437`.
- Characterization commit: `f7dd6a2c82dc59744de6a4682dc92dee08d657e2`.
- Implementation commit: `b7f5aafcd6089872208e1f3c299f53d6fcac85ef`.
- Переиспользованы существующие `AsyncProviderSearchEngine`, `CollectorService`,
  `CollectorStateRepository`, session/factory/progress/UI owners; второй engine или DB не созданы.
- Provider identity/adapters, RM-107 decision logic, AI и production-модель контрагента не менялись.
- Для изменённой статусной UI-проекции read-only проверен canonical Figma node `41:35`
  (`综合治理`, 1920×1080); sample metrics и декоративное поведение не переносились.

## 2. Реализованные boundaries

- Backward-compatible typed page iterator, stable query fingerprint без navigation/secrets,
  deterministic page loop, cursor/non-progress/page/item budgets и cancellation между страницами.
- Typed cumulative resume/checkpoint и atomic accepted-page receipt/items/artifact/checkpoint commit.
- Content-addressed SHA-256 raw artifact store с 50 MiB hard limit, verification, deduplication,
  sanitized URL и коротким Windows-safe staging name.
- Schema 15 с explicit 14→15 inventory, verified backup/readback, restore и fail-closed future/corrupt
  handling; existing registry DB остаётся единственным storage owner.
- Process-wide run lease, page/artifact counters и truthful `TIMED_OUT`/`FAILED`/`PARTIAL` status.
- Typed budgets проходят через единый scheduler admission → session → service → engine:
  interactive 20 pages/10 000 items/180 s; scheduled 200/100 000/900 s; ceiling нельзя повысить.
- Сняты десять P3-owned strict xfail markers. Остаётся ровно `C-CP-001` для P4 EIS repair.

## 3. Зелёная локальная проверка

- Focused final: `61 passed, 1 xfailed in 25.14s`.
- Full exact implementation commit: `2437 passed, 1 xfailed, 2 warnings in 246.37s`.
- Secret scan, Ruff check, Ruff format (`798 files`), mypy (`20 source files`) и diff-check успешны.
- Mandatory offline pair: `2 passed`; migrations: `5 passed`; bootstrap: `1 passed`;
  build/frozen: `9 passed`; import smoke и RM-155 compatibility guard успешны.
- `pip-audit --skip-editable`: known vulnerabilities не найдены.
- 25-cycle resource contour: baseline/final tasks `1/1`, threads `1/1`, open-handle growth `0`,
  temp files `0`; offline cancellation `16.758 ms`, то есть budget ≤1 s пройден.

## 4. Непройденный performance gate

Норматив P1 не изменён: exact 10 000 raw / 5 000 merged, пять samples, nearest-rank p95
≤10 000 ms, не хуже P1 baseline `8 096.375 ms` более чем на 20%, RSS delta ≤64 MiB.

- Corrected normal-priority P3: p50 `14 781.712 ms`, p95 `15 051.716 ms`, RSS delta
  `49 913 856 bytes`; memory проходит, time/regression не проходят.
- Same-host corrected P2 A/B: p50 `14 719.283 ms`, p95 `15 022.911 ms`, RSS delta
  `74 227 712 bytes`. P3 time delta против текущего P2 составляет около `+0.19%`, поэтому
  P3-specific regression не обнаружена, но это не отменяет абсолютный утверждённый gate.
- High-priority diagnostic P3: p50 `11 250.687 ms`, p95 `11 354.335 ms`, RSS delta
  `57 638 912 bytes`; результат подтверждает фоновую CPU-конкуренцию, но также не проходит gate.

Ранние прогоны с удержанием warm-up/предыдущего full result признаны методически невалидными и не
используются как evidence. Скрипт `python -m scripts.benchmark_pre_rm156_collector_p3` освобождает
каждый result между samples и возвращает non-zero, пока любой норматив не выполнен.

## 5. Следующее действие и rollback

1. Повторить стандартный benchmark на освобождённом same-host контуре.
2. Только при зелёных p95/regression/RSS обновить этот документ как acceptance, открыть P3 PR и
   дождаться PR-head и exact merge-SHA Windows gates на Python 3.12/3.13.
3. P4 не начинать до exact P3 merge-SHA success.

Rollback до merge — revert implementation commit. После schema 15 предпочтителен roll-forward;
automatic downgrade запрещён. Verified schema-14 backup восстанавливается только явной операцией
при подтверждённом отсутствии новых schema-15 данных. User data, artifacts и audit evidence не
удаляются rollback-процедурой.
