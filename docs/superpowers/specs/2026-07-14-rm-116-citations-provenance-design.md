# RM-116 Verified Citations and Provenance — Design

Date: 2026-07-14
Status: approved in conversation; pending written-spec review
Canonical requirements: `docs/RM-116_REQUIREMENTS.md`
Audit: `docs/RM-116_AUDIT.md`

## Purpose

Tender Intelligence currently verifies only that a candidate quote occurs somewhere in a
known document. RM-116 makes verification auditable: every verified finding receives a local
exact-match locator, stable citation ID, source snapshot, and current-run provenance. AI can
suggest evidence but cannot assert verification or create canonical citation fields.

## Chosen approach

Use one domain-owned resolver and extend existing immutable domain schemas. Add a small public
provider metadata contract rather than embedding configuration in transport responses or
expanding runtime DI with a parallel provenance context.

Alternatives rejected:

- Adding provider metadata to every `analyze()` response would mix transport data with stable
  provider identity and make disabled/error responses part of provenance design.
- Injecting a separate provenance service through bootstrap would duplicate context already
  owned by the analysis service and add unnecessary runtime wiring.

## Components

### Provider metadata

`AiProviderMetadata` is an immutable, sanitized value exposed through `AIProvider.metadata`.
Provider selection supplies stable IDs (`disabled`, `openai`, `openai_compatible`, `ollama`)
and model names. The analyzer reads only this public contract and the existing safe response
ID; it never reads internal provider attributes.

### Citation resolver

`app/core/ai/citations.py` contains the only resolver. It accepts strict candidate evidence,
the already-built documents, and the current fingerprint. It validates checksum/confidence,
finds exact occurrences, derives enclosing markers, resolves ambiguity only with locally
confirmed hints, and returns verified `AiEvidence` or a closed safe failure reason.

The resolver is deterministic and pure. It performs no filesystem, provider, repository,
network, or UI access.

### Provenance and schemas

`AiEvidence` gains canonical citation fields. `AiSourceSnapshot` captures safe source metadata.
`AiAnalysisProvenance` binds snapshots and version contracts to one analysis ID and current
fingerprint. `AiDocumentAnalysis` owns optional provenance and serializes a source registry.

Payload version 3 is the first version eligible for RM-116 verification. Legacy versions are
readable but always downgraded to unverified findings.

### Analysis data flow

1. The context builder produces sanitized `AiDocument` values from extracted text.
2. The analysis service calculates the versioned context fingerprint.
3. Cache reuse is attempted only for that exact fingerprint.
4. The analyzer sends the unchanged RM-115 strict output format to the provider once.
5. Structurally valid candidate findings enter the local resolver.
6. The analyzer builds current provenance from the fingerprint, versions, public provider
   metadata, safe response ID, and source snapshots.
7. The service persists the normalized result in the existing append-only payload table.
8. RM-107, UI, and exporters consume normalized citations and never re-resolve evidence.

### UI and exports

The AI tab renders an internal link containing only a validated citation ID. A local lookup in
the current analysis converts it to a known document ID and emits a signal. The controller
opens the existing document dialog and selects the matching row through a narrow presentation
API. It does not automatically open the file.

HTML export uses document-source anchors within the report. JSON exposes structured citations,
provenance, and source registry. Both surfaces escape or structurally serialize untrusted text
and never expose paths, file URLs, provider URLs, prompts, or raw documents/responses.

## Failure policy

- Structural provider-output failure remains `INVALID_RESPONSE` with no findings.
- Candidate evidence failure creates an `UNVERIFIED` finding and a constant safe warning.
- Resolver/provenance exceptions are isolated and cannot stop deterministic full analysis.
- Missing/damaged provenance cannot promote a finding or permit cache reuse.
- Future payloads are `CACHE_INCOMPATIBLE`; damaged newest rows do not block an older safe row.
- Current provider failure is returned for the current run and is never replaced by stale
  success.

## Security boundaries

The AI domain receives basename-only display names and logical source references. A regression
fixture using `C:\Users\SecretUser\Documents\tender.pdf` must prove that the path cannot reach
payload JSON, repository JSON, HTML, UI HTML, warnings, or logs. Internal citation handlers
allow only the application scheme and known citation IDs. `file`, HTTP(S), `data`, JavaScript,
UNC, userinfo, query, fragment, and arbitrary provider links are rejected.

## Testing strategy

Implementation follows TDD in slices: resolver, provenance/schema round-trip, analyzer/service
integration, cache compatibility, RM-107 eligibility, UI navigation, and exporters. Each slice
adds focused failing tests before production code and keeps the full suite runnable.

Final proof includes the required target contour, full pytest, Ruff check/format, expanded
mypy contour, secret scan, dependency audit, and diff check. Tests remain offline and isolated
from Windows Credential Manager and saved credentials.

## Scope boundary

No database migration, fuzzy matching, OCR, web verification, new viewer, new AI workflow,
new scoring, recommendation change, retry/failover/streaming, Chat Completions fallback, or
RM-117 functionality is part of this design.
