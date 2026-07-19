# RM-146 implementation plan

## Scope and sequencing

Close only `UI-141-007` from exact RM-145 closeout baseline
`cf2bc8f080ad006131ab501863a424dcede30a1c`. Preserve RM-142 navigation, RM-143 design ownership,
RM-144 shell/lifecycle, RM-145 KPI/evidence/drill-down semantics, repository owners, deterministic
score/recommendation logic, and critical stop-factor priority. RM-147 tender analytics and RM-148
financial analytics remain excluded.

## Phase 1 — audit-first documentation gate

Commit only the six required pre-code documents: technology audit, chart contract, interaction and
accessibility contract, export artifact contract, performance/DPI plan, and this plan. Confirm no
`app/`, tests, dependency, build, or canonical roadmap file changed.

Intent: `docs(rm-146): audit accessible chart contracts`.

Stop if the exact RM-145 gate/status evidence changes, licensing requires a new unapproved surface,
or one package cannot own the complete presentation contract. Rollback: revert this docs commit.

## Phase 2 — passing characterization

Add focused passing tests for current dependency/build absence, RM-143 chart token parity, reusable
RM-145 evidence, QWidget shell conventions, deterministic owner boundaries, and no current chart
consumer. Characterization describes the accepted baseline and must pass before expected-red.

Intent: `test(rm-146): characterize chart presentation baseline`.

Stop if characterization discovers an existing chart owner/framework or incompatible evidence
model. Rollback: revert the characterization commit.

## Phase 3 — expected-red contracts

Add focused tests for absent immutable public model, validation, normalized plan, state semantics,
bar/line and missing gaps, exact data export, bounded visual export, table equivalence, keyboard and
mouse selection, tooltip escaping, resize/DPI, dark/light parity, limits, and public import. Record
the exact failures before production implementation.

Intent: `test(rm-146): add expected-red chart contracts`.

Every red must map to a documented missing RM-146 behavior. Stop on a failure that requires a real
tender/financial aggregation, provider, schema, route, second theme owner, or changed business
decision. Rollback: revert only this test commit.

## Phase 4 — immutable model and normalized plan

Create the cohesive `app.ui.charts` package with frozen contracts, stable validation, RM-145
evidence reuse, deterministic formatting/ticks, semantic states, bounded limits, and normalized
bar/line render plans. Add no dependency. Make pure contract/normalizer tests green first.

Intent: `feat(rm-146): define immutable chart render plans`.

Stop on float business values, naive time, lost IDs/order/provenance, hidden aggregation/sampling,
or duplicate contract/normalizer ownership. Rollback: revert this commit; no data migration exists.

## Phase 5 — painter, export, and textual equivalent

Implement one shared QPainter routine for canvas, QImage PNG, and QSvgGenerator SVG. Implement
deterministic JSON/CSV and a complete Qt table model. Use only RM-143 chart/semantic/focus tokens;
do not add local stylesheet ownership or a second renderer.

Intent: `feat(rm-146): render and export accessible charts`.

Stop on unsafe SVG/CSV, unbounded pixels, divergent screen/export plan, non-exact data output,
incomplete table, or frozen-build resource/dependency expansion. Rollback: revert this commit.

## Phase 6 — widget interaction and accessibility

Implement the focusable canvas/composite widget, exact closed key map, bounded mouse hit testing,
typed selection, safe tooltip equivalent, visible semantic states, table toggle/focus, selection
retention by stable ID, theme change, and resize behavior. The widget emits selection only; callers
retain navigation/business-action ownership.

Intent: `feat(rm-146): add keyboard chart interaction`.

Stop if keyboard and mouse resolve different IDs, a state relies on colour alone, the table differs
from export/source order, or lifecycle work escapes widget ownership. Rollback: revert this commit.

## Phase 7 — measured acceptance and frozen evidence

Measure 0/1/10/100/1,000/10,000, resize, scale, light/dark, JSON/CSV/PNG/SVG, memory/artifact bounds,
and explicit `TOO_LARGE`. Run focused RM-146 plus neighboring RM-141–145, shell, lifecycle,
navigation, Dashboard, design, offline, schema/migration, public import, release/build/frozen, and
resource selections. Run full pytest, Ruff check/format, mypy, secrets, dependency audit, design/UI
audits, `git diff --check`, and the Windows Quality Gate equivalent.

Create `docs/RM-146_ACCEPTANCE.md` only from exact results. Mandatory searches prove one public
chart package/contract/normalizer/painter/table/exporter, no external chart framework, no business
aggregation/rounding, no real RM-147/148 consumer, no provider/network/schema/dependency, and no
literal colour or hidden sampling.

Intent: `test(rm-146): prove accessible chart acceptance`.

Stop on any unexplained regression, new warning, secret/vulnerability, duplicate owner, artifact
leak, packaging failure, or unmeasured native claim. Rollback: revert acceptance changes until the
evidence is truthful.

## Phase 8 — feature PR, merge gate, and closeout

Push/PR/merge require explicit user authorization. The feature PR head gate must pass on the exact
feature SHA. After authorized merge, verify the exact merge-SHA Windows Python 3.12/3.13 gate, then
create a separate docs-only closeout from that verified `origin/main`. Only closeout may mark
RM-146 `DONE`, close `UI-141-007`, and activate RM-147 as the sole `IN PROGRESS` stage.

No push, PR, merge, release, canonical status transition, or start of RM-147 is implicit.
