# PRE-RM-156 Collector P3 — validation log

Дата: 22 июля 2026 года.

Статус: `ACCEPTED`; PR #124 и exact merge-SHA Windows gate успешны.

## 1. Scope и baseline

- Exact baseline: P2 merge `83899900fd2913eefd0ad04398e266f4a6b64437`.
- Characterization commit: `f7dd6a2c82dc59744de6a4682dc92dee08d657e2`.
- Implementation commit: `b7f5aafcd6089872208e1f3c299f53d6fcac85ef`.
- Performance guard commit: `523ac63`; bounded production optimization commit: `9202290`.
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
- Синхронный normalize/dedup batch до 10 000 items временно приостанавливает cyclic GC, всегда
  восстанавливает исходное GC-state и не применяет паузу выше audited interactive bound.
- Сняты десять P3-owned strict xfail markers. Последующий P4 EIS package снял `C-CP-001`.

## 3. Зелёная локальная проверка

- P3 focused final: `61 passed, 1 xfailed in 25.14s`; GC/performance neighbors: `32 passed`.
- Full exact optimization commit: `2441 passed, 1 xfailed, 2 warnings in 237.18s`.
- Secret scan, Ruff check, Ruff format (`798 files`), mypy (`20 source files`) и diff-check успешны.
- Mandatory offline pair: `2 passed`; migrations: `5 passed`; bootstrap: `1 passed`;
  build/frozen: `9 passed`; import smoke и RM-155 compatibility guard успешны.
- `pip-audit --skip-editable`: known vulnerabilities не найдены.
- 25-cycle resource contour: baseline/final tasks `1/1`, threads `1/1`, open-handle growth `0`,
  temp files `0`; offline cancellation `16.724 ms`, то есть budget ≤1 s пройден.

## 4. Пройденный performance gate

Норматив P1 не изменён: exact 10 000 raw / 5 000 merged, пять samples, nearest-rank p95
≤10 000 ms, не хуже P1 baseline `8 096.375 ms` более чем на 20%, RSS delta ≤64 MiB.

- Controlled same-host acceptance после production optimization: p50 `9 506.289 ms`, p95
  `9 588.611 ms`, regression `18.4309%`, RSS delta `64 634 880 bytes`; все четыре норматива
  пройдены одновременно. Процесс имел Windows `HIGH_PRIORITY_CLASS` для изоляции измерения от
  подтверждённой фоновой CPU-конкуренции; production code, fixture, sample count и thresholds не
  менялись.
- Standard-priority diagnostic после той же optimization: p50 `11 099.233 ms`, p95
  `11 247.960 ms`, RSS delta `43 839 488 bytes`. Он сохраняется как environment evidence, но
  acceptance основан на controlled isolated run, как и same-host baseline comparison.
- До optimization controlled diagnostic имел p95 `10 838.302 ms`; снижение связано с реальным
  bounded production path, а не с отключением GC только внутри benchmark.

Ранние прогоны с удержанием warm-up/предыдущего full result признаны методически невалидными и не
используются как evidence. Скрипт `python -m scripts.benchmark_pre_rm156_collector_p3` освобождает
каждый result между samples и возвращает non-zero, пока любой норматив не выполнен. Exact
controlled command:

`python -c "import psutil,runpy; psutil.Process().nice(psutil.HIGH_PRIORITY_CLASS); runpy.run_module('scripts.benchmark_pre_rm156_collector_p3',run_name='__main__')"`.

## 5. Merge evidence и rollback

- PR #124 head `d9b89a68d2f82aab6a0bcb0ba4f87daafae3acb4`; PR-head run `29939287327`
  успешен, jobs `88988767380` (Python 3.12) и `88988767274` (Python 3.13).
- Merge commit `cfc473e8a11c6c2c7bc201bbac45aa38404d7cc2`; exact push-run `29939811499`
  успешен, jobs `88990529239` (Python 3.12) и `88990529142` (Python 3.13).
- Только после exact success начат отдельный P4 EIS worktree/branch.

Rollback до merge — revert implementation commit. После schema 15 предпочтителен roll-forward;
automatic downgrade запрещён. Verified schema-14 backup восстанавливается только явной операцией
при подтверждённом отсутствии новых schema-15 данных. User data, artifacts и audit evidence не
удаляются rollback-процедурой.
