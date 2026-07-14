# RM-114 Requirements — OpenAI-compatible Responses API

Status: ACCEPTED
Canonical contract date: 2026-07-14  
Depends on: RM-107, RM-111, RM-112, RM-113

## Goal and architecture invariants

RM-114 hardens the existing `app.ai.provider.OpenAICompatibleProvider` and formalizes its synchronous Responses API contract. The system must continue to have one such provider, one `TenderDocumentAiAnalyzer`, one `TenderAiOrchestrator`, one AI repository, the existing bootstrap DI path, and exactly one production `provider.analyze()` call in `app/core/ai/analyzer.py`.

AI transport output must never override RM-107 score/recommendation or the absolute priority of a critical stop factor. No database, migration, persistence-schema, document-context, tender-adapter, or UI business-logic change is allowed.

## Endpoint and execution

- The only endpoint is `POST {normalized_base_url}/responses`.
- No `/chat/completions` fallback, streaming, background mode, retries/backoff, failover, discovery, or health/connection test is allowed.
- A request is made only from an explicit user-started AI analysis. Construction, bootstrap, settings load, and settings save remain offline.
- The provider may return `retryable=true`, but RM-114 never automatically repeats a POST.

## Request contract

The UTF-8 JSON object contains:

- `model`: the selected model;
- `input`: the current prompt as a `system` message and joined document context as a `user` message;
- every content item has `type: "input_text"`;
- `stream: false`.

Cloud profiles (`openai`, `openai_compatible`) additionally send `store: false`. The Ollama profile uses the same provider but omits `store` and other optional fields outside the confirmed subset. `SYSTEM_PROMPT` and the analysis business schema do not change.

The existing `source[:500000]` provider guard remains unchanged; no competing document truncation policy is introduced. API key, base URL, prompt, document text, and private data must not appear in metadata, user-agent, query strings, logs, warnings, or results.

Required headers are `Content-Type: application/json`, `Accept: application/json`, and (for the current cloud-compatible contract) `Authorization: Bearer <credential>`. Credentials containing control characters are rejected at selection time so no unsafe header can be constructed.

## Transport contract

Implementation remains in `app/ai/provider.py`, uses the standard-library urllib stack, and exposes an injectable opener/factory for offline tests. A default opener must be resolved at runtime so existing monkeypatch-based tests remain valid.

- Timeout must be positive; invalid configuration fails closed without network.
- TLS certificate and hostname verification remain enabled. No insecure SSL context is permitted.
- Redirects are rejected before following them; Authorization is never forwarded to another URL or origin.
- The response body limit defaults to the named constant `4 * 1024 * 1024` bytes and is configurable for tests.
- The implementation reads at most `max_response_bytes + 1` and rejects overflow.
- A successful body is decoded as UTF-8 and parsed as JSON.
- The provider performs one attempt only and does not log URL, headers, request/response body, prompt, documents, credentials, or exception text.

`app/tenders/http_client.py` must not be imported: it is a tender-provider, GET-oriented transport with a different retry/response contract. A shared HTTP-framework refactor is outside RM-114.

## Safe result contract

Success is exactly compatible with:

```json
{"status":"ok","text":"<non-empty model output>","raw_id":"<bounded safe id>"}
```

Failure is exactly compatible with:

```json
{"status":"error","error_code":"<stable code>","message":"<constant safe message>","retryable":false}
```

The closed error-code set is:

- `authentication_error`, `permission_error`, `invalid_request`, `endpoint_not_supported`;
- `request_too_large`, `rate_limited`, `provider_unavailable`;
- `timeout`, `network_error`, `tls_error`, `redirect_rejected`;
- `response_too_large`, `invalid_json`, `invalid_response`;
- `incomplete_response`, `refused`, `empty_output`.

Messages are constant per internal classification. Results and logs never contain an HTTP body, provider error/refusal text, exception text, traceback, header, API key, complete URL/query, local/private path, prompt, document text, or raw payload.

HTTP status mapping is deterministic:

- 400 and 422: `invalid_request`, not retryable;
- 401: `authentication_error`, not retryable;
- 403: `permission_error`, not retryable;
- 404: `endpoint_not_supported`, not retryable;
- 408: `timeout`, retryable;
- 413: `request_too_large`, not retryable;
- 429: `rate_limited`, retryable;
- 500–599: `provider_unavailable`, retryable;
- all other 4xx: `invalid_request`, not retryable;
- all remaining HTTP statuses: `provider_unavailable`, not retryable.

Timeout exceptions map to retryable `timeout`; certificate/TLS failures to non-retryable `tls_error`; redirect attempts to non-retryable `redirect_rejected`; `URLError` and other network/OS failures to `network_error` with retryability limited to timeouts by the preceding rule. No exception text is surfaced.

## Responses parsing contract

1. The parsed value must be a JSON object.
2. A non-null top-level `error` is a safe `provider_unavailable` error; its content is ignored.
3. `status="completed"` is eligible for success. `failed` maps to `provider_unavailable`; `incomplete`, `in_progress`, `cancelled`, and `queued` map to `incomplete_response`. Unknown explicit statuses are `invalid_response`.
4. Absence of `status` is allowed only when valid non-empty output exists and top-level `error` is absent/null.
5. Text is collected only from string `output[*].content[*]` entries with `type="output_text"`, in source order.
6. A non-empty string top-level `output_text` is a compatibility fallback when nested text is absent.
7. Tool calls, reasoning items, unknown item/content types, and non-string text are ignored.
8. A refusal marker without valid output text maps to `refused`; refusal text is discarded.
9. Empty or whitespace-only output maps to `empty_output`.
10. `raw_id` is accepted only as a string, stripped, and bounded to a named fixed limit; absence or an invalid type produces an empty ID, never a raw-payload substitute.

## Configuration boundary

Stable IDs remain `disabled`, `openai`, `openai_compatible`, and `ollama`. Generic compatible base URLs must:

- use only HTTP or HTTPS and include a hostname;
- contain no username, password, query, fragment, control character, or port zero;
- preserve their path and normalize trailing slashes;
- never be echoed in a warning or result.

The official OpenAI URL remains fixed. Ollama remains loopback-only and normalized to `/v1`. Cloud credentials remain solely in Windows Credential Manager/keyring and are absent from config, database, dataclass representation, warnings, and logs.

## Required verification

`tests/test_openai_compatible_provider.py` must directly cover the exact URL/method/headers/body, cloud and Ollama request profiles, no network before `analyze()`, nested/multiple/fallback output, bounded ID, lifecycle statuses, top-level error, refusal, empty output, malformed/non-object/invalid-UTF-8 bodies, body-size limit, HTTP classifications, timeout/URL/TLS/OS errors, redirect rejection, and absence of secrets/raw bodies/URLs/paths/exceptions from results and logs.

Existing provider-selection, Ollama, runtime, analyzer, settings UI, bootstrap, full-analysis, and tender-runtime tests must preserve the offline DI, keyring isolation, current safe provider error, stale-result, single-call/single-graph/shared-repository, RM-107, and stop-factor invariants. `app/ai/provider.py` is added to the mandatory mypy contour.

Acceptance requires the target pytest command, full pytest, Ruff check, Ruff format check, mypy, repository secret scan, `pip-audit --skip-editable`, and `git diff --check` to pass offline. Final acceptance additionally requires the feature merge and post-merge Windows Quality Gate on Python 3.12 and 3.13.

## Explicitly out of scope

- Strict JSON Schema, `text.format`, `response_format`, and the next Tender Intelligence schema (RM-115).
- Citations, links, and provenance (RM-116).
- Specialized technical-specification analysis (RM-117).
- Chat Completions selection, streaming, retries/backoff, failover, model discovery, live connection tests, API-key rotation, UI redesign, new database/migration, or score/recommendation changes.

RM-114 must not be marked accepted/DONE until its feature PR is merged and the post-merge Windows Quality Gate succeeds.

## Local acceptance — 2026-07-14

Implementation was validated from `feat/rm-114-openai-compatible-api` on Python 3.12:

- target pytest contour: `152 passed in 12.19s`;
- full pytest: `863 passed in 67.59s`;
- `python -m ruff check .`: passed;
- `python -m ruff format . --check`: passed (`502 files already formatted`);
- `python -m mypy`: passed (`10 source files`);
- `python scripts/check_repository_secrets.py`: passed;
- `python -m pip_audit --skip-editable`: passed (`No known vulnerabilities found`); the newly created venv's bundled `pip 24.2` was first upgraded to `pip 26.1.2` after the audit identified tool-package advisories;
- `git diff --check`: passed;
- architecture scan: two existing production construction sites, one production `provider.analyze()` call, and no AI import of `app/tenders/http_client.py`.

All provider tests are offline: no live OpenAI/Ollama endpoint, host keyring, API key, or DNS is used. No database or migration was added. Strict JSON Schema, citations/provenance, and RM-115/RM-116/RM-117 behavior remain out of scope and unimplemented.

## Final acceptance — 2026-07-14

Feature PR #30 was merged into `main` as `e4caca0dd8fc45714bb94be160665e961af66313`.
Post-merge Quality Gate run `29315630189` completed successfully on both required matrix
versions: Python 3.12 (`863 passed in 161.88s`) and Python 3.13
(`863 passed in 164.67s`). Ruff check/format, mypy, secret scan, dependency audit, all
smoke stages, and the full suite passed in both jobs.

The accepted implementation adds no database or migration and preserves the single
provider/analyzer/Orchestrator/repository graph, existing bootstrap DI, RM-107
score/recommendation ownership, and critical stop-factor priority. RM-115 behavior was not
implemented. RM-114 satisfies its Definition of Done and is accepted.
