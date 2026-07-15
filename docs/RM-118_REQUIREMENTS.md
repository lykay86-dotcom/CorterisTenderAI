# RM-118 Requirements — Explainable Draft Contract Analysis

Status: implementation contract
Baseline: `2697637fc0173082f1a6fec7c5b5eaef8e099698`
Branch: `feat/rm-118-draft-contract-analysis`

## Outcome and hard boundary

Extend the single `AiDocumentAnalysis` result with
`draft_contract: AiDraftContractAnalysis`. The subsection neutrally extracts and explains draft
contract terms from locally classified contract documents in the one provider response, verifies
evidence through the RM-116 resolver, reports completeness honestly, and renders/exports without
changing RM-107.

Do not add a provider call, analyzer, ContractAnalysisService, Orchestrator, repository, database
object, AI stage, prompt workflow, UI workflow, exporter, classifier, Decision Engine, legal-risk
assessment, financial-risk assessment, cash-flow calculation, profitability assessment, score,
recommendation, AI action, or stop factor.

## Explicit local domain contract

Add `AiDraftContractStatus` with `not_found`, `complete`, `partial`, and `unavailable` and an
explicit `AiDraftContractAnalysis` dataclass with:

- local `status`, `document_ids`, `included_document_ids`, and `warnings`;
- `subject_and_scope`;
- `term_schedule_and_location`;
- `price_and_price_change`;
- `payment_terms`;
- `acceptance_and_closing_documents`;
- `performance_security`;
- `warranty_and_defect_remediation`;
- `customer_obligations_and_dependencies`;
- `contractor_obligations_and_subcontracting`;
- `liability_penalties_and_damages`;
- `change_suspension_and_termination`;
- `force_majeure_and_notifications`;
- `dispute_confidentiality_and_ip`;
- `ambiguities`, `contradictions`, and `clarification_points`.

Every finding uses the existing `AiFinding`. Provider output contains exactly the 16 finding
arrays and cannot control status, document IDs, included IDs, warnings, category, verification,
severity, legal/financial risk, score, recommendation, participation, stop factors, citations,
provenance, or links.

## Classification contract

1. Keep one public `classify_document_kind(source_name, text)` and one `DocumentKind.DRAFT_CONTRACT`.
2. Recognize the required project-contract filenames, heading, and characteristic contract
   structure.
3. Reject experience-contract wording, notice conclusion wording, performance-security
   instructions, TS references to work under a contract, future-contract application forms, and
   NMCK analogous-contract references.
4. Preserve TS priority for `Приложение к договору — Техническое задание.pdf`.
5. Deterministic `TenderRequirementsAnalyzer` and AI context must agree because they call the same
   classifier. Existing deterministic contract rules remain unchanged.

## Context and completeness contract

1. Use only existing extracted-text results; do not reread source files or download documents.
2. Stable order is TS, draft contract, notice/estimate, then all other documents.
3. Add `draft_contract_document_count`, `included_draft_contract_document_count`,
   `draft_contract_truncated`, `draft_contract_document_ids`, and
   `included_draft_contract_document_ids` to explicit context statistics.
4. Empty, unavailable, truncated, duplicate, and total-limit omitted contracts cannot produce a
   false `complete` result.
5. All completeness statistics participate in the existing context fingerprint.
6. Share only minimal internal scoped-statistics mechanics with TS; keep explicit typed public
   fields for both sections.

## Strict provider and prompt contract

1. Add one required `draft_contract` object to the canonical Pydantic provider output schema.
2. Reuse `ProviderFindingPayload`; keep `strict=True`, `extra="forbid"`, one decoder and one JSON
   Schema. All 16 arrays are mandatory, even when empty.
3. A missing key, extra key, duplicate key, wrong nested type, or provider-owned local field
   rejects the entire provider payload.
4. The one prompt permits contract findings only from `KIND draft_contract`, only with supplied
   document IDs and exact continuous quotes. It forbids invention, uncited clarification points,
   links, local fields, and legal/financial conclusions and requests one JSON object only.

## Local evidence and status contract

1. Build allowed IDs only from current `DocumentKind.DRAFT_CONTRACT` documents and pass every
   candidate through the single `resolve_citation()`.
2. Unknown/non-contract IDs, altered quotes, invalid locators, damaged provenance, and unsupported
   clarification points remain explicit unverified findings and make the section partial.
3. Stable deduplication preserves identical statements from different documents or quotations.
4. A verified contradiction needs at least two distinct canonical citations. Two different
   offsets in one contract are allowed; repeating one citation is not.
5. `not_found` means no local contract was classified. `unavailable` means one was found but a
   safe result could not be prepared. `partial` covers incomplete context, rejected evidence, or
   insufficient contradiction/clarification support. `complete` requires found and fully included
   contract context, structurally valid provider output, only verified returned findings, and no
   contract warning.

## Payload, cache and version contract

1. Add the subsection to canonical `to_payload()`/`from_payload()` with exact fail-closed shape.
2. Current round-trip retains verified contract evidence. Generic/TS/non-contract cached evidence
   cannot be promoted; future/corrupt payloads remain incompatible.
3. Supported old payloads read safely with an empty unavailable contract section. A current
   provider failure cannot be replaced by stale success.
4. Persist no raw response, prompt, full document text, credential, exception, traceback, or
   private path.
5. Increase exactly once: payload `4→5`, provider schema `2→3`, response format `v2→v3`, prompt
   `4→5`, analyzer `5→6`, context `3→4`. Citation resolver remains `1`.
6. Continue using the existing SQLite table and versioned JSON; no migration is required.

## UI, export and security contract

1. Extend the existing AI tab with `Проект договора/контракта`, Russian status text, found and
   included counts, all 16 labels, contract warnings, verified/unverified distinction, safe
   RM-116 citation links, and incomplete-context notice.
2. Render unverified evidence with `Неподтверждённый вывод — не влияет на рекомендацию.`
3. Extend the existing `_current_citation_targets()` and JSON/HTML exporter. JSON uses canonical
   `to_payload()`; HTML escapes all external strings and uses only safe internal anchors.
4. Contract citations enter the existing deduplicated source list. UI/export must not reveal raw
   responses, prompt, document bodies, credentials, tracebacks, exceptions, or private paths.

## RM-107 invariants

- Do not change `ParticipationDecisionPolicy`, thresholds, recommendation types, deterministic
  requirement rules, `CommercialEstimator`, stop-factor services, or critical-stop ordering.
- Do not add draft-contract findings to `_current_verified_ai_findings()`.
- Draft-contract findings never change score, recommendation, action plan, participation, or stop
  factors. Existing generic risks/suspicious conditions/contradictions retain current behavior.
- A deterministic critical stop factor still blocks participation at score 100.

## Required test and review contour

Add `tests/test_ai_draft_contract_analysis.py` and extend the existing classifier, context, strict
schema, persisted schema, analyzer, service, repository, provenance, provider-runtime, export,
full-analysis UI, and RM-107 tests named in the task specification.

The tests must cover all specified positive/negative classification cases; ordering,
completeness and fingerprint changes; strict 16-key schema rejection; complete/not-found/
unavailable/partial analysis; evidence tampering and contradiction independence; current/legacy/
future/corrupt cache; one provider call and one runtime graph; all UI statuses, labels, citations,
XSS and recovery; and unchanged RM-107/critical-stop behavior.

Adversarial review must prove there is no second AI workflow/classifier, no wholesale TS
normalization copy, no cached evidence promotion or provider-controlled local decision, contract
completeness is fingerprinted, private material is not exposed, RM-120/RM-121 are absent, and
RM-107 is unchanged.

## Validation record

Baseline environment: Python 3.12.7, worktree-local `TEMP/TMP`,
`QT_QPA_PLATFORM=offscreen`, and no live provider/DNS/keyring.

- Baseline SHA: `2697637fc0173082f1a6fec7c5b5eaef8e099698`.
- Target baseline: `240 passed in 12.73s`.
- Full baseline: `1043 passed in 53.98s`.
- Implementation checkpoint SHA: pending.
- Final target/full counts, Ruff, format, mypy, secret scan, dependency audit, diff check, and
  adversarial review: pending implementation.

Required final commands:

```powershell
python -m pytest -q
python -m ruff check .
python -m ruff format . --check
python -m mypy
python scripts/check_repository_secrets.py
python -m pip_audit --skip-editable
git diff --check
```

Feature-branch acceptance does not mark RM-118 `DONE`; feature merge, post-merge Windows Quality
Gate on Python 3.12/3.13, and a separate docs-only closeout remain mandatory.
