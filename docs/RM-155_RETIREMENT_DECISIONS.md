# RM-155 retirement decisions

| Decision ID | Candidates | Decision | Evidence threshold |
|---|---|---|---|
| RM155-RET-001 | COMP-001--006 | REMOVE old module/wrapper/re-exports | migrate direct tests; no production/frozen/settings/public consumers; import must fail explicitly |
| RM155-RET-002 | COMP-007--010 | MIGRATE to `workflow_page`, then REMOVE aliases/fallbacks | bootstrap parity first; no attribute consumer remains; one workflow owner still proven |
| RM155-RET-003 | COMP-011 | REMOVE obsolete catalog-query seam | no runtime caller; canonical unified-search seam remains and is tested |
| RM155-RET-004 | COMP-012--021 | KEEP route aliases and stable enum | active sidebar/deep-link/test/RM-156 consumers; not duplicate router |
| RM155-RET-005 | COMP-022--024 | KEEP settings/actions/object names | persisted/UIA/QSS/visual contracts; rename has no benefit |
| RM155-RET-006 | COMP-025--032 | KEEP cross-stage adapters/evidence | typed accepted boundaries or release evidence; no duplicate production owner |

The remove decisions are reversible source changes and require no data rollback. KEEP means no new
business logic may be added to the boundary. Future retirement requires a new audited consumer and
persistence decision; RM-155 does not silently schedule removal by version.
