# RM-152 accessible semantics contract

Baseline: `9cb37b9a83f50ac9f8f8e34fdeb582c2ed76e257`

## Boundary and source of truth

RM-152 exposes existing presentation facts through native Qt semantics. It cannot calculate,
repair, reorder, or override RM-107 score/recommendation/critical precedence; RM-148 Decimal,
currency, and unit values; RM-149 tender identity/actions; RM-150 table identity; or RM-151 safe
operation feedback. Accessible metadata performs no repository, filesystem, network, provider,
keyring, AI, or scoring call.

Prefer native Qt widgets/roles. A custom clickable card must retain its existing pointer/key parity
and button-like semantics; decorative glyphs remain out of the focus chain.

## Name, role, description, state, value

- A name is short, localized, stable across theme/DPI, and identifies the action/control.
- Role comes from the actual native control or accepted custom component behavior.
- Description adds consequences, format, disabled reason, freshness/conflict, critical relation,
  retry/cancel policy, or safe correlation only when name/role/state do not already say it.
- State includes enabled/disabled, checked, selected/current, expanded, read/unread, invalid,
  loading/partial/error, running/cancelling/terminal, and exact owner availability.
- Value remains the exact safe semantic value. Decimal/currency/unit, timestamps/timezone, progress,
  table coordinates, and chart selection are never reconstructed from display text.

Names/descriptions are bounded plain text. They contain no HTML, control/bidi override, secret,
credential value, authorization/cookie, database URL, user/absolute path, URL query/fragment, raw
exception/traceback/provider body, or unbounded collection.

## Explicit and implicit naming

An explicit name is required for icon-only tools, custom cards/tiles, tables/charts, status regions,
unlabelled edits, notification badges/items/actions, and controls whose visible text is ambiguous.
Native implicit naming is accepted only when a runtime relation and native Narrator observation
produce the correct name. Placeholder and tooltip alone are not a field label.

Baseline fixes include:

- name `TopBarTenderSearch` by task, not placeholder;
- name/describe theme action with current/next theme state;
- expose notification unread count/value without changing its action ID;
- name `SystemHealthBadge`, workflow filters, Dashboard dynamic state action, and representative
  tables/status regions;
- give sidebar, quick actions, and reusable buttons unique stable control IDs separate from names.

## Labels, buddies, validation, and secrets

Every form field has a visible label and usable relation. `QFormLayout.addRow(str, field)` is an
accepted implicit buddy when runtime asserts `label.buddy() is field`; otherwise `QLabel.setBuddy`
is explicit. Mnemonics, if introduced, are unique within a window/dialog and focus the field.

- Required/optional and input format are text/description, not color or placeholder alone.
- Validation text is associated with the field; submit failure focuses the first invalid field and
  preserves all valid input.
- Hidden optional fields are disabled/removed from Tab and accessibility reading.
- Credential fields announce only purpose and write-only behavior. Stored values are never
  prefilled, named, described, copied, or read back.
- Money/ratio/date fields retain RM-148 unit/currency/timezone text.

## Semantic status catalog

Every state has visible text and accessible state/description; color/icon/animation is supplemental.

| State family | Required text/semantics |
|---|---|
| success | completed/result identity and safe next action |
| warning/partial/stale/conflict | exact distinct label and reason/evidence route |
| error/failure | safe reason and owner-provided retry/recovery |
| loading/running/cancelling | state and bounded/indeterminate progress; cancel request differs from cancelled |
| selected/current/read/unread | explicit state and stable human label |
| disabled/unavailable | native disabled plus safe reason where needed |
| critical stop factor | first semantic section, text+icon, evidence; never demoted by positive score |
| provider/source health | text status and last observation/freshness where supplied |

## Tables, charts, notifications, operations

- RM-150 table headers, row/column, exact selected row, sort, state region, action availability, and
  full semantic cell value are exposed; placeholder states are never fake rows.
- RM-146 chart exposes title/summary, selected series/point, keyboard result, and complete textual
  equivalent. Tooltip information is available without hover and data order/formula is unchanged.
- Notification item reading order is time, severity, read state, title, safe summary, action. The
  action uses typed subject/revision and never row index.
- RM-151 episode text distinguishes queued/running/partial/cancelling/succeeded/failed/timed-out/
  cancelled/closed. Coalescing and terminal non-suppression remain authoritative; updates never
  move focus.

## Destructive actions

Archive/delete/restore/import/recovery/credential deletion semantics include the validated safe
subject label and consequences. The destructive control is not default. Escape/Close cancels.
Revalidation happens in the existing owner after confirmation; stale identity fails closed and
focus returns to the owning container without neighbor selection.

## Security fixture and postconditions

Automated tests project the RM-151 malicious synthetic fixture through names, descriptions,
tooltips, status, dialog text selected for accessibility, notification DTOs, and clipboard-safe
text. The output must exclude fake credentials, Windows/Unix paths, DB URLs, query/fragment,
traceback, HTML/script, bidi/control markers, and raw exception text. A safe opaque correlation ID
may remain. Tests never read live keyring, reports, settings, or customer data.

## Evidence and limitations

Static baseline: 67 name calls, 36 description calls, zero explicit buddies. Isolated shell:
1,008 widgets, 252 non-`NoFocus`, 76 named, 31 described, 194 labels, 25 runtime buddy relations.
These are diagnostic counts only.

Offscreen tests prove property values, relations, state text, keyboard signals, exact identity, and
security postconditions. They do not prove Narrator speech, native role mapping, high-contrast
fidelity, or physical focus visibility. Those require the native matrix; every unobserved cell stays
`NOT_EXECUTED`.
