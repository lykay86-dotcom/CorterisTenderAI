from __future__ import annotations

from email.message import Message
import io
import json
import ssl
import urllib.error

import pytest

from app.ai.provider import (
    AiProviderMetadata,
    MAX_RAW_RESPONSE_ID_LENGTH,
    OpenAICompatibleProvider,
)


class Response:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.read_limit: int | None = None

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        self.read_limit = limit
        return self.body[:limit]


class RecordingOpener:
    def __init__(self, payload: object) -> None:
        self.response = Response(json.dumps(payload).encode("utf-8"))
        self.calls: list[tuple[object, float]] = []

    def __call__(self, request: object, *, timeout: float) -> Response:
        self.calls.append((request, timeout))
        return self.response


def _provider(opener: object, **kwargs: object) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        "secret-key",
        "https://api.example.test/v1/",
        "gpt-test",
        opener=opener,  # type: ignore[arg-type]
        **kwargs,  # type: ignore[arg-type]
    )


def _success(**extra: object) -> dict[str, object]:
    return {
        "id": "resp-1",
        "status": "completed",
        "output": [{"content": [{"type": "output_text", "text": "result"}]}],
        **extra,
    }


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


def _error_code(result: dict[str, object]) -> str:
    assert result["status"] == "error"
    assert set(result) == {"status", "error_code", "message", "retryable"}
    return str(result["error_code"])


def _output_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "name": "corteris_tender_analysis_v1",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
            "additionalProperties": False,
        },
    }


def test_exact_cloud_request_contract_and_no_network_before_analyze() -> None:
    opener = RecordingOpener(_success())
    provider = _provider(opener)

    assert opener.calls == []
    result = provider.analyze("system prompt", ["document one", "document two"])

    assert result == {"status": "ok", "text": "result", "raw_id": "resp-1"}
    assert len(opener.calls) == 1
    request, timeout = opener.calls[0]
    assert request.full_url == "https://api.example.test/v1/responses"  # type: ignore[attr-defined]
    assert request.get_method() == "POST"  # type: ignore[attr-defined]
    headers = {key.casefold(): value for key, value in request.header_items()}  # type: ignore[attr-defined]
    assert headers == {
        "authorization": "Bearer secret-key",
        "content-type": "application/json",
        "accept": "application/json",
    }
    assert timeout == 120.0
    assert json.loads(request.data.decode("utf-8")) == {  # type: ignore[attr-defined]
        "model": "gpt-test",
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": "system prompt"}]},
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "document one\n\n--- ДОКУМЕНТ ---\ndocument two",
                    }
                ],
            },
        ],
        "stream": False,
        "store": False,
    }


def test_cloud_request_forwards_exact_text_format_once_without_mutation() -> None:
    opener = RecordingOpener(_success())
    provider = _provider(opener)
    output_format = _output_format()
    original = json.loads(json.dumps(output_format))

    result = provider.analyze("system prompt", ["document"], output_format=output_format)

    assert result["status"] == "ok"
    assert len(opener.calls) == 1
    request, _timeout = opener.calls[0]
    body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
    assert body["text"] == {"format": original}
    assert "response_format" not in body
    assert output_format == original


def test_ollama_profile_omits_unconfirmed_optional_fields() -> None:
    opener = RecordingOpener(_success())
    provider = _provider(opener, store_response=None, supports_text_format=False)

    provider.analyze("prompt", ["context"], output_format=_output_format())

    request, _timeout = opener.calls[0]
    body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
    assert body["stream"] is False
    assert "store" not in body
    assert "text" not in body
    assert "response_format" not in body
    assert set(body) == {"model", "input", "stream"}


def test_provider_failure_never_exposes_output_format() -> None:
    secret_schema_marker = "private-schema-marker"

    def fail(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.HTTPError(
            "https://private.example/path?token=private",
            400,
            "private provider message",
            Message(),
            io.BytesIO(b"private response"),
        )

    output_format = _output_format()
    output_format["schema"] = {"description": secret_schema_marker}

    result = _provider(fail).analyze(
        "private prompt",
        ["private document"],
        output_format=output_format,
    )

    assert _error_code(result) == "invalid_request"
    assert secret_schema_marker not in repr(result)
    assert "private prompt" not in repr(result)
    assert "private document" not in repr(result)


def test_nested_output_text_parts_keep_stable_order_and_ignore_other_types() -> None:
    opener = RecordingOpener(
        {
            "status": "completed",
            "output": [
                {
                    "type": "reasoning",
                    "content": [
                        {"type": "reasoning_text", "text": "private reasoning"},
                        {"type": "output_text", "text": "first"},
                    ],
                },
                {"type": "tool_call", "content": [{"type": "tool_result", "text": "tool"}]},
                {"content": [{"type": "output_text", "text": "second"}]},
            ],
        }
    )

    result = _provider(opener).analyze("prompt", ["context"])

    assert result == {"status": "ok", "text": "first\nsecond", "raw_id": ""}
    assert "private reasoning" not in repr(result)
    assert "tool" not in repr(result)


def test_top_level_output_text_is_a_compatible_fallback_without_status() -> None:
    result = _provider(RecordingOpener({"output_text": " compatible result "})).analyze(
        "prompt", ["context"]
    )

    assert result == {"status": "ok", "text": "compatible result", "raw_id": ""}


def test_raw_id_is_string_only_stripped_bounded_and_control_safe() -> None:
    long_id = f"  {'x' * (MAX_RAW_RESPONSE_ID_LENGTH + 20)}  "
    bounded = _provider(RecordingOpener(_success(id=long_id))).analyze("prompt", ["context"])
    non_string = _provider(RecordingOpener(_success(id=123))).analyze("prompt", ["context"])
    control = _provider(RecordingOpener(_success(id="private\nvalue"))).analyze(
        "prompt", ["context"]
    )

    assert bounded["raw_id"] == "x" * MAX_RAW_RESPONSE_ID_LENGTH
    assert non_string["raw_id"] == ""
    assert control["raw_id"] == ""


@pytest.mark.parametrize(
    ("status", "code"),
    [
        ("failed", "provider_unavailable"),
        ("incomplete", "incomplete_response"),
        ("in_progress", "incomplete_response"),
        ("cancelled", "incomplete_response"),
        ("queued", "incomplete_response"),
        ("unknown", "invalid_response"),
    ],
)
def test_non_completed_explicit_status_is_not_success(status: str, code: str) -> None:
    result = _provider(RecordingOpener(_success(status=status))).analyze("prompt", ["context"])

    assert _error_code(result) == code


def test_explicit_completed_status_is_success() -> None:
    assert _provider(RecordingOpener(_success())).analyze("prompt", ["context"])["status"] == ("ok")


def test_top_level_error_is_sanitized() -> None:
    secret = "provider-body-secret"
    result = _provider(RecordingOpener({"error": {"message": secret}})).analyze(
        "prompt", ["context"]
    )

    assert _error_code(result) == "provider_unavailable"
    assert secret not in repr(result)


def test_refusal_without_output_is_sanitized() -> None:
    refusal = "private refusal explanation"
    result = _provider(
        RecordingOpener(
            {
                "status": "completed",
                "output": [{"content": [{"type": "refusal", "refusal": refusal}]}],
            }
        )
    ).analyze("prompt", ["context"])

    assert _error_code(result) == "refused"
    assert refusal not in repr(result)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"status": "completed", "output": []},
        {"output_text": "   "},
        {"output": [{"content": [{"type": "output_text", "text": 123}]}]},
    ],
)
def test_empty_or_invalid_output_is_not_success(payload: object) -> None:
    assert _error_code(_provider(RecordingOpener(payload)).analyze("prompt", ["context"])) == (
        "empty_output"
    )


@pytest.mark.parametrize("body", [b"{broken", b"\xff\xfe"])
def test_malformed_json_or_invalid_utf8_is_safe(body: bytes) -> None:
    response = Response(body)

    result = _provider(lambda *_args, **_kwargs: response).analyze("prompt", ["context"])

    assert _error_code(result) == "invalid_json"


@pytest.mark.parametrize("payload", [[], "text", 123, None])
def test_json_array_or_scalar_is_invalid_response(payload: object) -> None:
    result = _provider(RecordingOpener(payload)).analyze("prompt", ["context"])

    assert _error_code(result) == "invalid_response"


def test_response_body_is_read_once_with_max_plus_one_and_rejected_on_overflow() -> None:
    response = Response(b"x" * 17)
    provider = _provider(lambda *_args, **_kwargs: response, max_response_bytes=16)

    result = provider.analyze("prompt", ["context"])

    assert response.read_limit == 17
    assert _error_code(result) == "response_too_large"


@pytest.mark.parametrize(
    ("http_status", "code", "retryable"),
    [
        (400, "invalid_request", False),
        (401, "authentication_error", False),
        (403, "permission_error", False),
        (404, "endpoint_not_supported", False),
        (408, "timeout", True),
        (413, "request_too_large", False),
        (422, "invalid_request", False),
        (429, "rate_limited", True),
        (500, "provider_unavailable", True),
        (503, "provider_unavailable", True),
    ],
)
def test_http_status_is_classified_without_reading_body(
    http_status: int, code: str, retryable: bool, caplog
) -> None:
    raw_body = b"provider body token=private"

    def fail(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.HTTPError(
            "https://private.example/path?token=private",
            http_status,
            "private provider message",
            Message(),
            io.BytesIO(raw_body),
        )

    result = _provider(fail).analyze("private prompt", ["private document"])

    assert _error_code(result) == code
    assert result["retryable"] is retryable
    rendered = repr(result) + caplog.text
    assert "provider body" not in rendered
    assert "private.example" not in rendered
    assert "token=" not in rendered
    assert "private prompt" not in rendered
    assert "private document" not in rendered


@pytest.mark.parametrize(
    ("exception", "code", "retryable"),
    [
        (TimeoutError("private timeout path"), "timeout", True),
        (urllib.error.URLError("private DNS detail"), "network_error", False),
        (urllib.error.URLError(TimeoutError("private")), "timeout", True),
        (ssl.SSLError("private TLS detail"), "tls_error", False),
        (urllib.error.URLError(ssl.SSLError("private")), "tls_error", False),
        (OSError("C:\\Users\\private\\secret.txt"), "network_error", False),
    ],
)
def test_network_failures_are_sanitized(
    exception: BaseException, code: str, retryable: bool, caplog
) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise exception

    provider = _provider(fail)
    result = provider.analyze("private prompt", ["private document"])

    assert _error_code(result) == code
    assert result["retryable"] is retryable
    rendered = repr(result) + repr(provider) + caplog.text
    assert "secret-key" not in rendered
    assert "private prompt" not in rendered
    assert "private document" not in rendered
    assert "Users" not in rendered
    assert "private DNS" not in rendered


def test_default_transport_installs_reject_redirect_handler(monkeypatch, caplog) -> None:
    calls: list[str] = []

    class RedirectingOpener:
        def open(self, request: object, *, timeout: float) -> object:
            calls.append(request.full_url)  # type: ignore[attr-defined]
            raise urllib.error.HTTPError(
                request.full_url,  # type: ignore[attr-defined]
                302,
                "redirect to https://evil.example/?token=private",
                Message(),
                None,
            )

    def fake_build_opener(*handlers: object) -> RedirectingOpener:
        assert len(handlers) == 1
        assert type(handlers[0]).__name__ == "_RejectRedirectHandler"
        return RedirectingOpener()

    monkeypatch.setattr("urllib.request.build_opener", fake_build_opener)
    result = OpenAICompatibleProvider(
        "secret-key", "https://api.example.test/v1", "gpt-test"
    ).analyze("prompt", ["document"])

    assert calls == ["https://api.example.test/v1/responses"]
    assert _error_code(result) == "redirect_rejected"
    assert "evil.example" not in repr(result) + caplog.text
    assert "secret-key" not in repr(result) + caplog.text


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"timeout": 0}, "timeout must be positive"),
        ({"max_response_bytes": 0}, "max_response_bytes must be positive"),
    ],
)
def test_invalid_transport_limits_fail_before_network(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        OpenAICompatibleProvider("secret", "https://api.example/v1", "model", **kwargs)


@pytest.mark.parametrize("credential", ["", "secret\n", "secret\x7fvalue"])
def test_unsafe_credential_never_constructs_request_header(credential: str) -> None:
    calls: list[object] = []

    def opener(*args: object, **_kwargs: object) -> object:
        calls.extend(args)
        raise AssertionError("network must stay disabled")

    result = OpenAICompatibleProvider(
        credential,
        "https://api.example/v1",
        "model",
        opener=opener,
    ).analyze("prompt", ["document"])

    assert calls == []
    assert _error_code(result) == "authentication_error"
