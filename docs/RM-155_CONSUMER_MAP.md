# RM-155 consumer map

## Removable island

| Candidate | Production | Tests | History/public | Frozen/settings/data | Migration |
|---|---|---|---|---|---|
| old `app.ui.main_window` module | none | RM-127, 131--133, 142, 144 | retained explicitly only through RM-155 | none | import canonical page; remove wrapper-only assertions |
| `quotes_page` | bootstrap fallback | RM-142/144 | temporary through RM-155 | none | use `workflow_page` |
| `estimates_page` | bootstrap fallback | RM-142/144 | temporary through RM-155 | none | use `workflow_page` |
| compatibility catalog search method | none | one RM-127 test | superseded by RM-128 unified search | none | remove obsolete assertion |

The bootstrap support-bundle lookup is migrated first and tested with only `workflow_page`.
All tests then import `TenderWorkspacePage` and the three live notice constants from the canonical
page module. Removal is permitted only after repository-wide AST/string checks return no old
imports or attributes.

## Retained boundaries

| Boundary | Why retained | Guard |
|---|---|---|
| route aliases and string page keys | Sidebar/object-name and prior deep-link compatibility | RM-142 registry/shell tests |
| action/shortcut/object names | QAction consumers, accessibility UIA, QSS and visual fixtures | RM-127/140/152/154 tests |
| `ui/theme` | persisted user preference with safe fallback | theme/native/visual tests |
| chart/analytics/financial/detail/table adapters | accepted typed owner boundaries, not duplicate engines | RM-146--150 suites and frozen self-test |
| notification legacy adapter | persisted schema-v1 compatibility and safe redaction | RM-151 tests |
| RM-152 exceptions | owner-approved truthful residual evidence | strict validator |
| RM-153/RM-154 harnesses | required performance/visual gates, absent from product graph | build contract/spec/CI |

## Search protocol

Final acceptance repeats `rg`, AST import parsing, bootstrap runtime composition, test collection,
route registry resolution, action/shortcut/object-name catalogs, PyInstaller spec inspection,
frozen self-test, settings/schema search and `git log --follow` evidence. An empty `rg` alone is
not accepted as proof.
