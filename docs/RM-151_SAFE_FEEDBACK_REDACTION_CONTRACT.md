# RM-151 safe feedback and redaction contract

## Verdict

User-visible feedback is an allowlist projection, never `str(exception)`, raw provider body,
traceback, path or arbitrary context. Existing technical artifacts remain with their accepted
diagnostic owners and are not rewritten by the presentation sanitizer.

## Values and projection boundary

`SafeText` is a validated bounded value, not a type alias. `SafeFeedback` contains an opaque
feedback ID, episode ID, severity, safe title/summary, typed reason code, ordered typed actions,
optional diagnostic correlation ID, aware occurrence time and markup-free accessible text.

Every boundary classifier maps `(exception type, typed owner result, allowlisted context)` to:

1. a closed reason code;
2. severity;
3. a static localized template;
4. typed allowlisted fields;
5. retry/cancel/recovery policy;
6. optional safe diagnostic record/correlation.

Free-form message substring parsing may add defense-in-depth but cannot determine the only reason
code. Unknown input becomes generic `INTERNAL_ERROR` with a correlation ID.

## Reason catalog

The shared minimum catalog is `OFFLINE`, `TIMEOUT`, `CANCELLED_BY_USER`, `SOURCE_UNAVAILABLE`,
`AUTH_REQUIRED`, `PERMISSION_DENIED`, `VALIDATION_FAILED`, `CONFLICT`, `STALE_TARGET`,
`UNSUPPORTED_SCHEMA`, `DATA_DAMAGED`, `STORAGE_UNAVAILABLE`, `DEPENDENCY_UNAVAILABLE` and
`INTERNAL_ERROR`. Domain-specific reason enums map explicitly and remain owned by their services.

## Forbidden user-visible data

The following must not occur in labels, dialogs, status bar, notifications, accessible text,
clipboard safe summary or user feedback export:

- credentials, authorization/cookie values, keyring/environment secrets or secret-shaped values;
- Windows/Unix absolute paths, usernames in profile paths or DB connection strings;
- URL query/fragment, raw request/response body, SQL or traceback;
- file contents or unbounded `repr`/mapping/collection values;
- raw HTML/script/style/event attributes;
- control characters and bidi overrides that alter reading order.

Allowed values are closed kind/reason labels, bounded safe subject labels, validated host without
credentials/query/fragment, stable safe action names and opaque correlation IDs.

## Allowlist-first algorithm

1. Classify at the existing owner boundary.
2. Select a static template for typed reason code.
3. Insert only typed allowlisted fields.
4. Apply Unicode normalization and remove/visualize forbidden controls/bidi marks.
5. For typed URL fields retain only validated HTTPS host when policy permits; for path fields use
   a neutral artifact label.
6. Bound title, summary, field count and each inserted value.
7. Produce plain text; if a static rich wrapper is required, HTML-escape every dynamic fragment.
8. Build separate markup-free accessible text.
9. Run postcondition marker/secret/path/query/HTML scan.
10. On any uncertainty return the generic safe template and correlation ID.

Regex replacement is only a final defense. Sanitization must be idempotent and deterministic for
equal typed input and logical clock.

## Rich text and clipboard

Plain text is the default. Dynamic data is never passed to `setHtml` or auto-rich-text labels.
Permitted links are static action controls backed by validated HTTPS or internal RM-142 routes;
`javascript:`, `file:`, `data:`, relative external and credential-bearing links are rejected.
Clipboard uses the same safe plain-text projection, not widget text containing diagnostics.

## Malicious characterization and expected-red fixture

The synthetic fixture combines these markers without using live data:

```text
RM151_FAKE_OPENAI_CREDENTIAL_DO_NOT_USE
Authorization: Bearer FAKE_TOKEN
C:\Users\Yuri\secret\config.json
/home/alice/.config/corteris/secret.env
https://example.invalid/api?t=FAKE_SECRET&user=alice#fragment
postgresql://alice:password@localhost/private
<script>alert(1)</script><img src=x onerror=alert(2)>
TRACEBACK_MARKER / SQL_MARKER / ENV_MARKER / U+202E
```

Characterization must prove at least one legacy projection can expose a marker. Expected-red then
requires every safe projection surface to exclude all forbidden markers while its correlation ID
still resolves an actionable safe diagnostic record. The test scans title, summary, accessible
text, notification DTO, status/clipboard projection and exported feedback.

## Static guard

A bounded source guard will reject new direct `str(exc/error/exception)` or `repr` passed into
user-facing setters/message boxes/status bars, dynamic `setHtml`, keyring reads from presenter/
notification modules and imports of PySide6 in the Qt-free core. Existing legacy candidates are
allowlisted by exact audited file/symbol and reduced as representative migrations land; the guard
must not silently bless new occurrences.

## Residual boundary

Explicit crash/report diagnostic views may show the already scrubbed traceback from the existing
crash owner after user action. That text is diagnostic evidence, not the safe summary, and is not
copied into notification/status/accessibility projections. Complete privacy/support-policy review
of every internal artifact remains separate from UI redaction.
