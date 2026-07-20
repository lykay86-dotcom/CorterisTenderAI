# RM-152 owner-approved native exceptions

## Decision

- decision ID: `RM152-OWNER-EXCEPTIONS-2026-07-20`;
- approved by: project owner;
- approved at: 2026-07-20, Europe/Moscow;
- scope: every incomplete RM-152 native cell;
- policy: retain `BLOCKED` and `NOT_EXECUTED`; an exception is never a `PASS`.

The canonical machine-readable source is
`docs/evidence/RM-152_NATIVE_MATRIX.json`. Every record there names the exact cell, available and
unavailable environment, reason, residual risk, retained status, and decision ID. The fail-closed
validator rejects a missing/malformed exception and rejects status promotion.

## Exact register

| Exception | Cell | Retained status | Unavailable scope / residual risk |
|---|---|---|---|
| `RM152-EX-SR-01-DEV` | `SR-01-DEV` | `NOT_EXECUTED` | complete dev shell/topbar route, search, theme, notification speech; dev-only name/state defects may remain |
| `RM152-EX-SR-01-FROZEN` | `SR-01-FROZEN` | `NOT_EXECUTED` | complete frozen shell/topbar journey; frozen-only name/state defects may remain |
| `RM152-EX-SR-02-DEV` | `SR-02-DEV` | `NOT_EXECUTED` | complete dev Dashboard headings/KPI/feed/actions journey; value/state speech defects may remain |
| `RM152-EX-SR-02-FROZEN` | `SR-02-FROZEN` | `NOT_EXECUTED` | complete frozen Dashboard journey; packaged value/state speech defects may remain |
| `RM152-EX-SR-03-DEV` | `SR-03-DEV` | `NOT_EXECUTED` | complete dev search lifecycle/announcement journey; lifecycle or focus defects may remain |
| `RM152-EX-SR-03-FROZEN` | `SR-03-FROZEN` | `NOT_EXECUTED` | complete frozen search lifecycle journey; packaged lifecycle or focus defects may remain |
| `RM152-EX-SR-04-DEV` | `SR-04-DEV` | `NOT_EXECUTED` | complete dev registry/detail journey; warning order, decision, action, or provenance speech defects may remain |
| `RM152-EX-SR-04-FROZEN` | `SR-04-FROZEN` | `NOT_EXECUTED` | complete frozen registry/detail journey; packaged warning/decision speech defects may remain |
| `RM152-EX-SR-05-DEV` | `SR-05-DEV` | `NOT_EXECUTED` | complete dev modern-table journey; position, selection, sort, or fallback speech defects may remain |
| `RM152-EX-SR-05-FROZEN` | `SR-05-FROZEN` | `NOT_EXECUTED` | complete frozen modern-table journey; packaged table semantic defects may remain |
| `RM152-EX-SR-06-DEV` | `SR-06-DEV` | `NOT_EXECUTED` | complete dev chart/text-equivalent journey; identity/value/parity defects may remain |
| `RM152-EX-SR-06-FROZEN` | `SR-06-FROZEN` | `NOT_EXECUTED` | complete frozen chart/text-equivalent journey; packaged parity defects may remain |
| `RM152-EX-SR-07-DEV` | `SR-07-DEV` | `NOT_EXECUTED` | complete dev notification journey; unread/severity/action/arrival speech defects may remain |
| `RM152-EX-SR-07-FROZEN` | `SR-07-FROZEN` | `NOT_EXECUTED` | complete frozen notification journey; packaged announcement defects may remain |
| `RM152-EX-SR-08-DEV` | `SR-08-DEV` | `NOT_EXECUTED` | complete dev provider/credential journey; labels, state, or write-only handling defects may remain |
| `RM152-EX-SR-08-FROZEN` | `SR-08-FROZEN` | `NOT_EXECUTED` | complete frozen provider/credential journey; packaged secret-field semantic defects may remain |
| `RM152-EX-SR-09-DEV` | `SR-09-DEV` | `NOT_EXECUTED` | complete dev backup/import/recovery journey; target/warning/default/focus defects may remain |
| `RM152-EX-SR-09-FROZEN` | `SR-09-FROZEN` | `NOT_EXECUTED` | complete frozen backup/import/recovery journey; packaged safety speech defects may remain |
| `RM152-EX-SR-10-DEV` | `SR-10-DEV` | `NOT_EXECUTED` | complete dev crash/safe-mode/support journey; safe-summary or confidential-data defects may remain |
| `RM152-EX-SR-10-FROZEN` | `SR-10-FROZEN` | `NOT_EXECUTED` | complete frozen crash/safe-mode/support journey; packaged safe-feedback defects may remain |
| `RM152-EX-SR-11-DEV` | `SR-11-DEV` | `NOT_EXECUTED` | complete dev close/lifecycle journey; busy/terminal/deleted-focus defects may remain |
| `RM152-EX-SR-11-FROZEN` | `SR-11-FROZEN` | `NOT_EXECUTED` | complete frozen close/lifecycle journey; packaged lifecycle/focus defects may remain |
| `RM152-EX-NATIVE-1366-100-DL` | `NATIVE-1366-100-DL` | `NOT_EXECUTED` | no physical 1366x768 display; clipping, focus, or action reachability defects may remain |
| `RM152-EX-NATIVE-1366-125-DL` | `NATIVE-1366-125-DL` | `NOT_EXECUTED` | no physical 1366x768/125% environment; constrained-viewport defects may remain |
| `RM152-EX-NATIVE-1920-100-DL` | `NATIVE-1920-100-DL` | `BLOCKED` | complete all-route/all-state focus and Narrator journey; unvisited semantic defects may remain |
| `RM152-EX-NATIVE-1920-125-DL` | `NATIVE-1920-125-DL` | `BLOCKED` | complete 125% route/state/Narrator journey; unvisited clipping/focus defects may remain |
| `RM152-EX-NATIVE-1920-150-DL` | `NATIVE-1920-150-DL` | `BLOCKED` | complete 150% route/state/Narrator journey; unvisited clipping/focus defects may remain |
| `RM152-EX-NATIVE-2560-150-DL` | `NATIVE-2560-150-DL` | `NOT_EXECUTED` | no physical 2560x1440/150% display; layout/theme/popup defects may remain |
| `RM152-EX-NATIVE-2560-175-DL` | `NATIVE-2560-175-DL` | `NOT_EXECUTED` | no physical 2560x1440/175% display; layout/theme/popup defects may remain |
| `RM152-EX-NATIVE-3840-200-DL` | `NATIVE-3840-200-DL` | `NOT_EXECUTED` | no physical 4K/200% display; table/modal/layout defects may remain |
| `RM152-EX-NATIVE-HC` | `NATIVE-HC` | `BLOCKED` | complete high-contrast route/state/surface/Narrator matrix; invisible focus or collapsed semantics may remain |
| `RM152-EX-NATIVE-MIXED-DPI` | `NATIVE-MIXED-DPI` | `NOT_EXECUTED` | one monitor only; A-to-B-to-A geometry, popup, and removed-monitor defects may remain |
| `RM152-EX-NATIVE-FROZEN` | `NATIVE-FROZEN` | `NOT_EXECUTED` | complete combined frozen SR/DPI/high-contrast matrix; packaging-only defects may remain |

## Acceptance effect

The strict native gate passes only because all 33 truthful non-`PASS` cells have valid, explicit
exceptions. The evidence does not claim WCAG conformance, complete Windows Narrator support,
complete DPI coverage, mixed-monitor support, or native parity for unexecuted surfaces.
