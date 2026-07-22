# PRE-RM-156 Collector P2 — expected-red evidence

Дата: 22 июля 2026 года.

Baseline: P1 merge `6593fb2518d724c9bdde3ea46c9de84ff63b1b03`.

Contract commit: `c7c11ae`.

Scope: tests и test documentation only. `app/`, schema, dependencies, settings и production
fixtures не изменены.

## 1. Метод

Отсутствующие P3/P4 boundaries оформлены `pytest.mark.xfail(strict=True)` с immutable contract ID.
Regular pytest остаётся mergeable, но unexpected XPASS является failure. Тот же файл запускается
с `--runxfail`, чтобы доказать реальное падение каждого expected-red assertion до implementation.

Passing characterization tests не помечаются xfail: уже существующие discovery isolation,
completion-order determinism и public error redaction должны оставаться зелёными.

## 2. Contract matrix

| Contract ID | Test | P1 baseline |
|---|---|---|
| `C-PAGE-001` | engine consumes typed provider page iterator | expected-red |
| `C-PAGE-002` | repeated cursor fails boundedly | expected-red |
| `C-CANCEL-001` | cancellation between pages drops unaccepted page | expected-red |
| `C-CP-001` | EIS search does not commit checkpoint before page acceptance | expected-red |
| `C-CP-002` | checkpoint has version/fingerprint/replay/commit identity | expected-red |
| `C-STATUS-001` | zero successful providers gives `FAILED` | expected-red |
| `C-STATUS-002` | overall timeout keeps `TIMED_OUT` | expected-red |
| `C-DISC-001` | discovery excluded from partial normalization/dedup | passing guard |
| `C-ORDER-001` | completion order cannot change canonical output | passing guard |
| `C-IDENT-001` | engine rejects duplicate provider identity | expected-red |
| `C-ART-001` | raw artifact owner and accepted-page commit exist | expected-red |
| `C-SEC-001` | public error omits secret URL/body | passing guard |
| `C-MIG-001` | old Collector schema migration creates a new verified backup | expected-red |
| `C-LEASE-001` | repository rejects overlapping active runs | expected-red |

## 3. Direct red evidence

Command:

```powershell
python -m pytest -q --runxfail tests/test_pre_rm156_collector_expected_red.py
```

Result: `11 failed, 3 passed in 9.12s`.

Все 11 failures возникли на target assertions:

- page iterator не вызван;
- cancellation между pages не наблюдается;
- EIS checkpoint уже записан после provider search;
- typed checkpoint fields/save-accepted-page boundary отсутствуют;
- zero-success и timeout равны `partial`;
- duplicate provider ID не отвергается при engine composition;
- artifact module/accepted-page owner отсутствует;
- Collector 13→14 migration не создаёт новый backup;
- второй active run допускается.

Setup/import/fixture/network failures отсутствуют.

## 4. Regular green evidence

| Gate | Результат |
|---|---|
| P2 file | `3 passed, 11 xfailed in 9.89s` |
| focused neighbors + P2 | `27 passed, 11 xfailed in 20.02s` |
| full suite | `2414 passed, 11 xfailed, 2 warnings in 290.81s` |
| mandatory provider/diagnostic | `2 passed in 15.34s` |
| migration/schema | `5 passed in 10.46s` |
| bootstrap | `1 passed in 0.54s` |
| build/frozen | `9 passed in 8.56s` |
| secret scan | passed |
| Ruff | passed |
| Ruff format | `795 files already formatted` |
| mypy | 20 source files passed |
| RM-155 compatibility | passed |
| pip-audit | no known vulnerabilities |

Scoped `--basetemp` внутри worktree использован только из-за sandbox ACL системного temp. CI
продолжает использовать canonical команды workflow.

## 5. Exit

P2 не исправляет expected-red boundaries. Следующий package — отдельный P3 shared page/artifact/
checkpoint foundation от exact P2 merge SHA. Каждый strict xfail снимается только вместе с
implementation, которая делает соответствующий test pass; unexpected XPASS до этого блокирует PR.
