# RM-152 screen-reader and native evidence matrix

Baseline: `9cb37b9a83f50ac9f8f8e34fdeb582c2ed76e257`
Primary reader: Windows Narrator

## Evidence policy

`PASS` requires an actual native observation on the recorded app commit/build and environment.
`FAIL`, `BLOCKED`, and `NOT_EXECUTED` are distinct. Automated `setAccessibleName`, offscreen tests,
Qt role assumptions, screenshots, or a historical pass cannot promote a native cell.

All evidence uses temporary clean/seeded settings and synthetic data. Transcripts/screenshots omit
machine username, real paths, credentials, crash reports, customers, query strings, and raw errors.

## Status vocabulary

| Status | Meaning |
|---|---|
| `PASS` | observation completed and every assertion passed |
| `FAIL` | observation completed with a reproducible defect |
| `BLOCKED` | attempted but environment/product defect prevented completion |
| `NOT_EXECUTED` | not actually observed |

## Environment discovery record

| Field | Current discovered value |
|---|---|
| OS | Windows 10 `10.0.19045` |
| execution | physical local Windows session; RDP/VM not asserted |
| display | one `DELL E2218HN`, 1920x1080, available 1920x1040, 60 Hz |
| scale | logical DPI 96, DPR 1.0 (100%) |
| monitor count / mixed scale | 1 / unavailable in discovered environment |
| Python | 3.12.7 |
| PySide6 / Qt | 6.11.1 / 6.11.1 |
| app | dev source plus newly packaged RM-152 executable; automated frozen self-test passed |
| Narrator/high contrast | Narrator binary present / high contrast inactive; no journey executed |
| locale/input | Russian UI strings present; exact OS/input metadata not yet recorded |
| operator/timestamp | Codex-assisted session / 2026-07-20 Europe/Moscow |

Environment discovery is not a matrix execution. Every cell below starts `NOT_EXECUTED`.
The machine-readable source is `docs/evidence/RM-152_NATIVE_MATRIX.json`; the RM-152 guard rejects
`PASS` without an observation, environment metadata, and at least one evidence record.

## Representative Narrator matrix

| Cell | Surface / journeys | Required observation | Dev | Frozen |
|---|---|---|---|---|
| SR-01 | sidebar/topbar, J01/J04/J08/J14 | route names/selected; search; theme state; notification count/action | NOT_EXECUTED | NOT_EXECUTED |
| SR-02 | Dashboard, J01/J03 | heading, KPI name/exact value/state, feed identity/action, quick actions | NOT_EXECUTED | NOT_EXECUTED |
| SR-03 | search operation, J04/J07 | labels; running/partial/failure/cancelling/cancelled/terminal; no focus steal | NOT_EXECUTED | NOT_EXECUTED |
| SR-04 | registry/detail, J09/J11 | headers/selection; critical warning first; decision unchanged; actions/provenance | NOT_EXECUTED | NOT_EXECUTED |
| SR-05 | table, J03/J08/J09/J12 | headers, row/column/selection/sort/state, exact target, removed-row fallback | NOT_EXECUTED | NOT_EXECUTED |
| SR-06 | chart/text equivalent, J09/J12 | title, series/point, selection, value, F2 table, full equivalent | NOT_EXECUTED | NOT_EXECUTED |
| SR-07 | notifications, J08 | unread/severity/time/title/summary/action; bounded arrival announcement | NOT_EXECUTED | NOT_EXECUTED |
| SR-08 | providers/credentials, J06/J10 | labels/state; write-only field; no secret value/readback | NOT_EXECUTED | NOT_EXECUTED |
| SR-09 | backup/import/recovery, J13/J15 | exact target, warning, safe default, result/partial/failure, stable return | NOT_EXECUTED | NOT_EXECUTED |
| SR-10 | crash/safe mode/support, J02/J15 | safe summary/correlation/action; no path/raw traceback in ordinary feedback | NOT_EXECUTED | NOT_EXECUTED |
| SR-11 | close/lifecycle, J16 | busy/close decision and terminal status, no late focus to deleted object | NOT_EXECUTED | NOT_EXECUTED |

For each row record announced name, role, state/value, position/selection, description/help, action
result, focus order, duplicate/missing speech, dynamic update behavior, and confidential-data scan.

## Native keyboard/theme/DPI session register

| Session | Required environment | Status | Evidence |
|---|---|---|---|
| NATIVE-1366-100-D/L | 1366x768, 100%, dark/light, physical keyboard | NOT_EXECUTED | none |
| NATIVE-1366-125-D/L | 1366x768, 125%, dark/light, physical keyboard | NOT_EXECUTED | deterministic baseline minimum predicts failure; native observation still required |
| NATIVE-1920-100-D/L | 1920x1080, 100%, dark/light, all semantic states | FAIL | keyboard worked in both themes, but dark theme exposed white native fallback strips on the original build; fixed build `81A11C...A866` passed frozen self-test and awaits native visual rerun; all states and Narrator incomplete |
| NATIVE-1920-125-D/L | 1920x1080, 125%, dark/light | NOT_EXECUTED | none |
| NATIVE-1920-150-D/L | 1920x1080, 150%, dark/light | NOT_EXECUTED | none |
| NATIVE-2560-150-D/L | 2560x1440, 150%, dark/light | NOT_EXECUTED | no such display discovered |
| NATIVE-2560-175-D/L | 2560x1440, 175%, dark/light | NOT_EXECUTED | no such display discovered |
| NATIVE-3840-200-D/L | 3840x2160, 200%, dark/light | NOT_EXECUTED | no such display discovered |
| NATIVE-HC | Windows high contrast, representative surfaces | NOT_EXECUTED | none |
| NATIVE-MIXED-DPI | two monitors, A→B→A, separate dialog | NOT_EXECUTED | one monitor discovered |
| NATIVE-FROZEN | newly packaged executable, representative SR/DPI/HC | NOT_EXECUTED | EXE built and automated self-test passed; native journey not executed |

## Dynamic announcement observations

Native search/operation runs use synthetic adapters and a finite logical scenario: start, phase
change, 10% buckets where applicable, partial/failure/success/cancel request/confirmed cancel, and
terminal notification. Record exact speech count and content. RM-151 rules remain:

- terminal is never suppressed;
- duplicate progress is coalesced;
- partial differs from success;
- cancelling differs from cancelled;
- one terminal is not repeated by in-surface/status/notification projections;
- focus remains on the user's control;
- no path, secret, query, raw exception, markup, or bidi marker is spoken.

## Matrix update rules

Each executed cell adds Windows/build/display/DPI/theme/Narrator/settings/locale/operator/timestamp,
exact steps, observed output, privacy-scrubbed artifact links, and linked defect/fix/rerun. Native
multi-monitor, unsupported viewport, high-contrast, or frozen gaps require actual execution or an
explicit owner-approved exception before RM-152 feature acceptance. Silence is not approval.
