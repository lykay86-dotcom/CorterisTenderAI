# RM-152 acceptance report

## Verdict

`BLOCKED` for feature acceptance. Automated implementation and frozen build evidence are green,
but the required physical keyboard, Windows Narrator, high-contrast, DPI/viewport, and mixed-DPI
matrix was not executed and has no owner-approved exceptions. No unobserved cell is reported as a
pass, and RM-152 remains the sole `IN PROGRESS` stage.

## Baseline and commits

- canonical baseline: `9cb37b9a83f50ac9f8f8e34fdeb582c2ed76e257`;
- RM-151 exact merge-SHA Quality Gate: run `29711141067`, Windows Python 3.12/3.13 success;
- audit/contracts: `b7c7612`;
- characterization: `307138b` (`7 passed`);
- expected-red: `1f0eed3` (`12` intended failures before implementation);
- implementation/guards/evidence: `5e0910d`;
- branch: `feat/rm-152-accessibility-dpi` in dedicated `.worktrees/rm152`.

## Implemented contracts

- one shell traversal chain with stable sidebar/topbar/Dashboard IDs and bounded activity-feed
  exit; no global event filter;
- tables release `Tab` while retaining arrows/selection/Enter behavior;
- credential dialog restores focus only to a live, visible, enabled origin or explicit fallback;
- shared live-target semantics, Qt-free geometry clamp, and native-matrix validators;
- explicit names/descriptions for representative shell, status, search, table, verification,
  analysis, provider, backup, crash, and notification surfaces;
- focus styling covers tabs and scroll areas in addition to inherited controls;
- shell minimum is `960x540`; long Russian topbar text retains full accessible/tooltip content;
- machine-readable dark/light contrast inventory distinguishes threshold `PASS` from non-semantic
  `ADVISORY`; no local literal color was introduced;
- matrix validator rejects a `PASS` without actual observation, environment, and evidence.

RM-107 score, recommendation, and critical stop-factor priority are unchanged. Existing RM-142
route, RM-143 theme, RM-144 lifecycle, RM-146 chart, RM-150 table, and RM-151 operation owners are
reused. There is no database/schema/migration/dependency/network/AI/keyring/domain change.

## Inventory evidence

Static baseline -> post implementation:

| Measure | Baseline | Post |
|---|---:|---:|
| UI modules / lines | 91 / 36,614 | 97 / 37,243 |
| UI test modules | 148 | 151 |
| explicit name / description calls | 67 / 36 | 90 / 53 |
| literal colors outside theme | 0 | 0 |
| fixed / minimum / maximum calls | 15 / 34 / 6 | 15 / 35 / 6 |

Isolated runtime baseline -> post implementation: widgets `1,008 -> 1,008`, non-`NoFocus`
`252 -> 252`, accessible names `76 -> 84`, descriptions `31 -> 35`, and label/buddy relations
`194/25 -> 194/25`. The reproducible post command is
`python scripts/audit_rm152_runtime.py`; it uses only temporary settings and synthetic adapters.

## Automated verification

- RM-152 plus neighboring UI regression: `128 passed in 32.28s`;
- full suite: `2341 passed, 2 warnings in 134.33s`; both warnings are inherited openpyxl
  unsupported-extension warnings from the RM-132 legacy workbook fixture;
- Ruff: check passed; format check reports `771 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- secret scan and `scripts/check_rm152_accessibility.py`: passed;
- offline credential/provider smoke: `2 passed in 7.27s`;
- database/schema smoke: `5 passed in 5.03s`;
- composition smoke: `1 passed in 0.52s`;
- release/frozen contract smoke: `7 passed in 6.95s`;
- dependency audit: no known vulnerabilities; editable project correctly skipped;
- PyInstaller `6.21.0` build succeeded on Python `3.12.7` / Windows `10.0.19045`;
- frozen EXE SHA-256:
  `4D69D6B2378E77DBD179B86A8513FFB0CA20685489659F21778C3CD868F454D6`;
- isolated frozen self-test: `PASS`, nine checks including bundled resources, SQLite schema,
  offline provider composition, archive safety, analytics, and dark/light chart rendering.

The frozen report is not committed because its raw diagnostic details contain transient local
paths. This acceptance record keeps only privacy-safe, reviewable values.

## Native and DPI evidence

Environment discovery found one 1920x1080 display (available 1920x1040), logical DPI 96, DPR 1.0,
Narrator binary present, and Windows high contrast inactive. The newly built EXE manifest contains
`longPathAware` but no explicit DPI declaration. No process DPI-awareness change was made without
the required packaged/native matrix.

After Codex Desktop restart, the Windows automation connection succeeded. The first same-name
launch resolved to the installed `C:\Program Files\Corteris Tender AI\CorterisTenderAI.exe`, not
the RM-152 artifact, so its observations were discarded. An identical copy of the reviewed EXE
with a unique filename was then launched through an explicit process identifier; Windows reported
the exact `dist/CorterisTenderAI_RM152.exe` process and the expected `Corteris Tender AI 1.3 Alpha`
title. Text-only UI Automation returned a 176-element tree with exposed names, roles, states, and
table values. However, the reported focused element remained the global search even when keyboard
behaviour changed the active route to Analytics, and input calls timed out intermittently. The
screenshot path was not retried on the exact build after the channel had failed on the discarded
installed window with `SetIsBorderRequired failed: Интерфейс не поддерживается (0x80004002)`.
This evidence is insufficient for a physical keyboard, Narrator, or visual verdict. Therefore all
33 machine-readable native cells remain `NOT_EXECUTED`;
`--require-native-complete` reports exactly 33 `incomplete` errors. The following are not proven:

- physical Tab/Shift+Tab and visible focus in dark/light/high contrast;
- Narrator name/role/state/value/relations and bounded dynamic announcements;
- 1366x768 at 100/125%, 1920x1080 at 100/125/150%, 2560x1440 at 150/175%, and 4K at 200%;
- A->B->A mixed-DPI movement, saved/removed-monitor geometry, and frozen native parity.

## Blocker and required decision

Feature acceptance and PR creation are blocked until either:

1. the privacy-safe native matrix is executed on the required Windows environments and defects are
   fixed/rerun; or
2. the owner explicitly approves a named exception for every unavailable cell, with environment,
   reason, residual risk, and `NOT_EXECUTED`/`BLOCKED` status retained rather than converted to
   `PASS`.

No feature PR, merge, exact merge-SHA gate, docs-only closeout, `DONE` transition, or RM-153 start
is claimed in this state.
