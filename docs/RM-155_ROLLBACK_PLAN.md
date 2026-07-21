# RM-155 rollback plan

## Source rollback

Revert the RM-155 feature commits in reverse order. The narrow restoration operations are:

1. restore `app/ui/main_window.py` from baseline `119409b`;
2. restore the two same-object attributes in `ModernMainWindow.__init__`;
3. restore bootstrap lookup order `workflow_page`, `quotes_page`, `estimates_page`;
4. restore `apply_compatibility_search_text` if a proven consumer requires it;
5. restore migrated test imports/assertions only with the corresponding source boundary.

## Data and settings

No database, schema, migration, dependency, route value, action/shortcut/object name, setting,
credential, user file or visual baseline changes are planned. Therefore rollback needs no data
conversion, settings cleanup, keyring action or downgrade migration.

## Stop and recovery

Stop before merge on a consumer/import/frozen failure, route/action parity change, owner growth,
unsafe feedback, visual drift, new warning/vulnerability or deterministic-decision mismatch.
Restore the smallest candidate boundary, reproduce with the exact failing fixture, and update the
inventory decision to KEEP or BLOCKED rather than weakening a guard.
