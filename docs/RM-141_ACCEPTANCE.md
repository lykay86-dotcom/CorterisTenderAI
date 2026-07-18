# RM-141 acceptance record

## Current verdict

`ACCEPTED FOR DOCS-ONLY CLOSEOUT` — entry gate, baseline, inventory, runtime characterization,
focused UI suite, final local Quality Gate, audit PR merge and exact merge-SHA Quality Gate are
complete. This separate closeout marks RM-141 `DONE` and RM-142 as the sole `IN PROGRESS` stage.
No RM-142 production code is included.

## Entry gate

| Evidence | Result |
|---|---|
| Local `main` / `origin/main` before branch | both `8e704cf74c64e2125ace165807d1a33d3937b739` |
| RM-140 feature PR | #88, merged as `8c09ca6df469549b4ae50457b6924898a629c0d2` |
| RM-140 closeout PR | #89, merged; closing main SHA `8e704cf74c64e2125ace165807d1a33d3937b739` |
| Feature PR Quality Gate | run `29651765243`, Python 3.12/3.13 success |
| Feature exact merge-SHA gate | run `29651986321`, Python 3.12/3.13 success |
| Closeout PR Quality Gate | run `29652359999`, Python 3.12/3.13 success |
| Closeout exact-SHA gate | run `29652536755`, Python 3.12/3.13 success, dependency audit included |
| Canonical status at audit branch creation | RM-140 `DONE`; RM-141 sole `IN PROGRESS`; RM-142–RM-200 `PLANNED` |
| Audit worktree/branch | clean detached worktree from exact SHA; `docs/rm-141-ui-audit` |
| User changes | root checkout untracked `.agents/` and `skills-lock.json` preserved and excluded |

## Environment

- Host: Windows 10 10.0.19045, Europe/Moscow.
- Python: `C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe`, 3.12.7.
- pytest 9.1.1; Ruff 0.15.21; mypy 1.20.2; pip-audit 2.10.1; PySide6 6.11.1.
- Qt runtime characterization: `QT_QPA_PLATFORM=offscreen` with temporary settings/data.
- Shared Windows `%TEMP%` was inaccessible (`WinError 5`), so pytest used a repository-ignored,
  per-run `--basetemp` under the clean worktree. This changes no test semantics.

## Baseline quality gate at exact RM-140 closeout SHA

| Command/contour | Result |
|---|---|
| `python scripts/check_repository_secrets.py` | passed |
| `python -m ruff check .` | passed |
| `python -m ruff format . --check` | 630 files already formatted |
| `python -m mypy` | success, 20 source files |
| offline collector/diagnostic selection | 2 passed in 15.40 s |
| migration/schema contract selection | 5 passed in 10.02 s |
| `from app.ui.controllers import DashboardController` | imported `DashboardController` |
| bootstrap tender-search composition | 1 passed in 0.45 s |
| build/frozen contract selection | 6 passed in 11.49 s |
| full `pytest -q` with isolated base temp | 1,946 passed, 2 warnings in 144.18 s |
| local `python -m pip_audit --skip-editable` | `NOT_EXECUTED`: sandbox denied dependency-index metadata transmission |
| same-SHA GitHub dependency audit | passed in run `29652536755`, Python 3.12/3.13 |

The two full-suite warnings are existing openpyxl warnings in
`test_rm132_legacy_credentials_handoff.py`: unsupported worksheet extension and conditional
formatting extension. No test was skipped or replaced by a sample set.

## RM-141 audit validations

| Command/method | Result |
|---|---|
| `python -m scripts.audit_ui_inventory --format summary` | 68 modules, 28,910 lines, deterministic JSON summary |
| inventory script Ruff/format | passed |
| `python -m scripts.benchmark_rm141_ui_models` | passed; 12 measurements, no pass threshold |
| benchmark script Ruff/format | passed |
| UI/PySide6 selection from 97 test modules | 302 passed, 2 warnings in 81.39 s |
| isolated shell composition | one `QMainWindow`, 9 routes, 960 widgets; no socket connection |
| tender action/tab inventory | 8 workspace tabs, 6 settings tabs, 9 controller actions |
| rapid shell close during health refresh | reproduced late deleted-signal-source error; UI-141-005 |
| application/dependency/schema diff | no `app/`, dependency, migration, DB schema or production behavior change |

Final local Quality Gate was executed after both audit-content commits at branch SHA
`e307d3a349909cd7a97d9accacf6ee47b6bf4c1d`:

| Contour | Result |
|---|---|
| repository secret scan | passed |
| Ruff check | passed |
| Ruff format check | 632 files already formatted |
| mypy | success, 20 source files |
| combined mandatory offline/migration/composition/build selection | 14 passed in 19.32 s |
| Dashboard controller import | passed |
| full `pytest -q` with isolated base temp | 1,946 passed, 2 warnings in 165.52 s |

The subsequent acceptance-only commit records these results and changes no executable file.

## Model performance baseline

Method: Windows 10/Python 3.12.7/PySide6 6.11.1/offscreen, deterministic generated fixtures,
`perf_counter_ns`, two warmups, nine recorded runs, data construction excluded, no arbitrary SLA.

| Scenario | Rows | p50 ms | p95 ms | Range ms |
|---|---:|---:|---:|---:|
| workflow reset/sort | 0 | 0.004 | 0.005 | 0.004–0.005 |
| workflow filter, missing text | 0 | 0.007 | 0.008 | 0.006–0.008 |
| Dashboard tender reset | 0 | 0.003 | 0.004 | 0.003–0.004 |
| workflow reset/sort | 100 | 0.059 | 0.064 | 0.057–0.064 |
| workflow filter, missing text | 100 | 0.970 | 1.937 | 0.868–1.937 |
| Dashboard tender reset | 100 | 0.004 | 0.005 | 0.004–0.005 |
| workflow reset/sort | 1,000 | 0.656 | 2.230 | 0.597–2.230 |
| workflow filter, missing text | 1,000 | 11.969 | 14.559 | 9.591–14.559 |
| Dashboard tender reset | 1,000 | 0.010 | 0.020 | 0.009–0.020 |
| workflow reset/sort | 10,000 | 8.399 | 12.352 | 7.337–12.352 |
| workflow filter, missing text | 10,000 | 121.738 | 148.005 | 112.072–148.005 |
| Dashboard tender reset | 10,000 | 0.055 | 0.059 | 0.053–0.059 |

These values characterize model operations only. They are not a native paint, memory, startup or
end-to-end latency claim.

## Required Windows DPI manual test case

Status for every row below: `NOT_EXECUTED` in RM-141 due no controlled interactive display/scaling
matrix. RM-152 owns execution; the missing result is not a pass.

| Viewport | Scaling | Themes | Required route/state sweep |
|---|---:|---|---|
| 1366x768 | 100%, 125% | dark/light | shell, all routes, tender tabs, workflow dialogs |
| 1920x1080 | 100%, 125%, 150% | dark/light | same plus empty/loading/partial/error/success |
| 2560x1440 | 150%, 175% | dark/light | same plus theme and page switching |
| 3840x2160 | 200% | dark/light | same plus large table and modal nesting |

For each cell: launch with clean temporary settings; record Windows/Qt/Python/display metadata;
capture no-user-data screenshots; traverse Tab and Shift+Tab; activate with Enter/Space; close with
Escape/Alt+F4; inspect clipping, overlap, elision, scroll access, focus, hit targets, Russian label
growth and table headers; move across differently scaled monitors where available; verify saved
geometry remains on-screen. Record exact failures, not subjective “looks good”.

## Other `NOT_EXECUTED` evidence

- Native NVDA/Narrator/Windows high-contrast and IME/touch exercises.
- Reliable bootstrap-to-first-paint, native render, repeated dialog/theme/page cycles, peak-memory
  and QObject-leak benchmark. RM-153 owns instrumentation and budgets.
- Screenshot/golden comparison. RM-154 owns deterministic environment and review workflow.
- Live provider, live credentials/keyring values, private user data and real support-bundle contents,
  intentionally excluded for safety and determinism.

## Finding and handoff completeness

The audit register contains 17 findings: P0 0, P1 0, P2 16, P3 1. Each has status, evidence,
runtime consumer, expected invariant, impact, owner, tests, regression contract, dependencies,
compatibility concern and confidence. Each is mapped exactly once to a primary RM in RM-142–RM-155.
No stop-condition P0/P1 was evidenced.

## PR and merge evidence

| Gate | Status |
|---|---|
| Audit branch final full local gate | PASSED at `e307d3a349909cd7a97d9accacf6ee47b6bf4c1d` |
| Audit PR number and head SHA | #90; `f5de117d15265fb1529df346e577f571b1ccc838` |
| Audit PR Windows Quality Gate 3.12/3.13 | run `29654916158`; success / success |
| Audit PR merge SHA | `a2e8d0528a1b9c6378a543a5c9f2c5b762483c63` |
| Exact audit merge-SHA gate 3.12/3.13 | run `29655095879`; success / success; dependency audit passed |
| Docs-only closeout | this separate branch/PR; PR number and merge SHA are non-self-referential final-report evidence |

Rollback is a revert of RM-141 audit docs/read-only scripts and this closeout status update only.
RM-142+ code was not implemented.
