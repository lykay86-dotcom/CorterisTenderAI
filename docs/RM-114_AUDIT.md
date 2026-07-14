# RM-114 Audit — Existing OpenAI-compatible Transport

Status: completed before application-code changes  
Audit date: 2026-07-14  
Baseline branch: `feat/rm-114-openai-compatible-api`  
Baseline HEAD: `8edd84228f93e62ff6c4b96bce91ae8ec2f5d668` (`Merge pull request #29 from lykay86-dotcom/docs/rm-113-completion`)

## Baseline validation

- RM-114 target contour before the new provider test: `97 passed in 7.32s`.
- Full baseline: `808 passed in 61.41s`.
- Both runs were offline and used Python 3.12 in the isolated RM-114 worktree.

## Existing architecture

`app/ai/provider.py` defines the existing `AIProvider`, `DisabledProvider`, and the only HTTP AI adapter, `OpenAICompatibleProvider`. The adapter is synchronous, uses `urllib.request`, joins the supplied document strings, retains the existing `source[:500000]` defensive context limit, and returns a mapping consumed by the current analyzer.

There are exactly two production construction sites, both in `AiProviderSelectionService._resolve()` in `app/core/ai/provider_selection.py`:

1. Ollama creates `OpenAICompatibleProvider(OLLAMA_AUTH_PLACEHOLDER, normalized_loopback_url, model)`.
2. Official OpenAI and generic `openai_compatible` create the same provider with the keyring credential and selected base URL.

The only production source occurrence of `provider.analyze()` is `TenderDocumentAiAnalyzer.analyze()` in `app/core/ai/analyzer.py`. The bootstrap resolves the provider in `_create_ai_runtime()` and injects it through `create_tender_search_runtime()`. No network operation occurs during construction, bootstrap, settings load, or settings save. Tests contain direct calls only for transport fixtures and invariant checks.

The existing runtime retains one `TenderDocumentAiAnalyzer`, one `TenderAiOrchestrator`, and the shared AI repository. RM-107 remains the owner of score and recommendation, and critical stop factors remain authoritative. A second provider, analyzer, orchestrator, repository, Decision Engine, or AI pipeline is therefore neither necessary nor permitted.

## Current request and response behavior

Before RM-114 hardening, `OpenAICompatibleProvider.analyze()`:

- sends `POST {base_url.rstrip('/')}/responses`;
- sends `Authorization: Bearer <credential>` and `Content-Type: application/json`;
- encodes UTF-8 JSON containing `model` and two `input_text` messages: the prompt as `system`, and joined documents as `user`;
- does not explicitly send `Accept`, `stream=false`, or cloud `store=false`;
- uses `urllib.request.urlopen(request, timeout=self.timeout)`;
- performs no explicit timeout validation, response-size bound, response content-type check, or redirect restriction;
- parses UTF-8 JSON without first requiring a JSON object;
- collects nested `output[*].content[*]` items whose type is `output_text`;
- does not classify top-level `error`, lifecycle `status`, refusal, empty output, malformed shapes, or a top-level `output_text` compatibility field;
- returns the response `id` without type or length bounds.

The request has the existing 500,000-character provider-side context guard, but there is no explicit serialized request-size limit. The response is currently read without a limit. Automatic redirects are currently inherited from the default urllib opener, so an Authorization-bearing request is not protected by an explicit no-redirect policy. The default timeout is 120 seconds but non-positive values are not rejected. TLS uses Python's verified default context; no insecure SSL context exists.

## Current sanitization boundary and gaps

Provider selection already keeps cloud credentials in the existing keyring adapter, excludes secrets from settings/repository dataclasses, and degrades to `DisabledProvider` on secret-store errors. Warnings are constant and do not echo invalid provider IDs, URLs, private paths, or secret-store exception text.

The transport boundary is not yet safe: an `HTTPError` returns up to 1,000 characters of the raw response body, and other exceptions return `str(exc)`. Those values can disclose provider messages, URLs/query strings, paths, or other private data. RM-114 must replace them with stable internal codes, constant messages, and a boolean `retryable` flag. It must not log or return request/response bodies, headers, credentials, URLs, prompts, documents, exception text, or tracebacks.

## Configuration compatibility

Stable provider IDs already are `disabled`, `openai`, `openai_compatible`, and `ollama`.

- `openai` is pinned to `https://api.openai.com/v1` and uses the keyring credential.
- `openai_compatible` uses a configured HTTP(S) base URL and the same keyring credential.
- `ollama` uses the same provider, requires a loopback HTTP(S) URL normalized to `/v1`, and never reads the cloud credential.

Generic URL validation already rejects non-HTTP(S), missing hostname, user info, fragments, and malformed ports, but it still permits query strings, port zero, and control characters. It also normalizes by string trimming instead of a canonical URL helper. RM-114 must close those gaps while preserving the configured path and removing trailing slashes. Ollama's stricter loopback normalization remains intact.

A cloud credential is stripped when loaded but is not currently rejected for embedded control characters; such a credential could form an unsafe header. RM-114 must disable the provider before any request can be constructed.

Cloud requests need `stream=false` and `store=false`. Ollama requests need `stream=false` but must omit optional fields outside its confirmed compatibility subset, including `store`. This is a request profile on the existing provider, not a new adapter.

## Existing test contour

- `tests/test_ai_provider_selection.py`: stable IDs, keyring isolation, safe degradation, official/custom URL selection, secret-free configuration and representations.
- `tests/test_ollama_local_mode.py`: loopback-only normalization, no cloud credential access, save/bootstrap offline behavior, existing Responses endpoint fixture.
- `tests/test_ai_provider_runtime_integration.py`: bootstrap injection, current provider errors, one AI graph/shared repository, and the single direct production provider call.
- `tests/test_ai_document_analyzer.py`: safe provider-disabled/error/invalid-response behavior and evidence normalization.
- `tests/test_ai_provider_settings_ui.py`: stable UI values, key clearing/isolation, save without HTTP, official URL lock, and Ollama settings behavior.
- `tests/test_bootstrap_tender_search_integration.py`, `tests/test_full_analysis_service.py`, and `tests/test_tender_analysis_runtime_integration.py`: composition-root, stale-success, RM-107, and end-to-end safe-degradation invariants.

RM-114 adds direct transport/security coverage in `tests/test_openai_compatible_provider.py`; existing tests change only where the request contract or selection validation changes.

## Transport ownership decision

`app/tenders/http_client.py` is intentionally not imported. It belongs to tender-source providers and exposes a GET-oriented `HttpTransport.get()` with tender-specific retry and response abstractions. RM-114 requires one non-retried Authorization-bearing POST to the Responses API. Moving or generalizing that transport would broaden the stage into a cross-domain HTTP refactor without improving the required AI boundary.

## Audit conclusion

The existing provider and DI graph are the correct extension points. RM-114 will harden `app/ai/provider.py` and minimally strengthen `app/core/ai/provider_selection.py`; it will not create another transport/pipeline, alter persistence or schemas, change UI business logic, modify document-context rules, or affect RM-107/RM-111 decisions.
