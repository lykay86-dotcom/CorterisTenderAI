# RM-155 final cleanup audit

## Verdict

The RM-155 entry gate is open at canonical `main` SHA
`119409b110a826f179355c914890bb8171af3e06`. RM-154 is `DONE`, RM-155 is the sole
`IN PROGRESS` stage, and RM-156--RM-200 remain `PLANNED`. The RM-154 feature and closeout gates
are green; the final `main` gate is run `29824853432`.

The audit finds a narrow removable UI compatibility island and no permission for domain or data
cleanup. The removable island is `app.ui.main_window`, the same-object `quotes_page` and
`estimates_page` attributes, their bootstrap lookup fallbacks, and
`TenderWorkspacePage.apply_compatibility_search_text`. Canonical replacements already exist and
all current consumers are repository tests or internal fallbacks that can be migrated first.

Route aliases, action/shortcut/object names, `ui/theme`, data/schema compatibility, notification
adapters, chart/analytics/financial/detail/table boundaries, RM-152 exceptions, RM-153 benchmark
harnesses and RM-154 visual artifacts are retained. They are accepted contracts, persisted
identifiers, future-stage admission, or test/release evidence rather than duplicate production
owners.

## Evidence and method

- Dedicated branch/worktree: `refactor/rm-155-redesign-closeout`, `.worktrees/rm155`.
- Canonical sources read in full: status, roadmap, Definition of Done, roadmap history, RM-141
  audit/inventory/owner/journeys/handoff, RM-142--154 acceptance and relevant contracts, build and
  frozen specifications.
- Independent evidence: `rg`, import and string consumers, bootstrap trace, route registry,
  Qt actions/shortcuts/object names, Git blame/log, tests, PyInstaller spec, frozen self-test,
  settings/schema contracts and documentation.
- No network/provider/keyring/user database was used by the audit. Dependency audit was the only
  read-only network check.

## Baseline ledger

| Check | Exact result |
|---|---|
| full pytest | `2378 passed, 2 warnings in 234.66s` |
| secret scan | passed |
| Ruff check | passed |
| Ruff format | `788 files already formatted` |
| canonical mypy | success, 20 files |
| offline smoke | `2 passed in 23.12s` |
| migration/schema smoke | `5 passed in 11.41s` |
| composition smoke | `1 passed in 0.77s` |
| build/frozen smoke | `8 passed in 14.31s` |
| public controller import | `DashboardController` |
| dependency audit | no known vulnerabilities; editable project skipped |
| local RM-154 comparison | typed block: renderer fields differ |

The two warnings are the accepted RM-132/openpyxl unsupported-extension and conditional-formatting
warnings. Local visual blocking is expected because the workstation is not the canonical
`windows-latest-python312` renderer. Authoritative exact-main CI has strict `14/14 PASS`.

## Owner conclusions

- Production root: `app.bootstrap.bootstrap` creates one `QApplication` and one
  `ModernMainWindow`.
- Navigation: one `DEFAULT_ROUTE_REGISTRY`, one `DashboardLayout`, one `QStackedWidget`.
- Pages: one Dashboard, tender workspace, workflow and analytics instance.
- Compatibility `MainWindow` is not imported by production or frozen entry paths.
- `quotes_page`/`estimates_page` are same-object aliases only; production bootstrap is their sole
  fallback consumer and already prefers `workflow_page`.
- No cleanup candidate owns scoring, recommendation, critical stop-factor, AI, repository,
  migration, network, credential or transaction logic.

## Stop conditions

Stop removal if an external/public consumer is discovered, a persisted identifier requires the
candidate, frozen collection changes, a route/action bypass appears, visual drift is unexplained,
or decision parity changes. A database migration is neither required nor authorized.
