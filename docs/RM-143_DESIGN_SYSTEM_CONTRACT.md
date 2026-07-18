# RM-143 Corteris Design System v1 contract

Contract version: `corteris-design-v1`

Migration matrix version: `rm143-style-matrix-v1`

Baseline: `67beb8787db5908c9e8dd52f7e17e385aed48814`

## Canonical ownership

`app.ui.theme` is the only design-token and theme contract root. Focused modules may live below
that package, but there is no parallel `design`, `styles`, `theme_v2`, or `new_ui` owner.
`app.ui.widgets` owns reusable Qt presentation components. Existing public imports are retained by
thin re-export.

`ThemeName.DARK == "dark"`, `ThemeName.LIGHT == "light"`, QSettings key `ui/theme`, and
`build_stylesheet()` remain stable. Invalid persisted theme values fail safely to dark in the
existing shell. Design-system version is code-owned and never stored in the database.

## Immutable token root

The public token root contains immutable, uniquely named groups:

- colour: the single `ThemePalette` shape and semantic approved pairs;
- typography: `FontToken`, `FontWeight`, semantic scale, local Windows fallback chain;
- spacing: zero, xs, s, m, l, xl, xxl and named layout roles;
- sizing: compact/standard/large controls and xs/s/m/l icons;
- border/radius: default/focus/emphasis widths and small/medium/large/pill radii;
- elevation: none/low/medium/high shadow specifications;
- motion: instant/fast/standard/slow/loading-frame and bounded feedback durations;
- layout: page margin, section gap, card padding, form/dialog/table spacing only. Dashboard
  breakpoint behavior and the new shell grid remain outside RM-143.

Token groups reject invalid, negative, non-finite, duplicate, or non-monotonic values at contract
construction/test time. Consumers use semantic names rather than indexing numeric tuples.

## Colour and contrast

- `ThemePalette` remains the only palette dataclass; dark/light use the identical field set.
- Colour values are `#RRGGBB` or `#RRGGBBAA`; semantic transparency is one exported constant.
- Semantic roles cover brand, surfaces, text, border/focus, interaction, status, overlay/shadow,
  scrollbar and future chart slots.
- `SemanticTone`/`SemanticColor` selects a presentation pair; it does not calculate domain state.
- Approved pairs are declared by stable IDs and tested for both themes.
- Relative luminance uses the W3C sRGB transfer function. Contrast ratio is
  `(lighter + 0.05) / (darker + 0.05)`.
- Normal text pairs target 4.5:1; large/decorative or non-text focus/selection pairs use their
  explicitly documented threshold. Exceptions require exact pair ID, measured ratio, rationale,
  owner and target RM; no broad theme exception exists.
- RM-143 verifies component pairs only and does not claim application-wide WCAG compliance.

## Typography

- Stable names: display, H1–H3, body L/M/S, caption, button, code.
- Primary UI family is Segoe UI with repository-defined local fallbacks; code uses a local
  monospace chain headed by Consolas. No font download occurs.
- `FontToken.size` is a Qt/QSS point size. Line height is metadata for layout/documentation because
  Qt Style Sheets do not offer a reliable CSS line-height contract.
- Scaling requires a positive finite factor and returns a new immutable token.
- Foundation components contain no raw font size or weight.

## Icon system

- `IconId` is a closed stable semantic identity and never a filename or emoji.
- One `IconRegistry` maps required IDs to repository-owned SVG resources and a deterministic text
  fallback. `IconProvider` returns `QIcon`/pixmap presentation without network or user data.
- Required categories include navigation, topbar, common actions, state feedback, and neutral
  document/settings/history/schedule identities.
- Unknown IDs and missing/corrupt resources resolve to the generic fallback without raising to UI
  code or exposing a private/absolute path.
- Icon-only controls require a non-empty accessible name and tooltip. Meaning is also present as
  visible/accessible text where status or business meaning is involved.
- Route IDs, route order, hierarchy, availability, aliases and context do not change. Existing
  `RouteSpec.icon` remains a string compatibility field but stores/resolves a semantic ID through
  the one registry; no second navigation metadata map is created.
- Assets are local SVGs under the existing packaged `assets/` root, listed in a provenance file,
  and contain no script, external URL/reference, or runtime download.

## Global and local QSS

`build_stylesheet()` is the sole application/global QSS builder. It uses tokens for application,
surfaces, buttons/tool buttons, editable controls, combo/spin/check/radio, tables/headers,
tabs/menus/tooltips, dialog/status bar, scrollbars and normal/hover/pressed/focus/disabled/
checked/selected/error states.

Local QSS is allowed only when:

1. it is constructed from design tokens;
2. the exact file/symbol/site is registered in the migration matrix;
3. it owns component-specific selectors that cannot be expressed safely by global QSS; and
4. it contains no unregistered raw colour/font/foundation metric.

Static guards use exact paths/symbols and fail on new sites/literals. Broad globs are forbidden.

## Button contract

The existing `CorterisButton` family remains canonical.

- variants: primary, secondary, outline, ghost, danger, icon-only;
- sizes: small, medium, large;
- states: normal, hover, pressed, focused, disabled, loading, checked/selected where checkable;
- existing public subclasses, object name, Qt properties and `setText()` compatibility remain;
- loading keeps an accessible text state, disables activation, uses the motion token, stops its
  timer on exit/destruction, and does not duplicate timers during theme switching;
- icon-only construction requires `accessible_name`; semantic icon input is preferred while the
  legacy text fallback remains accepted during migration;
- default/cancel Qt semantics are preserved and not inferred from colour.

## Card contract

The existing `Card`/`KpiCard` family remains canonical.

- tones: default, info, success, warning, danger, neutral;
- density: compact/standard; shadow: none/low default;
- states: static, clickable normal/hover/pressed/focus/disabled and theme switching;
- clickable cards use strong focus and activate on Enter/Return/Space; their accessible name is
  non-empty;
- one effect instance is reused/replaced deterministically and does not grow on repeated theme
  switching;
- `clicked`, public properties, labels/object names and Dashboard consumers remain compatible;
- `KpiCard` renders provided values only and never calculates a KPI or recommendation.

## Status, data-state, and form contracts

- A status badge/banner accepts semantic tone, label, details and optional action. It never derives
  business status from colour or text.
- Existing Dashboard `DataState` remains the only state taxonomy and covers ready, loading, empty,
  partial/stale, error and disabled/unavailable. Each non-ready state has stable identity, title,
  message, semantic icon/tone and optional action.
- No raw exception is rendered by a design primitive and no retry/business logic lives in it.
- `FormField`/`FormSection` own label/help/required/error/read-only/disabled/loading presentation
  and spacing only. Dialog/service owners retain validation and persistence. Full buddies, global
  focus order, screen-reader and DPI acceptance remain RM-152.
- Dialog/table tokens provide visual foundations only; models, delegates, filtering, selection,
  pagination, workflow and lifecycle remain in their current owners/RM-144/RM-150/RM-151.

## Theme propagation and lifecycle

- Global QSS is generated once per explicit shell switch.
- Reusable components expose one compatible `set_theme`/`apply_theme` seam and keep no second
  global theme manager.
- Default construction is dark for compatibility; production composition supplies the current
  theme before display.
- Switching theme preserves route, page, data, filter and selection state and performs no file,
  network, DB or keyring load.
- Repeated switch/destroy cycles do not grow timers, graphics effects, registries or widgets.

## Component gallery

The gallery is a deterministic offline dev/test harness, not a production route. Its versioned
schema creates all button variants/sizes/states, cards/tones, status/data/form states, icons and
fallbacks under dark/light themes with fixed synthetic Russian/long text. It supports construct,
switch and destroy smoke. It uses no DB, user records, keyring, network or screenshot golden; RM-154
owns golden testing.

## Resource/build/security contract

- Reuse `PathManager`/`ResourceManager` and the existing PyInstaller `assets/` collection.
- Resource paths are relative, validated and repository-owned. No absolute/private path reaches UI.
- Build/frozen tests require the icon directory, provenance manifest, every registered file and safe
  missing fallback.
- SVG validation rejects script, event attributes and external references.
- The design system performs no socket, credential, DB or user-data operation.

## Compatibility and exclusions

Mandatory green guards:

- all RM-142 route IDs, hierarchy, primary order, availability, aliases, exact tender/workflow
  context, history and focus-origin behavior;
- one `ModernMainWindow`, one `DashboardLayout`, one stack and one route registry;
- `ui/theme`, public imports, object names, signals, QAction identities and shortcuts;
- RM-127/RM-128/RM-140 composition/search/offline/shutdown behavior;
- existing Dashboard and workflow construction;
- RM-107 score/recommendation/hard exclusions and absolute critical stop-factor priority.

Excluded: new shell/page extraction, charts/analytics, table model migration, background episode
architecture, full DPI/accessibility/WCAG verdict, screenshot goldens, DB migration, new dependency,
and any AI/search/business ownership change.
