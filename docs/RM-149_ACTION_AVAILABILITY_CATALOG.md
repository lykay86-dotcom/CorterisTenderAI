# RM-149 action availability catalog

Policy version: `tender-primary-action-v1`

## States and execution boundary

States: `AVAILABLE`, `DISABLED`, `RUNNING`, `COMPLETED`, `FAILED`, `CONTEXT_REQUIRED`, `STALE`,
`CONFLICTED`, `UNSUPPORTED`.

Every `TenderActionSpec` includes stable ID/label/state/reason, exact `TenderIdentity`, required
capability, primary/secondary role, destructive flag, snapshot fingerprint/revision, focus-return
token and accessible description. Execution requires exact identity and matching current fingerprint,
then delegates to an existing owner. No action executes from current row index.

## Catalog

| ID | Existing owner | Availability | Destructive |
|---|---|---|---:|
| `open_detail` | registry dialog/detail controller | exact persisted registry row | no |
| `open_official_source` | validated source opener | HTTPS URL passes bounded validation | no |
| `download_documents` | `TenderSearchUiController.open_registry_documents` | exact registry tender and runtime available | no |
| `view_documents` | existing documents dialog | existing/current dialog or local document state | no |
| `run_requirements_analysis` | existing requirement-analysis controller | exact registry tender and service available | no |
| `view_requirements_analysis` | existing requirement dialog/repository | persisted result available | no |
| `run_full_analysis` | existing full-analysis worker | exact tender, service available, no active same-ID run | no |
| `view_full_analysis` | existing full-analysis dialog | persisted/completed result available | no |
| `view_participation_decision` | existing score dialog | persisted score/decision available | no |
| `recalculate_participation_decision` | existing score worker | explicit user action and service available | no |
| `view_verification` | existing verification dialog | exact registry row | no |
| `resolve_verification` | existing verification review service/dialog | unresolved conflict and capability available | yes |
| `open_commercial_estimate` | existing commercial estimator | exact registry row and repository available | no |
| `archive_tender` | `TenderRegistryRepository.set_archived` | current exact active record/revision | yes |
| `restore_tender` | same repository | current exact archived record/revision | yes |
| `return_to_origin` | RM-142 navigation owner | valid bounded origin snapshot | no |

Unsupported or unavailable actions stay explainable; they are not hidden to mask an error.

## Primary action priority

Exactly one primary action is selected, in this order:

1. blocking stop-factor/hard exclusion → `view_participation_decision` or `view_verification`;
2. unresolved decision-affecting conflict → `view_verification`;
3. missing required document/analysis evidence → existing `download_documents` or
   `run_full_analysis`;
4. current persisted decision → first safe existing action ID in its persisted action plan that maps
   to this catalog, otherwise `view_participation_decision`;
5. no decision context → `open_detail`, then validated `open_official_source`.

The policy chooses presentation focus only; it never invents “participate” or changes RM-107.

## Destructive revalidation

Archive/restore/verification resolution require exact registry key, current record revision and
explicit confirmation naming procurement number/title. Cancel performs no mutation. Stale revision
returns `action_stale`, refreshes the exact identity and preserves selection/focus; no adjacent-row
fallback exists.

## Routing map

The detail controller emits a typed request. `TenderSearchUiController` remains the sole owner of
document, requirements, full-analysis, score, verification and commercial dialogs/workers. The
registry repository remains the sole archive owner. Source opening goes through one validator. RM-149
adds no service, worker, network call or hidden mutation.
