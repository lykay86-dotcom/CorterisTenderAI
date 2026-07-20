# RM-152 acceptance report

## Verdict

`DONE` with explicit owner-approved native exceptions. Automated implementation, full regression,
frozen build, feature PR, exact merge-SHA gate, and strict evidence validation are green. The physical keyboard,
Windows Narrator, high-contrast, DPI/viewport, and mixed-DPI matrix remains incomplete: four cells
are `BLOCKED`, 29 are `NOT_EXECUTED`, and none is `PASS`. Decision
`RM152-OWNER-EXCEPTIONS-2026-07-20` names all 33 cells with exact environment, reason, residual
risk, and retained status. Feature PR #112 merged as
`5f20df74b89fcf6d67c7c79faa2e8cceca4b206b`; exact merge-SHA Quality Gate `29777125490`
passed. This separate canonical closeout transitions RM-152 to `DONE` and activates RM-153.

## Baseline and commits

- canonical baseline: `9cb37b9a83f50ac9f8f8e34fdeb582c2ed76e257`;
- RM-151 exact merge-SHA Quality Gate: run `29711141067`, Windows Python 3.12/3.13 success;
- audit/contracts: `b7c7612`;
- characterization: `307138b` (`7 passed`);
- expected-red: `1f0eed3` (`12` intended failures before implementation);
- implementation/guards/evidence: `5e0910d`;
- dark-theme native regression contract: `a0e6b39` (`2` intended failures before the fix);
- dark-theme native fallback fix: `9da4f79`;
- readable-Russian production guard: `bf2099e` (`5` production files failed before the fix);
- readable-Russian feedback fix: `0ab712d`;
- owner-exception expected-red contract: `7acd209`;
- fail-closed 33-cell exception registry and validator: `05ecca2`;
- deterministic stop-factor test time: `e570930`;
- feature head: `ae70c0ae5ee5fff0a1bcf374361d82d80bfb329a`;
- feature PR #112 merge: `5f20df74b89fcf6d67c7c79faa2e8cceca4b206b`.

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

- focused dark-theme and neighboring UI regression: `46 passed`;
- owner-exception/static focused contour: `20 passed`;
- stop-factor time-stability contour: `8 passed`;
- full suite after owner-exception acceptance: `2345 passed, 2 warnings in 197.56s`; both warnings are inherited openpyxl
  unsupported-extension warnings from the RM-132 legacy workbook fixture;
- Ruff: check passed; format check reports `772 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- secret scan and strict `scripts/check_rm152_accessibility.py --require-native-complete`: passed;
- offline credential/provider smoke: `2 passed in 17.35s`;
- database/schema smoke: `5 passed in 11.99s`;
- composition smoke: `1 passed in 0.52s`;
- release/frozen contract smoke: `7 passed in 11.56s`;
- dependency audit: no known vulnerabilities; editable project correctly skipped;
- PyInstaller `6.21.0` build succeeded on Python `3.12.7` / Windows `10.0.19045`;
- original observed frozen EXE SHA-256:
  `4D69D6B2378E77DBD179B86A8513FFB0CA20685489659F21778C3CD868F454D6`;
- rebuilt dark-theme-fix EXE SHA-256:
  `81A11CF64665E61A29739F349BA435F21B234252476B46917DC8D8A0D342A866`;
- rebuilt readable-Russian-fix EXE SHA-256:
  `11E59DC42FDBAC4F804D7006F01BA7E6AB7BA4E0C78B60DA455BBAB4993066F0`;
- final closeout EXE built from `e57093081e3e8695b0e1452f29585e9b58c07ac0`, size
  `83,485,730` bytes, SHA-256
  `5BED2D3F30AE6917F911800FBB85D7679BFBA6CEBB76F6F98F6B73376EBC2719`;
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
behaviour changed the active route to Analytics, and input calls timed out intermittently. A later
screenshot attempt against the confirmed exact-build process failed with
`SetIsBorderRequired failed: Интерфейс не поддерживается (0x80004002)`. The native protocol stopped
further automated input after that observation failure. In a subsequent owner-observed physical
keyboard probe on the open exact build, visible focus was confirmed and was seen moving between
controls. The owner also confirmed that the requested Tab sweep did not trap focus, Shift+Tab moved
backward, and no clipping or overlap was observed in the displayed state. The original
`NATIVE-1920-100-DL` run found white fallback strips after switching from light to dark. The source
fix is covered by expected-red/green tests, and rebuilt exact artifact `81A11C...A866` passed its
isolated frozen self-test. The owner then reran the same dark-theme surfaces on that exact build and
confirmed the white strips were removed. The cell is now `BLOCKED`, not `PASS`, because all semantic
states, complete route order, and Narrator output remain unobserved. The
next exact-build text-only UIA pass exposed 143 elements, but also reproduced mojibake in the
Russian safe-feedback banner directly from five production source files. An expected-red guard,
the source fix, `25` focused passes, `2344` full-suite passes, and a new frozen self-test are green.
Native launch of rebuilt artifact `11E59D...066F0` was not executed because the required Windows
app approval initially timed out. After explicit owner approval, the uniquely named exact artifact
was launched and confirmed by process path and the expected `Corteris Tender AI 1.3 Alpha` title.
Text-only UIA exposed 176 elements; the full tree contained zero mojibake marker lines, and the
status banner, AI warning, and data-state projection all exposed the correct Russian safe-feedback
text and diagnostic label. The UTF-8 defect rerun is `PASS`; the combined native cell remains
`BLOCKED`. Windows Narrator was then started with explicit owner approval on the exact build. A
slow sweep of 10 `Tab` and five `Shift+Tab` transitions was owner-observed: speech moved between
distinct controls, Russian names were readable, and reverse traversal moved backward without a
loop. This is partial Narrator evidence only; complete routes, roles, states, values, relations,
dynamic announcements, and semantic-state assertions remain incomplete. The
owner then explicitly approved a temporary Windows scale change from 100% to 125%. Windows
Settings UIA confirmed 125%, the exact frozen artifact was restarted, and its text-only UIA tree
retained 176 elements with zero mojibake marker lines. At 1920x1080/125%, the owner confirmed no
clipping or overlap, clean light/dark switching without white strips, and forward/reverse keyboard
movement without a trap. `NATIVE-1920-125-DL` is `BLOCKED`, not `PASS`, because the observation did
not cover every semantic state or a complete Narrator journey. After the run, Windows Settings UIA
confirmed restoration to `100% (recommended)`; the exact test process and Settings window were
closed. The owner next approved a temporary 150% run. Windows Settings UIA confirmed 150%, the
exact frozen artifact was restarted, and text-only UIA exposed 166 current elements with zero
mojibake marker lines and all key dashboard surfaces present. The owner confirmed no clipping or
overlap, clean light/dark switching without white strips, and forward/reverse focus movement
without a trap. `NATIVE-1920-150-DL` is `BLOCKED`, not `PASS`, because all semantic states and a
complete Narrator journey remain incomplete. Windows Settings UIA then confirmed restoration to
`100% (recommended)`; the exact test process and Settings window were closed. The owner then
approved Windows High Contrast Black and launched the same exact frozen artifact at
1920x1080/100%. Windows Settings UIA exposed the active theme selector, and the app exposed 176 UIA
elements with readable Russian names. After 10 `Tab` and five `Shift+Tab` transitions, the owner
confirmed no clipping, overlap, or white fallback strips, a visible focus indicator moving in both
directions without a trap, and distinguishable Russian text and control states. `NATIVE-HC` is
`BLOCKED`, not `PASS`, because only a representative dashboard state was exercised; complete
routes, semantic states, menus, tooltips, dialogs, tables, charts, destructive warnings, and
Narrator output remain incomplete. The owner disabled High Contrast after the run; registry Flags
`126` confirmed restoration, and the exact test process and Settings window were closed. The other
29 cells remain `NOT_EXECUTED`. The owner then explicitly approved named exceptions for all 33
non-`PASS` cells. The fail-closed validator requires the exact cell, decision ID, approver,
timestamp, available/unavailable environment, reason, residual risk, retained status, and
`accepted_without_pass=true`; malformed, missing, duplicate, unknown-cell, status-mismatch, or
`PASS` exceptions fail validation. The strict `--require-native-complete` gate now passes without
changing any cell status. The following remain explicitly unproven and accepted as residual risk:

- complete physical Tab/Shift+Tab order and visible focus across every route/state in dark, light,
  and high contrast;
- complete Narrator name/role/state/value/relations across all routes and bounded dynamic announcements;
- 1366x768 at 100/125%, complete 1920x1080 at 100/125/150%, 2560x1440 at 150/175%, and 4K at 200%;
- A->B->A mixed-DPI movement, saved/removed-monitor geometry, and frozen native parity.

## Owner exception decision and closeout gate

The owner explicitly approved decision `RM152-OWNER-EXCEPTIONS-2026-07-20`. The exact register is
`docs/RM-152_OWNER_EXCEPTIONS.md`; the authoritative structured records are in
`docs/evidence/RM-152_NATIVE_MATRIX.json`. This removes the native-evidence blocker for feature PR
creation and stage closeout while preserving every truthful `BLOCKED`/`NOT_EXECUTED` status and
residual risk.

Feature PR #112 on head `ae70c0ae5ee5fff0a1bcf374361d82d80bfb329a` merged as
`5f20df74b89fcf6d67c7c79faa2e8cceca4b206b`. PR-head Quality Gate `29776619427` passed on
Python 3.12/3.13 (jobs `88467423008` and `88467423174`). Exact merge-SHA Quality Gate
`29777125490` confirmed the merge commit and passed on Python 3.12/3.13 (jobs `88469119363` and
`88469119432`). All required steps, including the full suite and dependency audit, are `success`.
RM-152 now satisfies the Definition of Done; this docs-only closeout marks it `DONE` and makes
RM-153 the sole `IN PROGRESS` stage.
