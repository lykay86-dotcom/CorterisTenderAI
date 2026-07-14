# RM-116 Verified Citations and Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Give every verified Tender Intelligence finding a locally resolved exact citation and current-run provenance without allowing AI output to control verification or RM-107 decisions.

**Architecture:** Extend the existing immutable AI domain models and add one pure citation resolver in app/core/ai/citations.py. The existing analysis service computes the fingerprint, the analyzer resolves strict RM-115 candidate evidence and builds provenance, and current repository/UI/export/RM-107 consumers use only normalized results.

**Tech Stack:** Python 3.12/3.13, frozen dataclasses, Pydantic v2 provider-output schema, SQLite payload JSON, PySide6, pytest, Ruff, mypy, pip-audit.

## Global Constraints

- Work only in feat/rm-116-citations-provenance; RM-116 remains IN PROGRESS until closeout.
- Preserve one provider, analyzer, Orchestrator, repository, context builder, strict JSON Schema, Decision Engine, document viewer, and exporter.
- Provider output remains exactly the RM-115 candidate contract; do not add citation/provenance fields to output_schema.py.
- Use exact case-sensitive continuous quote matching only; no fuzzy matching, OCR, web verification, vector search, or second RAG path.
- AI never owns verification status, citation ID, offsets, checksum, source reference, provenance, score, recommendation, or stop-factor priority.
- Keep deterministic fallback offline; tests must not use DNS, OpenAI/Ollama, host keyring, saved credentials, or real API keys.
- Keep the existing SQLite table and payload_json; no physical database migration.
- Never serialize or log API keys, Authorization headers, provider URLs, prompts, raw responses, full document text, absolute paths, file URLs, Windows usernames, traceback, or exception text.
- RM-117 and later roadmap stages are out of scope.

## File Structure

- Create app/core/ai/citations.py: exact-match resolver, marker parsing, deterministic IDs, and closed resolution outcomes.
- Modify app/ai/provider.py and app/core/ai/provider_selection.py: public provider metadata.
- Modify app/core/ai/schemas.py: citation fields, source snapshots, provenance, payload v3, and decision eligibility.
- Modify app/core/ai/document_context.py: basename-only display identity and logical source value.
- Modify app/core/ai/analyzer.py, prompts.py, and repository.py: resolution, provenance, versions, and cache.
- Modify participation_decision_service.py: current-citation eligibility only.
- Modify existing full-analysis/documents dialogs and controller: safe internal navigation.
- Modify existing tender_ai_analysis exporter: structured JSON and internal HTML anchors.
- Create tests/test_ai_citations.py and tests/test_ai_provenance.py; extend existing focused tests.

---

### Task 1: Public Provider Metadata Contract

**Files:**
- Modify: app/ai/provider.py:14-101
- Modify: app/core/ai/provider_selection.py:250-318
- Test: tests/test_openai_compatible_provider.py
- Test: tests/test_ai_provider_selection.py

**Interfaces:**
- Produces: AiProviderMetadata(provider_id: str, model: str).
- Produces: AIProvider.metadata -> AiProviderMetadata.
- Consumes: stable AiProviderId.value supplied by provider selection.

- [ ] **Step 1: Write failing metadata tests**

~~~python
def test_provider_exposes_only_public_safe_metadata() -> None:
    provider = OpenAICompatibleProvider(
        "secret", "https://api.openai.com/v1", "gpt-5", provider_id="openai"
    )
    assert provider.metadata == AiProviderMetadata("openai", "gpt-5")
    rendered = repr(provider.metadata)
    assert "secret" not in rendered
    assert "api.openai.com" not in rendered


def test_provider_metadata_bounds_untrusted_values() -> None:
    metadata = AiProviderMetadata("bad\nprovider", "m" * 500)
    assert metadata.provider_id == "unknown"
    assert len(metadata.model) == 200
~~~

Also assert resolved OpenAI, generic compatible, and Ollama providers expose their stable ID,
and DisabledProvider exposes disabled without reading keyring.

- [ ] **Step 2: Run tests and verify RED**

~~~powershell
python -m pytest -q tests/test_openai_compatible_provider.py tests/test_ai_provider_selection.py
~~~

Expected: missing AiProviderMetadata, metadata, and provider_id constructor support.

- [ ] **Step 3: Implement the minimal public contract**

~~~python
@dataclass(frozen=True, slots=True)
class AiProviderMetadata:
    provider_id: str = "unknown"
    model: str = "unknown"

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _safe_metadata_value(self.provider_id, 80))
        object.__setattr__(self, "model", _safe_metadata_value(self.model, 200))


class AIProvider(ABC):
    @property
    def metadata(self) -> AiProviderMetadata:
        return AiProviderMetadata()
~~~

The helper strips whitespace, rejects control characters, truncates to the limit, and returns
unknown for empty/rejected values. DisabledProvider returns disabled/unknown.
OpenAICompatibleProvider accepts keyword-only provider_id="openai_compatible" and exposes only
the sanitized immutable value. Provider selection passes settings.provider_id.value.

- [ ] **Step 4: Run Step 2 and verify GREEN**

Expected: all focused tests pass with no network calls.

- [ ] **Step 5: Commit**

~~~powershell
git add app/ai/provider.py app/core/ai/provider_selection.py tests/test_openai_compatible_provider.py tests/test_ai_provider_selection.py
git commit -m "feat(rm-116): expose safe provider metadata"
~~~

### Task 2: Canonical Exact Citation Resolver

**Files:**
- Create: app/core/ai/citations.py
- Modify: app/core/ai/schemas.py:23-68
- Create: tests/test_ai_citations.py
- Modify: tests/test_ai_document_schemas.py

**Interfaces:**
- Produces: CITATION_RESOLVER_VERSION = "1".
- Produces: CitationResolutionIssue, CitationResolution, resolve_citation(...).
- Produces: extended AiEvidence with canonical citation fields.

Use this closed resolution envelope and exact function signature:

~~~python
class CitationResolutionIssue(StrEnum):
    UNKNOWN_DOCUMENT = "unknown_document"
    INVALID_QUOTE = "invalid_quote"
    INVALID_CHECKSUM = "invalid_checksum"
    INVALID_CONFIDENCE = "invalid_confidence"
    QUOTE_NOT_FOUND = "quote_not_found"
    AMBIGUOUS_QUOTE = "ambiguous_quote"
    LOCATOR_CONFLICT = "locator_conflict"


@dataclass(frozen=True, slots=True)
class CitationResolution:
    evidence: AiEvidence | None
    issue: CitationResolutionIssue | None


def resolve_citation(
    *,
    document_id: str,
    quote: str,
    section: str,
    page: int | None,
    confidence: float,
    documents: tuple[AiDocument, ...],
    context_fingerprint: str,
) -> CitationResolution: ...
~~~

- [ ] **Step 1: Write the unique-match failing test**

~~~python
def test_unique_exact_quote_resolves_offsets_and_stable_id() -> None:
    document = _document(
        text="===== Страница 2 =====\nСрок поставки десять дней.",
        checksum="a" * 64,
    )
    first = resolve_citation(
        document_id="doc-1",
        quote="Срок поставки десять дней.",
        section="",
        page=None,
        confidence=0.8,
        documents=(document,),
        context_fingerprint="b" * 64,
    )
    second = resolve_citation(
        document_id="doc-1",
        quote="Срок поставки десять дней.",
        section="",
        page=None,
        confidence=0.8,
        documents=(document,),
        context_fingerprint="b" * 64,
    )
    assert first.evidence is not None
    assert first.evidence.character_start == document.text.index("Срок")
    assert first.evidence.character_end == first.evidence.character_start + len(first.evidence.quote)
    assert first.evidence.page == 2
    assert first.evidence.section == "Страница 2"
    assert first.evidence.citation_id == second.evidence.citation_id
~~~

- [ ] **Step 2: Add the rejection/ambiguity matrix**

Cover unknown document, empty/absent quote, invalid checksum, bool/string/NaN/Infinity/out-of-
range confidence, changed checksum/fingerprint, duplicate quote without locator, duplicate
quote selected by matching local page/section, conflicting locator, case change, and quote in
truncated context. Rejections have evidence=None and a closed enum issue.

- [ ] **Step 3: Run resolver tests and verify RED**

~~~powershell
python -m pytest -q tests/test_ai_citations.py
~~~

Expected: import failure because citations.py does not exist.

- [ ] **Step 4: Extend AiEvidence and implement the resolver**

~~~python
class AiEvidenceVerificationMethod(StrEnum):
    EXACT_QUOTE = "exact_quote"


@dataclass(frozen=True, slots=True)
class AiEvidence:
    citation_id: str
    document_id: str
    quote: str
    character_start: int
    character_end: int
    section: str
    page: int | None
    confidence: float
    verification_method: AiEvidenceVerificationMethod
    checksum_sha256: str
    source_ref: str
    context_fingerprint: str
~~~

In citations.py, parse markers with multiline ^===== (.+) =====$, find all occurrences with
str.find, derive the nearest preceding marker, and parse Страница <positive integer>. For
duplicates, provider hints may filter only locally derived locator values and must leave one
match. Hash canonical JSON of fingerprint, document ID, checksum, start, end, and quote;
citation_id is cit_ plus 32 lowercase hex chars. source_ref is doc_ plus 32 hex chars of the
document-ID hash.

- [ ] **Step 5: Run focused tests and verify GREEN**

~~~powershell
python -m pytest -q tests/test_ai_citations.py tests/test_ai_document_schemas.py
~~~

Expected: all citation/schema tests pass; no partially populated verified evidence is valid.

- [ ] **Step 6: Commit**

~~~powershell
git add app/core/ai/citations.py app/core/ai/schemas.py tests/test_ai_citations.py tests/test_ai_document_schemas.py
git commit -m "feat(rm-116): add canonical citation resolution"
~~~

### Task 3: Provenance, Source Snapshots, and Payload Version 3

**Files:**
- Modify: app/core/ai/schemas.py
- Modify: app/core/ai/document_context.py:80-125
- Create: tests/test_ai_provenance.py
- Modify: tests/test_ai_document_schemas.py
- Modify: tests/test_ai_document_context.py

**Interfaces:**
- Produces: AiSourceSnapshot, AiAnalysisProvenance, analysis.provenance.
- Produces: AiDocumentAnalysis.is_current_verified(finding) -> bool.
- Changes: AI_ANALYSIS_SCHEMA_VERSION from 2 to 3.

- [ ] **Step 1: Write failing provenance and legacy tests**

~~~python
def test_provenance_is_timezone_aware_and_contains_only_safe_sources() -> None:
    provenance = _provenance()
    assert datetime.fromisoformat(provenance.created_at).utcoffset() is not None
    assert provenance.sources[0].display_name == "tender.pdf"
    serialized = json.dumps(provenance.to_payload(), ensure_ascii=False)
    assert r"C:\Users\SecretUser" not in serialized
    assert "document body" not in serialized


def test_legacy_payload_findings_are_always_unverified() -> None:
    restored = AiDocumentAnalysis.from_payload(_legacy_version_2_payload_marked_verified())
    assert restored.risks[0].status == AiFindingStatus.UNVERIFIED
    assert restored.risks[0].evidence is None
~~~

Also test version-3 round-trip, missing/corrupt provenance, future payload, bounded response ID,
source counts, and current-verification rejection for checksum/fingerprint/citation/source
mismatches.

- [ ] **Step 2: Add a private-path context test**

Use C:\Users\SecretUser\Documents\tender.pdf. Assert the context document has name tender.pdf,
source local_document_store, and no field containing the private path.

- [ ] **Step 3: Run tests and verify RED**

~~~powershell
python -m pytest -q tests/test_ai_provenance.py tests/test_ai_document_schemas.py tests/test_ai_document_context.py
~~~

Expected: missing provenance models/version fields and current source leakage.

- [ ] **Step 4: Implement immutable provenance models**

~~~python
@dataclass(frozen=True, slots=True)
class AiSourceSnapshot:
    document_id: str
    display_name: str
    document_type: str
    checksum_sha256: str
    verification_status: str
    received_at: str
    truncated: bool
    included_character_count: int
    original_character_count: int


@dataclass(frozen=True, slots=True)
class AiAnalysisProvenance:
    analysis_id: str
    context_fingerprint: str
    created_at: str
    prompt_version: str
    output_schema_version: str
    persisted_schema_version: int
    analyzer_version: str
    context_version: str
    citation_resolver_version: str
    provider_id: str
    provider_model: str
    provider_response_id: str
    sources: tuple[AiSourceSnapshot, ...]
~~~

Add bounded serialization. Version 3 restores verified findings only when evidence and
provenance fully validate and is_current_verified() succeeds. Versions 1-2 restore statements
but force UNVERIFIED/no evidence. Future versions produce CACHE_INCOMPATIBLE with no findings.
Normalize received_at to a timezone-aware ISO value when valid and to the literal unknown when
the extraction timestamp is absent or invalid.
AiDocumentAnalysis.to_payload() emits both a provenance object and a source_registry list built
only from provenance.sources; from_payload() requires them to describe the same ordered source
snapshots before any finding can remain verified.

- [ ] **Step 5: Sanitize document context**

Set source="local_document_store"; use basename only; prefer safe record.document_format;
preserve checksum, extracted timestamp, truncation, included length, and original length.

- [ ] **Step 6: Run Step 3 and verify GREEN**

Expected: all tests pass and private paths are absent from domain/payload data.

- [ ] **Step 7: Commit**

~~~powershell
git add app/core/ai/schemas.py app/core/ai/document_context.py tests/test_ai_provenance.py tests/test_ai_document_schemas.py tests/test_ai_document_context.py
git commit -m "feat(rm-116): add analysis provenance contract"
~~~

### Task 4: Analyzer, Prompt, Fingerprint, and Service Integration

**Files:**
- Modify: app/core/ai/analyzer.py
- Modify: app/core/ai/prompts.py
- Modify: app/core/ai/repository.py:20-70
- Modify: tests/test_ai_document_analyzer.py
- Modify: tests/test_ai_document_analysis_service.py
- Modify: tests/test_ai_document_analysis_repository.py
- Modify: tests/test_ai_output_schema.py

**Interfaces:**
- Changes analyzer.analyze(registry_key, documents, *, context_fingerprint: str).
- Service passes its repository lookup fingerprint to the analyzer.
- Fingerprint versions add citation_resolver.
- Analyzer builds provenance using provider.metadata and safe raw_id.

- [ ] **Step 1: Add failing resolver-driven analyzer tests**

Update the provider double with safe metadata. Assert unique quote creates offsets/checksum/
citation/fingerprint; duplicates are unverified unless local hints select one; wrong provider
page/section is never canonical; resolver failure gives PARTIAL plus a constant warning; strict
structural failure remains INVALID_RESPONSE with zero findings.

- [ ] **Step 2: Add failing service/fingerprint/version tests**

Assert service passes the same fingerprint used for cache lookup. Changing resolver version
changes the fingerprint. Assert schema=3, prompt/analyzer versions advance, and provider-output
schema remains version 1 with no citation/provenance fields.

- [ ] **Step 3: Run and verify RED**

~~~powershell
python -m pytest -q tests/test_ai_document_analyzer.py tests/test_ai_document_analysis_service.py tests/test_ai_document_analysis_repository.py tests/test_ai_output_schema.py
~~~

Expected: old signature, direct substring verification, missing provenance, and missing resolver
fingerprint fail.

- [ ] **Step 4: Integrate resolver and provenance**

~~~python
result = self.analyzer.analyze(
    registry_key,
    documents,
    context_fingerprint=fingerprint,
)
~~~

Resolve every strict candidate locally. Build one provenance per successful provider response
using a local analysis ID, aware UTC time, current constants, provider.metadata, bounded raw_id,
and snapshots from the same documents. Unexpected resolver/provenance exceptions degrade to a
constant safe warning without exception text.

- [ ] **Step 5: Version contracts**

Set AI_PROMPT_VERSION="3", AI_ANALYZER_VERSION="4", and add resolver version to fingerprint.
Prompt says page/section are hints and forbids links, citation IDs, and provenance while
retaining strict bare JSON and exact quote rules.

- [ ] **Step 6: Run Step 3 and verify GREEN**

Expected: all tests pass and output schema remains candidate-only.

- [ ] **Step 7: Commit**

~~~powershell
git add app/core/ai/analyzer.py app/core/ai/prompts.py app/core/ai/repository.py tests/test_ai_document_analyzer.py tests/test_ai_document_analysis_service.py tests/test_ai_document_analysis_repository.py tests/test_ai_output_schema.py
git commit -m "feat(rm-116): bind citations to current analysis"
~~~

### Task 5: Repository Round-Trip and Cache Compatibility

**Files:**
- Modify: app/core/ai/repository.py:75-230
- Test: tests/test_ai_document_analysis_repository.py
- Test: tests/test_ai_document_analysis_service.py

**Interfaces:**
- Consumes version-3 from_payload() and resolver-aware fingerprint.
- Preserves the existing SQLite table and append-only rows.

- [ ] **Step 1: Add failing cache scenarios**

Test current v3 reuse; v2 safe display with no verified evidence; future version incompatible;
checksum invalidation; corrupt provenance skipped; corrupt newest row falling back to previous
valid v3; and current provider failure not replaced by stale success.

- [ ] **Step 2: Retain a no-migration assertion**

Expected columns remain analysis_id, registry_key, context_fingerprint, status, payload_json,
created_at, and payload_version.

- [ ] **Step 3: Run and verify RED**

~~~powershell
python -m pytest -q tests/test_ai_document_analysis_repository.py tests/test_ai_document_analysis_service.py
~~~

- [ ] **Step 4: Harden repository acceptance**

Continue past INVALID_RESPONSE/CACHE_INCOMPATIBLE rows. A reusable v3 result requires valid
provenance whose fingerprint equals the query fingerprint. latest() keeps safe display behavior.
Warnings remain constants and never contain payload/exception text.

- [ ] **Step 5: Run tests and commit**

~~~powershell
python -m pytest -q tests/test_ai_document_analysis_repository.py tests/test_ai_document_analysis_service.py
git add app/core/ai/repository.py tests/test_ai_document_analysis_repository.py tests/test_ai_document_analysis_service.py
git commit -m "feat(rm-116): enforce provenance-aware cache reuse"
~~~

Expected: all tests pass.

### Task 6: RM-107 Current-Citation Eligibility

**Files:**
- Modify: app/tenders/participation_decision_service.py:240-350
- Test: tests/test_participation_decision_service.py
- Test: tests/test_full_analysis_service.py
- Test: tests/test_ai_orchestrator.py
- Test: tests/test_ai_orchestrator_runtime_integration.py

**Interfaces:**
- Consumes analysis.is_current_verified(finding).
- Preserves score, recommendation, confidence, stop-factor order, and current-run result.

- [ ] **Step 1: Add failing decision tests**

Build valid current v3 citation plus legacy, damaged provenance, wrong checksum/fingerprint,
invalid ID, and unverified variants. Only the current valid finding adds AI decision evidence.
A blocked critical stop factor still wins over high score and valid AI risk.

- [ ] **Step 2: Run and verify RED**

~~~powershell
python -m pytest -q tests/test_participation_decision_service.py tests/test_full_analysis_service.py tests/test_ai_orchestrator.py tests/test_ai_orchestrator_runtime_integration.py
~~~

- [ ] **Step 3: Replace both eligibility predicates**

~~~python
verified_ai_findings = (
    tuple(
        item
        for item in (
            *ai_analysis.risks,
            *ai_analysis.suspicious_conditions,
            *ai_analysis.contradictions,
        )
        if ai_analysis.is_current_verified(item)
    )
    if ai_analysis is not None
    else ()
)
~~~

Reuse this tuple for decision evidence and action-plan decisions. Do not alter scoring or policy.

- [ ] **Step 4: Run tests and commit**

~~~powershell
python -m pytest -q tests/test_participation_decision_service.py tests/test_full_analysis_service.py tests/test_ai_orchestrator.py tests/test_ai_orchestrator_runtime_integration.py
git add app/tenders/participation_decision_service.py tests/test_participation_decision_service.py tests/test_full_analysis_service.py tests/test_ai_orchestrator.py tests/test_ai_orchestrator_runtime_integration.py
git commit -m "feat(rm-116): restrict decisions to current citations"
~~~

### Task 7: Safe Citation Navigation in Existing UI

**Files:**
- Modify: app/ui/tender_full_analysis_dialog.py
- Modify: app/ui/tender_documents_dialog.py
- Modify: app/ui/tender_search_ui_controller.py
- Test: tests/test_tender_full_analysis_dialog.py
- Test: tests/test_tender_documents_dialog.py
- Test: tests/test_tender_search_ui_controller.py

**Interfaces:**
- Produces citation_requested = Signal(str, str): registry key and known document ID.
- Produces select_document(document_key: str) -> bool.
- Produces controller open_analysis_citation(registry_key, document_key).

- [ ] **Step 1: Add failing rendering and link tests**

Verified finding shows safe name, local page/section, exact quote, “уверенность AI”, shortened
citation ID, truncation, and corteris-citation://open/<citation_id>. A known link emits current
registry/document. Parameterize file/http/https/data/javascript, UNC-like text, unknown ID,
query, fragment, and userinfo; none may emit.

- [ ] **Step 2: Add selection/controller tests**

~~~python
assert dialog.select_document("doc-2") is True
assert dialog.selected_document().document_key == "doc-2"
assert dialog.select_document("missing") is False
~~~

Controller test asserts the existing dialog is shown and selects the row without invoking
QDesktopServices.openUrl.

- [ ] **Step 3: Run and verify RED**

~~~powershell
python -m pytest -q tests/test_tender_full_analysis_dialog.py tests/test_tender_documents_dialog.py tests/test_tender_search_ui_controller.py
~~~

- [ ] **Step 4: Implement safe lookup and signal**

Disable external links. Build a private map only from analysis.is_current_verified() citations.
Require scheme corteris-citation, host open, empty query/fragment/userinfo, one path component
matching ^cit_[0-9a-f]{32}$, and membership in the map. Emit the mapped document ID, never a
document value parsed from the URL.

- [ ] **Step 5: Implement selection and controller navigation**

select_document refreshes, finds exact key, selects/scrolls the row, and returns bool. Refactor
controller dialog creation into one helper reused by normal and citation navigation. Connect
the existing string documents_requested signal to open_registry_documents rather than the
object-valued open_tender_documents slot.

- [ ] **Step 6: Run tests and commit**

~~~powershell
python -m pytest -q tests/test_tender_full_analysis_dialog.py tests/test_tender_documents_dialog.py tests/test_tender_search_ui_controller.py
git add app/ui/tender_full_analysis_dialog.py app/ui/tender_documents_dialog.py app/ui/tender_search_ui_controller.py tests/test_tender_full_analysis_dialog.py tests/test_tender_documents_dialog.py tests/test_tender_search_ui_controller.py
git commit -m "feat(rm-116): add safe citation navigation"
~~~

### Task 8: Structured JSON and Escaped HTML Sources

**Files:**
- Modify: app/reporting/tender_ai_analysis.py
- Test: tests/test_tender_ai_analysis_export.py
- Test: tests/test_ai_provenance.py

**Interfaces:**
- Consumes analysis.to_payload(), provenance sources, and current citations.
- Produces internal HTML anchors only; JSON remains the canonical payload.

- [ ] **Step 1: Add failing export security tests**

Use malicious statement/quote/section/name, a private storage path, and provider-looking URL.
JSON must contain provenance/source_registry. HTML must escape values and contain only
href="#source-<citation_id>", source anchors, checksum prefix, locator, and citation ID.
Neither output may contain script markup, private paths, file links, or external hrefs.

- [ ] **Step 2: Run and verify RED**

~~~powershell
python -m pytest -q tests/test_tender_ai_analysis_export.py tests/test_ai_provenance.py
~~~

- [ ] **Step 3: Extend the existing exporter**

Keep JSON as analysis.to_payload(). Link only current verified findings to escaped internal
source IDs. Render unverified findings without links. Build Источники from safe snapshots and
citation locators. Escape every untrusted value; never emit local/external URLs.

- [ ] **Step 4: Run tests and commit**

~~~powershell
python -m pytest -q tests/test_tender_ai_analysis_export.py tests/test_ai_provenance.py
git add app/reporting/tender_ai_analysis.py tests/test_tender_ai_analysis_export.py tests/test_ai_provenance.py
git commit -m "feat(rm-116): persist and export analysis provenance"
~~~

### Task 9: Cross-Layer Regression and Acceptance Documents

**Files:**
- Modify: pyproject.toml
- Modify focused tests required by the RM-116 contract if integration reveals gaps
- Modify: docs/RM-116_AUDIT.md
- Modify: docs/RM-116_REQUIREMENTS.md
- Modify: docs/ROADMAP.md
- Modify: docs/STATUS.md
- Modify: docs/ROADMAP_HISTORY.md

**Interfaces:**
- Adds app/core/ai/citations.py, app/core/ai/document_context.py, and
  app/core/ai/repository.py to the fixed mypy contour; schemas.py and analyzer.py remain in it.
- Keeps RM-116 IN PROGRESS and RM-117 planned.

- [ ] **Step 1: Run the exact RM-116 target**

~~~powershell
python -m pytest -q tests/test_ai_citations.py tests/test_ai_provenance.py tests/test_ai_document_schemas.py tests/test_ai_document_analyzer.py tests/test_ai_document_context.py tests/test_ai_document_analysis_repository.py tests/test_ai_document_analysis_service.py tests/test_tender_ai_analysis_export.py tests/test_tender_full_analysis_dialog.py tests/test_tender_documents_dialog.py tests/test_full_analysis_service.py tests/test_ai_orchestrator.py tests/test_ai_orchestrator_runtime_integration.py tests/test_participation_decision_service.py tests/test_openai_compatible_provider.py
~~~

Expected: all pass; record exact count/duration.

- [ ] **Step 2: Run strict/provider/UI regressions**

~~~powershell
python -m pytest -q tests/test_ai_output_schema.py tests/test_ai_provider_selection.py tests/test_ollama_local_mode.py tests/test_tender_search_ui_controller.py
~~~

Expected: strict candidate schema unchanged; metadata safe; Ollama offline/no-keyring.

- [ ] **Step 3: Run the full local quality gate**

~~~powershell
python -m pytest -q
python -m ruff check .
python -m ruff format . --check
python -m mypy
python scripts/check_repository_secrets.py
python -m pip_audit --skip-editable
git diff --check origin/main...HEAD
~~~

Expected: every command succeeds. Record Python version, test/file/mypy counts, durations,
secret result, audit result, and diff result. If pip-audit is blocked only by managed network
policy, request read-only approval and rerun it.

- [ ] **Step 4: Run architecture and leak scans**

Use rg to prove one provider/analyzer/Orchestrator/repository/context builder/exporter, one
production provider call, no second output schema, no Chat Completions/retry/fuzzy/web path,
and no private-path fixture in payload/HTML/log captures. Inspect the full diff for raw
exception/response logging.

- [ ] **Step 5: Record acceptance without closing RM-116**

Add exact results and decisions to audit/requirements. Add ROADMAP implementation acceptance
and a preparation history entry, but retain RM-116 IN PROGRESS and RM-117 planned. State the
feature merge, post-merge gate, and docs closeout remain required.

- [ ] **Step 6: Commit**

~~~powershell
git add pyproject.toml docs/RM-116_AUDIT.md docs/RM-116_REQUIREMENTS.md docs/ROADMAP.md docs/STATUS.md docs/ROADMAP_HISTORY.md
git commit -m "docs(rm-116): prepare stage acceptance"
~~~

### Task 10: Review, Push, and Feature PR

**Files:**
- Review: git diff origin/main...HEAD
- No new production files unless review finds a scoped defect.

- [ ] **Step 1: Perform correctness and doubt-driven review**

Review ambiguity, checksum/fingerprint binding, legacy downgrade, corrupt cache, path isolation,
link validation, escaping, RM-107 eligibility, stop-factor priority, offline behavior, and
single-pipeline architecture. Fix each finding with a regression test.

- [ ] **Step 2: Repeat final verification**

Repeat Task 9 target and quality commands after review fixes. Expected: all pass and
git status --short is empty.

- [ ] **Step 3: Push and open the feature PR**

~~~powershell
git push -u origin feat/rm-116-citations-provenance
~~~

Open non-draft PR titled:

~~~text
feat(rm-116): add verified citations and provenance
~~~

Body lists architecture invariants, payload v3/no migration, exact validation results, and
post-merge/closeout boundary.

- [ ] **Step 4: Monitor PR Quality Gate**

Wait for Python 3.12 and 3.13. Diagnose exact logs and fix only RM-116-owned defects. Do not
mark RM-116 done or activate RM-117.

- [ ] **Step 5: Preserve the closeout stop-line**

After owner merge, verify the merge SHA post-merge gate. Only then create docs-only closeout PR
docs(rm-116): complete citations and provenance stage, mark RM-116 DONE, and activate RM-117.
Do not implement RM-117 in this package.
