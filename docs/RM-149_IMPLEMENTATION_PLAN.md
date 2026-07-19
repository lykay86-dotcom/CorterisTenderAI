# RM-149 implementation plan

Baseline: `77b89efb58c3369f577201ef91063e9c8d60a460`  
Branch: `feat/rm-149-tender-detail-hierarchy`

## Ordered delivery

1. Commit this audit/decision/contract package before application code.
2. Add characterization tests for legacy ORM vs registry identity, current registry/search HTML,
   exact analytics handoff, controller action owners, persisted decision reads and lifecycle reuse.
3. Add expected-red contracts for identity, same-fixture parity, critical precedence, action
   revalidation, unsafe text/URL, route context and repeated open/close.
4. Implement `app.tenders.detail` immutable contracts, action catalog, projections and one assembler.
5. Implement a bounded reusable `TenderDetailPanel`/card projection renderer with RM-143 tokens and
   no repository/service access.
6. Replace registry and persisted-search duplicated detail assembly; keep their tables unchanged.
7. Bind registry-backed Dashboard card/detail and RM-147 exact contributor handoffs through the
   existing controller/runtime. Preserve legacy ORM workspace as typed compatibility.
8. Delegate all operations to existing `TenderSearchUiController`/repositories and refresh exact
   identity after committed mutations.
9. Measure projection/assembly/lifecycle boundaries and write `RM-149_ACCEPTANCE.md`.
10. Run local and GitHub gates, feature merge, exact merge-SHA gate, then separate docs closeout.

## Proposed modules

```text
app/tenders/detail/
  __init__.py
  contracts.py
  assembler.py
  action_catalog.py
  projections.py
app/ui/widgets/tender_detail.py
app/ui/controllers/tender_detail_controller.py  # only if typed action routing cannot stay bounded
```

The assembler depends on narrow existing repository protocols; it is Qt-free and performs no
network/AI/analysis/score/FX/keyring/file operation. The UI controller, if needed, only validates
identity/fingerprint and delegates existing actions.

## Test sequence

Characterization commit precedes expected-red. Expected-red must prove missing production symbols
or behavior before implementation. Focused tests cover contracts/assembler/actions/security/UI;
neighboring tests cover RM-107, RM-142–RM-148, registry/search/documents/analysis/score/verification,
composition and frozen self-test.

Validation is derived from `pyproject.toml` and `.github/workflows/quality-gate.yml`:

```text
python -m pytest -q <focused RM-149 contour>
python -m pytest -q <neighboring contour>
python -m pytest -q
python scripts/check_repository_secrets.py
python -m ruff check .
python -m ruff format . --check
python -m mypy
python -m pip_audit --skip-editable
```

Also run offline/migration/public-import/composition/build/frozen smoke commands exactly as the
workflow, deterministic shuffled fixtures, source URL/text security checks, and the RM-149 benchmark.

## Performance measurement

Record environment, warmups/samples, p50/p95, peak memory and read counts for cold/warm exact detail,
card projection at 0/1/100/1,000/10,000, bounded history, same-ID refresh and repeated open/close.
No arbitrary cross-machine timing threshold is introduced. Generic table optimization is RM-150.

## Scope and rollback

No DB/schema/migration, dependency, second repository/router/page stack, scoring/decision/AI engine,
generic table rewrite or network-on-open is permitted. Rollback is a feature-merge revert; persisted
registry/decision data requires no downgrade.

Stop on ambiguous identity, unreadable persisted decision, critical-priority conflict, evidence loss,
unsafe URL/text boundary, required schema/dependency expansion or red full/frozen/CI gate.
