# RM-143 design-system audit

## Verdict

RM-143 can close `UI-141-003` by extending the existing `app.ui.theme` and reusable widget
owners. A second theme package, shell, router, service, repository, database change, runtime
dependency, or network-delivered font/icon is neither necessary nor allowed.

The post-RM-142 inventory still contains exactly 45 local `setStyleSheet()` calls. Most are already
palette-backed, but they retain untyped spacing/radius/font metrics and have no complete exception
registry. Two raw status colours remain in rich text, while Sidebar, TopBar, route metadata and
several state widgets still use Unicode/emoji as icon identity. `CorterisButton`, `Card`, and
`KpiCard` have no direct test owners. The current build does package the repository-owned `assets/`
tree, so a bounded local SVG registry can reuse the existing `PathManager`/`ResourceManager`
pipeline and PyInstaller spec.

`DB/schema/migration: not required`. `Runtime dependency: not required`.

## Entry gate and baseline

- Date/environment: 2026-07-18, Windows, Python 3.12.7, Qt offscreen.
- Canonical closeout SHA, local `main`, and fetched `origin/main`:
  `67beb8787db5908c9e8dd52f7e17e385aed48814`.
- Dedicated worktree/branch: `.worktrees/rm143`, `feat/rm-143-design-system`.
- Root-only user files `.agents/` and `skills-lock.json` are not present in this worktree and remain
  untouched.
- RM-142 feature PR #92 is merged as
  `246734d2f3b700392c6682c7bcfb5d6ab1469ec5`; closeout PR #93 is merged as the baseline above.
- Exact feature merge-SHA run `29659317641` is `success` for
  `quality-gate (Python 3.12)` and `quality-gate (Python 3.13)`, including dependency audit.
- Canonical documents mark RM-142 `DONE`, RM-143 as the sole `IN PROGRESS` stage, and
  RM-144–RM-200 `PLANNED`; the RM-142 → RM-143 handoff is recorded.
- No RM-144+ application implementation exists on `main`; the feature worktree starts at the exact
  closeout SHA.
- Full local entry baseline:
  `1983 passed, 2 warnings in 170.15s`; the warnings are the accepted openpyxl extension warnings
  in `test_rm132_legacy_credentials_handoff.py`.

## Reproducible inventory

Command:

```powershell
python -m scripts.audit_ui_inventory --format summary
```

Post-RM-142 result:

| Measure | Result |
|---|---:|
| `app/ui` Python modules | 72 |
| Lines in `app/ui` | 30,174 |
| UI/PySide6 test modules | 105 |
| Local `setStyleSheet` calls | 45 |
| Literal colours outside theme | `#2e8b57`, `#b22222` |
| Fixed / minimum / maximum dimension calls | 14 / 31 / 6 |
| `QTableWidget` / `QTableView` construction sites | 30 / 2 |
| `QTimer` / `QThread` construction sites | 6 / 1 |
| Static accessible name / description / buddy calls | 30 / 13 / 0 |
| Repository-owned image/icon/font/Qt resources under `app/ui` | 0 |

RM-142 added four navigation modules, so the module and line totals increased from RM-141. The
style count and two raw colours are unchanged.

## Existing owners

| Concern | Current owner | Audit result |
|---|---|---|
| theme identity/persistence | `ThemeName`, `ModernMainWindow`, QSettings `ui/theme` | retain stable `dark`/`light` values and safe dark fallback |
| palette | frozen `ThemePalette`, `DARK_PALETTE`, `LIGHT_PALETTE` | retain one dataclass; add missing semantic/interaction roles only here |
| typography | `FontToken`, `FontWeight`, `Typography` | retain and formalize fallback/scale semantics |
| global QSS | `build_stylesheet()` | retain as the only application stylesheet builder |
| buttons | `CorterisButton` family | retain public classes/object name; replace duplicate metric maps with tokens |
| cards | `Card`, `KpiCard` | retain public classes/signals/object names; fix focus/keyboard/effect lifecycle |
| data state | Dashboard `DataState` / `DataStatePanel` | extend the existing taxonomy; do not create a second state model |
| status feedback | `DashboardStatusBanner`, `SystemHealthBadge`, local status labels | extract a thin reusable presentation contract without notification ownership |
| forms | dialog-owned labels/controls | add a presentation-only field/section primitive; validation remains in owners |
| navigation | `DEFAULT_ROUTE_REGISTRY`, `DashboardLayout` | preserve IDs/order/availability/aliases; adapt icon presentation only |
| resources | `PathManager`, `ResourceManager`, `installer/corteris_tender_ai.spec` | reuse `assets/`; no new resource root or runtime download |

## Palette and contrast findings

- Dark and light palettes are instances of the same frozen dataclass and therefore have structural
  parity, but parity and colour-format validation lack direct RM-owned tests.
- Semantic status pairs exist for info/success/warning/danger/neutral. Interactive disabled,
  selection, overlay, scrollbar and chart slots also exist, but approved foreground/background
  pairs are not declared as a versioned contract.
- `contrast_text()` uses an 8-bit perceived-brightness heuristic. It is not an sRGB
  relative-luminance/contrast calculation and cannot be the RM-143 acceptance utility.
- The only raw Python UI colours outside the theme owner are database-health rich-text values in
  `TenderWorkspacePage._update_db_status`. The exception path also interpolates raw exception text;
  RM-143 will remove the presentation literals and escape the text without expanding RM-151 error
  architecture.
- `transparent` is repeated as a QSS literal and needs one code-owned semantic constant.

## Typography, spacing, sizing, elevation, and motion findings

- Typography already covers display, H1–H3, body L/M/S, caption, button, and code with Segoe UI
  and Consolas, but fallback families and QSS point-size policy are implicit.
- Button size metrics are duplicated between `_apply_size()` and `_apply_theme()`.
- Card, state, badge, form, and global QSS metrics use local numeric radii/padding/heights.
- `QGraphicsDropShadowEffect` is recreated by `Card._apply_shadow()` on every theme/state apply.
- Button loading uses a hard-coded 160 ms timer. Dashboard banner timeouts are caller literals.
- Dashboard breakpoints are an established page-specific contract and are deferred to RM-145;
  RM-143 must not replace them with a shell grid.

## Icon and resource findings

- Route icon metadata currently stores `🏠`, `🔎`, and `📄`; Sidebar renders the string directly.
- TopBar uses `🤖`, `🔔`, `🌙`, and `👤`; theme switching writes `☀`/`🌙` directly.
- State widgets use small glyphs (`✓`, `×`, `…`, `!`, `—`) as display fallback. Their text labels
  already carry meaning and can remain deterministic fallbacks after semantic IDs are introduced.
- `assets/` contains only two logo PNGs. There is no icon registry, provenance manifest, or direct
  frozen icon test.
- The PyInstaller spec includes the whole optional `assets/` tree. A repository-owned SVG set with
  a manifest/license note is therefore compatible with source and one-file builds.

## Component findings

### Buttons

- Existing variants: primary, secondary, outline, ghost, danger; `IconButton` is the icon-only
  form. Existing sizes: small, medium, large.
- Object name `CorterisButton`, public subclasses, `setText`, Qt properties, and loading behavior
  are compatibility inputs.
- Missing: explicit icon-only variant identity, semantic icon input, accessible-name enforcement
  at the base contract, deterministic destruction test, checked/default/cancel styling, and direct
  dark/light test ownership.

### Cards

- Existing tones: default/info/success/warning/danger; compact density and click signal exist.
- Clickable cards do not set a focus policy or implement Enter/Space activation.
- Theme/state application recreates the shadow effect. Disabled/focus styling is absent.
- `KpiCard` only renders supplied strings and does not calculate KPI values; this invariant must be
  retained.

### Status/data/form

- Dashboard `DataState` provides ready/loading/empty/error/partial; RM-143 will extend it with
  disabled/unavailable while retaining existing factories and owners.
- `DashboardStatusBanner` and `SystemHealthBadge` provide semantic text plus colour. They can back a
  reusable badge/banner presentation API without moving status calculation from their domain owner.
- Form labels, help, validation and action spacing are repeated across dialogs. A thin
  `FormField`/`FormSection` visual primitive can centralize presentation while leaving validation,
  persistence, focus order, and label-buddy completion to current owners/RM-152.

## Local stylesheet policy

All 45 calls are registered in `RM-143_COMPONENT_MIGRATION_MATRIX.md`. RM-143 does not impose
mechanical zero-local-QSS. Foundation/reusable/status/form sites migrate now; existing page/dialog
composition that is already palette-backed is retained under an exact exception or deferred to its
own redesign RM. Broad `app/ui/**` exceptions are forbidden.

## Test and compatibility findings

- No direct tests currently import `CorterisButton`, `Card`, or `KpiCard`.
- Existing theme tests cover `SystemHealthBadge` and backup-center presentation only.
- Dashboard state/banner/component tests provide useful characterization but no shared v1 contract.
- RM-127/RM-128/RM-142 tests guard one `QMainWindow`, one stack, public tender workspace,
  navigation identities, exact tender IDs, search delegation, and action/object names.
- Build tests verify template/certifi collection but do not require icon assets or registry import;
  frozen self-test only reports whether `assets/` exists.

## Security, privacy, and stop conditions

- Design-system resolution must be pure/local and must not touch DB, keyring, settings other than
  existing shell theme persistence, or network.
- Unknown icon IDs and missing files return a safe generic icon/fallback without an absolute path or
  raw exception.
- SVGs must be repository-owned, script/external-reference free, and listed in a provenance file.
- Gallery fixtures must be synthetic and offline.
- No P0/P1 issue, asset-license blocker, overlapping user change, new dependency need, or RM-144+
  implementation was found. The application implementation gate is open after this four-document
  package is committed.

## Audit decision

**ACCEPTED FOR DOCS-FIRST COMMIT.** The approved implementation extends the current owners, keeps
all RM-142 navigation and mature workflow contracts, introduces no database/dependency change, and
closes only `UI-141-003`.
