# RM-155 feature acceptance evidence

## Scope and exact identities

- Canonical production baseline: `119409b110a826f179355c914890bb8171af3e06`.
- Audit-first package: `d0d8ef3`.
- Characterization contract: `5e57b1b`.
- Expected-red retirement contract: `3aea67a`.
- Controlled compatibility retirement: `0679f77`.
- Permanent ownership and cross-stage guards: `10e21d7`.
- Stale source-consumer migration: `9a5d49e`.
- Feature head, PR, merge SHA and exact merge-SHA jobs: pending feature publication.

RM-155 closes only `UI-141-017`. It proves the RM-142--RM-154 redesign as one production
composition and retires only the audited, consumer-free compatibility island. RM-156 is not
started. RM-155 remains `IN PROGRESS` until the feature merge, exact merge-SHA Quality Gate and
separate docs-only closeout are complete.

## Entry gate and audit-first evidence

RM-154 entered through feature PR #116, merge `40f0e327d0d485b93e93f39bab1d838e584b8914`,
successful exact-merge Quality Gate run `29823579968`, and docs-only closeout PR #117 at canonical
main `119409b110a826f179355c914890bb8171af3e06`. The Python 3.12 canonical visual leg passed all
14 strict cases. Canonical status documents name RM-155 as the sole active stage.

Before production edits, the committed audit package recorded compatibility inventory, consumer
map, runtime composition, settings/action/route matrix, public imports, retirement decisions,
J01--J16, cross-stage gates, implementation and rollback. The inventory contains 32 candidates:

- 9 `REMOVE` decisions;
- 2 `MIGRATE`, followed by their approved removal;
- 21 `KEEP` decisions;
- 0 `DEPRECATE` and 0 `BLOCKED` decisions.

Each item names its origin, exact runtime/import/test/history/frozen/settings/public consumer
evidence, replacement, rollback and owner. No item was removed because of a legacy-looking name
alone.

## Controlled retirement and production composition

The retired island consists of the obsolete `app.ui.main_window` wrapper and its re-exports,
`ModernMainWindow.quotes_page`, `ModernMainWindow.estimates_page`, the bootstrap fallbacks for
those aliases, and `TenderWorkspacePage.apply_compatibility_search_text`. Tests and the one stale
source-inspection consumer now import the canonical tender page or use `workflow_page`.

`ModernMainWindow`, its typed workspace router, `TenderWorkspacePage`, `BusinessWorkflowPage`,
Dashboard, analytics and their existing controllers/repositories remain the sole production
owners. The bootstrap composition uses `workflow_page` only. The permanent RM-155 checker rejects
the retired module, symbols, fallback lookups and source-reading consumers, and is an explicit
Windows Quality Gate step.

The supported route aliases, `RouteId.FUTURE_ANALYTICS`, `ui/theme`, action/shortcut/object names,
chart evidence type alias, persisted notification/financial adapters, `legacy_orm` identity,
table adapters, RM-152 exceptions, RM-153 harness and RM-154 visual tooling remain owned and
tested. They are retained contracts, not duplicate production owners.

## Journeys and cross-stage acceptance

The RM-155 journey/cross-stage suites cover J01--J16 and the accepted contracts of RM-142 through
RM-154: navigation and deep links; canonical composition and close; Dashboard, charts, analytics,
financial workflow, tender identity/details, tables, operation truth, accessibility, performance
and visual governance. The focused RM-155 guard suite passed 18 tests; the neighboring RM-127--154
contour passed 840 tests. No journey has a new blocker.

Native evidence remains truthful at the accepted RM-152 boundary: 0 `PASS`, 4 `BLOCKED` and 29
`NOT_EXECUTED`, with the approved named exceptions. RM-155 neither promotes those cells nor treats
offscreen/frozen evidence as native UIA certification.

## Deterministic decision, data and security invariants

The RM-147 decision invariance, participation policy/service, collector stop-factor and scoring
contour passed 37 tests. Score, recommendation, action, evidence, confidence, Decimal values,
identity and absolute critical stop-factor priority are unchanged. AI output has no new decision
authority.

No dependency, database/settings schema, migration, telemetry, persistent cache or lifecycle
owner was added. Existing persisted notification, finance, identity and theme contracts are kept.
Repository secret scanning passed, offline provider tests passed, and `pip-audit --skip-editable`
reported no known vulnerability. Fixtures use synthetic/temporary data and do not read credentials,
production data or the network.

## Performance and resource evidence

The committed RM-153 performance contract tests passed. A fresh 20-sample comparable run on the
feature head used Python 3.12.7, PySide6 6.11.1, offscreen Qt, two warmups and the canonical fixture
sizes. All p95 guards passed: shell construction 563.806 ms, first paint 156.274 ms, shutdown
8.696 ms, page switch 29.832 ms, Dashboard update 20.934 ms, theme switch 162.589 ms, table filter
116.549 ms and chart update 41.118 ms. A 25-cycle resource run showed zero growth for QObject,
QThread, QTimer, active QTimer and Python-thread owners, with traced memory below the accepted
limits.

Two earlier loaded-host runs exceeded only the 12 ms shutdown p95 despite an approximately 8 ms
median. A controlled same-session A/B established environment noise rather than an RM-155
regression: exact baseline `119409b` measured 13.507 ms, then feature head measured 8.696 ms. The
shutdown implementation is byte-unchanged from the baseline; no out-of-scope optimization or
budget relaxation was introduced.

## Visual, build and frozen evidence

Local RM-154 comparison correctly produced a typed renderer-profile block because the local
Windows/Python/font fingerprint differs from the canonical CI renderer; it was not converted to a
pixel pass. The authoritative final main RM-154 run remains strict 14/14 `PASS`, and the unchanged
canonical comparison stays in the Python 3.12 Quality Gate leg.

An actual clean PyInstaller one-file build produced `dist/CorterisTenderAI.exe`, 83,683,131 bytes,
SHA-256 `044B35A3D8D73132A603073FBB0F8456010950B19CB5696C2EFBB8D7BC41F7A0`.
The hidden, isolated frozen self-test reported `success=true`, `frozen=true` and passed all nine
dependency/resource/writable-directory/SSL/database/provider/archive/analytics/chart checks. The
static build/frozen/RM-155 cross-stage contour passed 11 tests.

## Local validation ledger

- unchanged baseline full suite: `2378 passed, 2 warnings`;
- expected red: exactly `6 failed, 4 passed`, all intended missing retirement boundaries;
- post-retirement focused contour: `48 passed`;
- final RM-155 guards: `18 passed`;
- neighboring RM-127--154 contour: `840 passed, 2 warnings`;
- final full suite: `2411 passed, 2 warnings in 207.24s`;
- accepted warnings: the existing openpyxl unsupported-extension and conditional-formatting
  fixture warnings;
- Ruff check: PASS; Ruff format: `794 files already formatted`;
- required mypy: `Success: no issues found in 20 source files`;
- offline credential isolation: `2 passed`; migration/schema: `5 passed`;
- bootstrap/RM-155 composition: `2 passed`; build/frozen/cross-stage: `11 passed`;
- RM-107 decision integrity: `37 passed`; RM-153 contract/theme: `9 passed`;
- public import smoke: `DashboardController`; dependency audit: no known vulnerabilities;
- design-system audit: matrix 47, styles 44, violations 0;
- RM-151 operation boundary and RM-152 strict accessibility guards: PASS.

## GitHub publication gate

The feature PR must record its final head, merge SHA, successful Windows Python 3.12/3.13 jobs,
the Python 3.12 strict RM-154 visual comparison and dependency audit. Only an exact merge-SHA push
run may authorize the separate docs-only closeout. This section is intentionally pending until
that evidence exists; local green evidence cannot substitute for it.

## Rollback and residuals

Rollback is a revert of the future feature merge. The old wrapper, exact-class re-exports,
same-object page aliases, bootstrap fallbacks and three-line search shim can be restored without a
second business owner or any data downgrade. No database, settings or user-data rollback is
required. Retained compatibility is enumerated in `RM-155_COMPATIBILITY_INVENTORY.md` with owner
and reason; there are no deprecated or blocked residuals.
