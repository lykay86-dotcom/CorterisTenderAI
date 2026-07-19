# RM-149 tender detail hierarchy acceptance

## Verdict and publication status

Feature implementation, PR-head gate, merge, and exact merge-SHA gate are complete. This separate
docs-only package records canonical closeout: RM-149 is `DONE`, RM-150 becomes the sole
`IN PROGRESS` stage, and RM-151–RM-200 remain `PLANNED`.

## Entry gate and traceability

- Exact feature baseline: `77b89efb58c3369f577201ef91063e9c8d60a460`.
- RM-148 feature PR #104 merged as `1116216cf00fc74dad2b870617c496242cd659c2`.
- RM-148 exact merge-SHA Quality Gate run `29699279963` succeeded on Windows Python 3.12 and
  Python 3.13.
- RM-148 docs-only closeout PR #105 merged as the feature baseline above; canonical status then
  identified RM-148 as `DONE`, RM-149 as the only `IN PROGRESS` stage, and RM-150–RM-200 as
  `PLANNED`.
- Dedicated worktree/branch: `.worktrees/rm149`, `feat/rm-149-tender-detail-hierarchy`.
- Required audit/decision documents were committed as `1540d75` before application code;
  characterization was committed as `cb4fd56`; expected-red was committed as `f37bef9`; the
  domain/UI/integration implementation was committed as `632d5aa`.
- The unrelated root-checkout `.agents/` and `skills-lock.json` were not changed.

Traceability closes `UI-141-010` at the feature level through the semantic evidence below. Final
canonical closure is intentionally deferred to the post-merge docs-only package.

## Identity, source of truth and owners

- `TenderIdentity(kind="registry", value=registry_key)` is the sole discovered-tender detail
  identity. `legacy_orm` remains a distinct compatibility namespace; equal-looking strings never
  bridge stores.
- `RouteContext.tender_identity_kind` is a closed optional scalar. Explicit registry contexts
  dispatch byte-for-byte to `TenderSearchUiController.open_registry_record`; missing/legacy kind
  continues only through `TenderWorkspacePage.open_tender`.
- `TenderRegistryRepository` owns exact record/tender/occurrence reads and archive state.
  `CollectorStateRepository` owns verification, freshness, latest persisted score and latest
  persisted RM-107 decision payload.
- `TenderSearchUiController` remains the existing documents, requirements, full-analysis,
  participation-score, verification and commercial action/worker owner. RM-149 adds no worker,
  scoring service, analysis service, provider, router, repository or presentation database.
- Registry detail assembly performs one exact record read, four existing state reads and one
  occurrence read bounded to 100. A card projection performs zero reads.

## Accepted contracts and hierarchy

- `app.tenders.detail` provides immutable Qt-free `TenderDetailSnapshot` and
  `TenderCardProjection` contracts, `TenderDetailAssembler`, a complete explainable action catalog,
  HTTPS source policy, stale-action validation and repository-free card projection.
- Contract versions are `tender-detail-v1`, `tender-card-v1` and
  `tender-primary-action-v1`.
- The reusable native Qt hierarchy is critical warning first, then identity, approved persisted
  decision plus exactly one primary action, status/trust strip, facts, evidence, provenance/history
  and secondary actions. It uses RM-143 `Card` and button components; untrusted domain strings are
  never supplied to `setHtml`.
- Critical hard exclusion/stop-factor remains visible even with a positive score. When a blocking
  fixture also has an unresolved verification conflict, `view_verification` is the primary action;
  the approved recommendation is displayed unchanged and is not recomputed.
- Missing decision renders `not loaded`, never `not_recommended`. Search relevance is explicitly
  labelled `Поисковая релевантность … (не решение об участии)` and remains separate from the
  persisted participation decision.
- Price is projected through RM-148 `MoneyAmount`/`format_money` with explicit currency and
  accessible exact output. No local FX/default-currency request exists.
- Typed states cover ready, partial, stale, conflicted, not-found, error and closed presentation;
  stable reason codes include all required identity/read/decision/verification/action/URL/closed
  outcomes. Repository exceptions return `detail_read_failed` without path or exception disclosure.

## Surface and same-fixture parity

`tests/test_rm149_surface_parity.py` persists one real search run, reads it through the accepted
repositories, and publishes the same snapshot through persisted search and registry detail.

| Semantic value | Persisted search | Registry / analytics detail | Compact card |
|---|---|---|---|
| identity | exact `registry_key` | exact `registry_key` | same `TenderIdentity` |
| decision | persisted score/decision only | identical dataclass | same recommendation |
| critical warning | common detail first | common detail first | complete accessible summary |
| primary action | policy v1 | same ID/state/identity | same action spec |
| verification/freshness/conflicts | snapshot | same snapshot | compact statuses |
| price | RM-148 projection | same fact | same formatted value |
| fingerprint | snapshot fingerprint | byte-identical | source snapshot fingerprint |

Search adds relevance only as entry context; it does not alter the shared snapshot or fingerprint.
RM-147 analytics already passes exact contributor registry keys to the same registry detail owner.
Dashboard's existing feed is audited as `legacy_orm` and remains deliberately outside registry-value
parity because no accepted persisted ORM↔registry bridge exists; the reusable `TenderCard` covers an
injected registry-backed dashboard seam without guessing. This is the safe outcome required by the
identity decision, not a hidden title/number join.

## Journeys, keyboard, focus and actions

- J03: Dashboard emits explicit `legacy_orm`; accepted RM-142 route/history tests preserve the
  Dashboard snapshot and stable focus behavior. An explicit registry context uses the existing
  registry controller and cannot call the legacy workspace.
- J09: registry selection/filter remains owned by `TenderRegistryDialog`; detail actions revalidate
  exact identity, snapshot fingerprint and source revision, then emit the existing controller
  signals. The action parity/resilience tests prove documents receive the same key and stale archive
  state performs no second mutation or adjacent-row fallback.
- J11: unresolved conflict is visible in text, produces `CONFLICTED` plus
  `verification_conflicted`, selects verification as primary for the blocking/conflicted fixture,
  and delegates to the existing verification dialog owner.
- Critical/status/action text has accessible names/descriptions and keyboard-focusable native
  buttons. State is text plus semantics, not color-only. Dark/light republishing reuses the same
  widgets. Twenty-five post-warm-up snapshot publications create zero QObject, QThread or QTimer
  growth.
- Archive/restore from user-facing buttons requires confirmation naming the exact procurement
  number/title. Cancel does not mutate. External source opening requires an explicit button action;
  row double-click no longer opens a URL.

## Security, offline and invariance evidence

- Blank, over-bound, control/bidi and unknown identities fail closed. Equal-looking registry and
  legacy IDs remain unequal.
- `file:`, `javascript:`, `data:`, HTTP, credential-bearing, fragment-bearing, malformed and
  control-bearing URLs are rejected. Accepted URLs are bounded canonical HTTPS values.
- Native labels render angle brackets as text. Control/bidi characters in domain display text are
  neutralized and strings are bounded. Raw exceptions, local paths, URL queries and credentials are
  not included in safe error snapshots.
- Opening, theme changes, compact projection and route dispatch cannot call a score/evaluate/AI,
  provider, download, FX, keyring or network owner. The assembler protocol exposes only accepted
  local reads.
- Fingerprints exclude current time, widget identity and theme. Equivalent repeated assembly and
  reversed projection action order remain deterministic.

## Performance and lifecycle evidence

Reproducible command:

```text
python scripts/benchmark_rm149_detail.py
```

Environment: Windows, Python 3.12. No arbitrary performance pass threshold was introduced. Detail
figures use one real local SQLite registry fixture. Card batches run five measured repetitions over
an already assembled snapshot; peak memory is `tracemalloc` incremental peak and repository reads
remain zero. Generic table rendering is not measured or changed because it belongs to RM-150.

Detail assembly:

| Scenario | p50/elapsed ms | p95 ms | Logical reads | History bound |
|---|---:|---:|---:|---:|
| first local assembly | 194.343 | n/a | 6 | 1 of max 100 |
| 20 warm assemblies | 29.328 | 34.206 | 6 per assembly | max 100 |

Repository-free card projection:

| Projections | p50 ms | p95 ms | Peak bytes | Reads |
|---:|---:|---:|---:|---:|
| 0 | 0.003 | 0.019 | 344 | 0 |
| 1 | 0.102 | 0.128 | 1,576 | 0 |
| 100 | 4.492 | 9.353 | 1,576 | 0 |
| 1,000 | 51.426 | 64.169 | 1,608 | 0 |
| 10,000 | 502.915 | 505.788 | 1,608 | 0 |

After one composition warm-up, 25 snapshot republications measured p50 `0.222 ms`, p95
`1.048 ms`, zero reads and growth `QObject=0`, `QThread=0`, `QTimer=0`.

## Exact local verification

| Contour | Result |
|---|---|
| focused RM-149 | `36 passed in 14.29s` |
| neighboring RM-107/116/124/125/140/142–148 and tender dialogs | `358 passed in 79.16s` |
| required offline/migration/composition/build/frozen smokes | `15 passed in 9.23s` |
| full repository suite | `2245 passed, 2 warnings in 185.80s (0:03:05)` |
| repository secret scan | `Repository secret scan passed.` |
| Ruff check | `All checks passed!` |
| Ruff format | `735 files already formatted` before this acceptance document |
| canonical mypy | `Success: no issues found in 20 source files` |
| public import | `DashboardController` |
| dependency audit | `No known vulnerabilities found` |

The two warnings are unchanged openpyxl unsupported-extension and conditional-formatting warnings
from `test_rm132_legacy_credentials_handoff.py`; RM-149 adds no warning.

Automated build/release contract and frozen self-test coverage pass. A newly packaged EXE, native
Narrator, high-contrast, physical 100/125/150/200% DPI and screenshot certification were not run
locally and are not claimed; per the RM-149 specification those bounded manual residuals remain for
RM-152/RM-154. Windows Python 3.12/3.13 evidence from the feature PR and exact merge-SHA Quality
Gate is recorded below.

## GitHub acceptance and closeout

- Feature PR #106 on head `d7a6896b9fa2daf94e760b0fcf1ae030089adcb1` was merged as
  `219e7c43527ca230a61de8cdeb3f191288fc3f87`.
- PR-head Quality Gate run `29703943804` succeeded. Python 3.12 job `88238135602` reported
  `2245 passed, 2 warnings in 95.59s`; Python 3.13 job `88238146684` reported
  `2245 passed, 2 warnings in 125.70s`. The first Python 3.12 attempt ended in a native Windows
  access violation without a test assertion; rerun of the unchanged head SHA passed completely.
- Automatic push-run `29704404132` reported exact
  `headSha=219e7c43527ca230a61de8cdeb3f191288fc3f87`.
- In that exact merge-SHA run, Python 3.12 job `88239262921` reported
  `2245 passed, 2 warnings in 209.10s`, and Python 3.13 job `88239263398` reported
  `2245 passed, 2 warnings in 141.43s`. The first Python 3.12 attempt ended in native Windows heap
  violation `0xc0000374` without a test assertion; rerun of the unchanged merge SHA passed. Every
  required step, including dependency audit, succeeded.
- This closeout is documentation-only: no application code, dependency, schema, migration,
  deterministic decision logic, score, recommendation, or critical stop-factor priority changes.

## Scope, rollback and next action

- No DB/schema/migration, dependency, provider/network/AI, credential, analytics aggregation,
  scoring/decision formula, critical precedence, generic table or second router/repository change.
- Code rollback is a revert of the RM-149 feature commits to baseline `77b89ef`; there is no data,
  schema, settings or dependency rollback.
- Stop publication on any identity/fingerprint/parity change, lost verification evidence, unsafe
  URL/text outcome, new owner/network/dependency, full/Windows failure or changed RM-107 decision.
- All feature and publication conditions are satisfied. This separate canonical docs-only closeout
  records RM-149 as `DONE` and activates RM-150. RM-151 must not start until RM-150 satisfies the
  Definition of Done and its canonical status is updated.
