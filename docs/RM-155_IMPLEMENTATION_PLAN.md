# RM-155 implementation plan

1. Commit this eleven-document audit package without application/test changes.
2. Add characterization and RM-155 guards for current consumers, one production composition,
   canonical public imports, route/action/settings/object-name retention, frozen exclusion and
   inventory completeness.
3. Record expected red caused only by intentionally absent retirement state: old module remains,
   aliases remain, bootstrap still accepts them, and obsolete method remains.
4. Migrate tests and bootstrap support-bundle lookup to `workflow_page` and canonical page imports.
5. Remove `quotes_page`, `estimates_page`, `apply_compatibility_search_text`, and finally
   `app/ui/main_window.py`; repeat AST/string/import and frozen checks after each island.
6. Run focused and neighboring RM-127/131--154, J01--J16, decision integrity, offline/security,
   accessibility, performance/resource, build/frozen and full gates.
7. Do not change the RM-154 baseline locally. CI on canonical Python 3.12 performs strict compare.
8. Publish a feature PR, require PR-head Windows Python 3.12/3.13 success, merge, then require the
   exact merge-SHA gate.
9. Only after that, create a separate docs-only closeout marking RM-155 `DONE`; do not implement
   or activate RM-156 application work in this package.

Commits remain reviewable: audit, characterization, expected red, consumer migration, controlled
removal, acceptance. No bulk opportunistic refactor is permitted.
