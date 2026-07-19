# RM-150 state and accessibility contract

Baseline: `c7b9c2210dbcbb5db7b9b24fc81f0809d05f8d6b`

## State presentation

| State | Rows | Required presentation | Actions |
|---|---:|---|---|
| `LOADING` | 0 | explicit progress/status region | row actions disabled |
| `EMPTY` | 0 | successful empty message and optional bounded recovery action | no fake selectable row |
| `ERROR` | 0 | error summary, safe detail and retry where owner provides it | no stale row action |
| `PARTIAL` | 0+ | visible partial-data warning plus available rows | only owner-approved actions |
| `READY` | 0+ | table; zero rows must transition to `EMPTY` | normal owner-approved actions |

Messages live in a sibling status region, never in a fabricated row. State changes clear stale
selection/action tokens. Error details are plain text and must not expose secrets, raw credentials or
unsafe rich text.

## Accessible structure

- Every migrated table has a stable accessible name and a purpose-oriented description.
- Every column exposes a non-empty header and, where the header is abbreviated, a full accessible
  description and unit.
- Each cell exposes the full semantic value; color, icon, elision and tooltip are never the sole
  carrier of status, criticality, partiality or action availability.
- Critical stop-factor text precedes approved score/recommendation in both visual and accessible
  reading order.
- Status-region changes are announced without moving focus or silently selecting a row.
- The current row's accessible text includes its stable human label and state, never an opaque ID
  alone.

## Keyboard and focus

Tab reaches the filter, table and external action controls in visual order. Arrow/Page/Home/End
navigation remains native. Space selects; Enter invokes the one documented primary action; context
actions are keyboard reachable. Escape never commits an edit or destructive action. After refresh,
focus follows exact identity if present and otherwise returns to the table/status region with no
neighbor selection.

Editable cells provide an accessible editor name, preserve typed validation, commit explicitly and
return focus to the same row identity. Validation errors remain associated with the editor and do
not replace table rows.

## Verification evidence

Automated Qt tests verify names, descriptions, headers, state-region visibility, keyboard dispatch,
focus/selection restoration and non-color status text. Manual keyboard verification is recorded in
acceptance. Screen-reader testing must be reported as `EXECUTED` with environment/results or
`NOT_EXECUTED`; it must never be implied by automated accessibility-property assertions.
