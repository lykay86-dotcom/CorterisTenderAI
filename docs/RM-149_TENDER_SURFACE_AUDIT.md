# RM-149 tender surface audit

Baseline: `77b89efb58c3369f577201ef91063e9c8d60a460`  
Finding: `UI-141-010`  
Verdict: implementation may proceed only with an exact typed identity boundary and one registry-backed
detail projection. No persisted bridge exists between Collector registry identities and legacy ORM
identities, so title, row, procurement number and equal-looking strings must never be used as a bridge.

## Entry gate

- RM-148 feature PR #104 merged as `1116216cf00fc74dad2b870617c496242cd659c2`.
- Exact feature merge-SHA Quality Gate `29699279963` succeeded on Python 3.12 and 3.13.
- Docs-only PR #105 merged as `77b89efb58c3369f577201ef91063e9c8d60a460`.
- Canonical status: RM-148 `DONE`, RM-149 sole `IN PROGRESS`, RM-150–RM-200 `PLANNED`.
- Dedicated branch/worktree: `feat/rm-149-tender-detail-hierarchy`, `.worktrees/rm149`.

## Identity audit

| Producer / consumer | Current identity | Exact owner | Result |
|---|---|---|---|
| Dashboard feed/controller | legacy SQLAlchemy `Tender.id`, reached through tender number map | `TenderRepository` | legacy-only; no registry inference |
| `TenderWorkspacePage.open_tender` | legacy table first-column ID | `TenderRepository` / workspace | typed legacy compatibility path |
| Search result | transient `UnifiedTender`; deterministic registry key can be calculated | search runner + registry save | canonical only after exact registry row exists |
| Registry table/detail/actions | `TenderRegistryRecord.registry_key` | `TenderRegistryRepository` | canonical discovered-tender detail identity |
| RM-147 analytics contributor | exact sorted `registry_key` | RM-147 snapshot | pass unchanged to canonical detail |
| Documents/requirements/full analysis/score/verification/commercial | `registry_key` | existing controller/services | reusable action destinations |
| `RouteContext.tender_id` | currently semantically mixed | RM-142 navigation contract | must be paired with a bounded identity kind |

Static and runtime composition contain no accepted persisted ORM-ID ↔ registry-key bridge. The
legacy ORM repository coerces numeric-looking IDs; Collector registry keys are bounded opaque strings
such as `procurement:<value>`. The new contract therefore chooses typed namespaces and fails closed
when a target handler receives the wrong kind.

## Surface and owner inventory

| Surface | Identity | Facts / status | Decision / provenance | Existing actions | Return/focus | Owner / RM-149 disposition |
|---|---|---|---|---|---|---|
| Dashboard `TenderFeed` | legacy ORM ID via number map | ORM title/customer/NMCK/deadline/status | ORM score/recommendation; no Collector evidence | open legacy workspace | route history + feed focus token | preserve legacy; add registry-card projection seam without guessing |
| `TenderSearchResultsDialog` | transient `UnifiedTender`, current row index | local HTML; relevance and provider outcomes | relevance only, no persisted decision | source/documents/full analysis | modeless dialog, selected row | resolve exact saved registry row and render common projection |
| `TenderRegistryDialog` | exact `registry_key` stored in item data | local HTML plus verification/freshness maps | occurrence history; local formatters | source/full/requirements/score/commercial/verification/documents/archive | `select_registry_key()` | retain table/filter/history; replace detail assembly with common snapshot |
| `TenderWorkspacePage` | legacy ORM ID | legacy overview + analysis tabs | legacy saved analyses | legacy workspace actions | RM-142 embedded page state | compatibility only; do not pretend it is registry detail |
| `TenderSearchUiController` | registry keys for mature Collector flows | controller owns runtime repositories and worker state | opens existing persisted result dialogs | all registry action destinations | controller-owned modeless dialogs | remain sole action/worker owner; bind detail adapters only |
| `TenderDocumentsDialog` | canonical key from `UnifiedTender` | document store state | source/evidence per document | download/view/analyze/open folder | dialog parent | existing owner; no filesystem reads by detail assembler |
| `TenderRequirementAnalysisDialog` | exact `registry_key` | persisted requirement analysis | critical findings/evidence | run/view related flows | controller dictionary keyed by ID | existing owner |
| `TenderFullAnalysisDialog` | exact `registry_key` | worker episode and result | score, summary and AI rendered together today | cancel/docs/requirements/score/recheck | controller dictionary keyed by ID | existing owner; deterministic decision remains visually superior |
| `TenderParticipationScoreDialog` | exact `registry_key` | persisted score fields | score/stop assessment + RM-107 decision | explicit recalculate | controller dictionary keyed by ID | existing owner; detail reads latest only |
| `TenderVerificationDialog` | exact `registry_key` | verification review/conflicts | field evidence and resolutions | refresh/resolve/clear | exact dialog key | existing owner; conflict primary action delegates here |
| Commercial estimator | exact `registry_key` | persisted draft/result | commercial evidence | explicit estimate operation | controller dictionary keyed by ID | existing owner |
| RM-147 analytics | exact contributor `registry_key` | immutable analytics snapshot | source/partial/conflict semantics | contributor activate | selected point/list | open common registry detail; preserve analytics snapshot |
| Source URL | raw stored string | local direct `QDesktopServices.openUrl` | no scheme gate in two dialogs | external open/double-click | none | central HTTPS-only validator; no automatic row double-click side effect |
| Archive/restore | exact selected record | current archived bool | none | direct repository mutation | registry selection refresh | keep existing repository mutation; add revision/identity revalidation |

## Duplication and risk findings

- Registry and search-results dialogs independently assemble rich HTML, format price/deadline/source,
  decide button availability, and open source URLs.
- Search relevance is displayed near legacy participation language and can be mistaken for an
  approved recommendation.
- Registry verification/freshness text is partly color/tooltip enhanced and is not one reusable
  accessible hierarchy.
- Dashboard maps tender number to legacy ORM ID; treating that number as a registry identity would
  be an unsafe implicit bridge.
- Analytics already provides the strongest exact-identity handoff and must remain unchanged.
- Existing persisted score and participation-decision payloads are available from
  `CollectorStateRepository`; opening detail never needs scoring or AI execution.
- Existing action workers and modeless-dialog lifetime maps are all owned by
  `TenderSearchUiController`; a second worker/controller stack would be duplication.

## Accepted migration boundary

- Migrate registry detail, persisted search-result detail, analytics drill-down destination, and a
  registry-backed Dashboard card seam to one snapshot/card projection.
- Keep registry/search tables and Dashboard feed table implementations for RM-150.
- Keep legacy workspace/ORM route explicitly namespaced and fail closed for registry-only actions.
- Keep every analysis/verification/document/commercial worker and mutation owner unchanged.
- Add no database table, migration, dependency, network path, scoring policy or AI owner.

## Characterization targets

Tests must first pin the two identity namespaces, registry selection preservation, duplicated HTML
facts/actions, analytics exact-key handoff, legacy deep-link behavior, persisted decision reads,
critical stop-factor presentation, unsafe URL behavior, controller owner counts, and repeated
modeless-dialog reuse. Expected-red tests then require one snapshot fingerprint, one primary action,
one critical warning and one approved decision on every migrated projection.
