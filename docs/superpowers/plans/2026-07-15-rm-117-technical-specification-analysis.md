# RM-117 Explainable Technical Specification Analysis Plan

Baseline: `343cd425e4f3f0eb1b22a1c4b2c41d8c3e2e0f24`

1. Complete and checkpoint the post-RM-116 audit before application changes.
2. Expose the existing deterministic document classifier and reuse it in the AI context builder.
   Add semantic document kind, TS-first stable ordering and TS completeness statistics.
3. Add RED tests for the strict 13-group provider object, nested domain model, legacy reading,
   future rejection and fingerprint isolation; then raise the audited versions and implement.
4. Update the single prompt/analyzer path. Normalize every TS candidate through the RM-116
   resolver, restrict verified evidence to TS documents, handle multi-source contradictions and
   derive local status/warnings without a second provider call.
5. Prove service/Orchestrator/runtime/cache invariants and the unchanged single `RUNNING_AI` stage.
6. Render the subsection in the existing AI tab and canonical JSON/HTML exporters with safe
   citation/provenance presentation and complete escaping.
7. Add RM-107 regression tests without changing decision production code.
8. Run focused tests after each slice, then the exact target contour, full pytest, Ruff, mypy,
   secret scan, dependency audit and diff check. Record versions, counts, durations and final SHA
   in `docs/RM-117_REQUIREMENTS.md`.
9. Perform an adversarial code review for component duplication, evidence trust, cache isolation,
   private-data leakage and deterministic decision boundaries before handoff.

No step may add a second classifier table, verifier, provider, request, service, Orchestrator,
repository, database object, AI stage, UI workflow or Decision Engine.
