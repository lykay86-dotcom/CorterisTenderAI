# RM-151 diagnostic correlation contract

## Owner decision

RM-151 adds a small Qt-free correlation index/adapter; it does not add a report database, upload,
telemetry, external support service or retention owner. Crash files remain owned by crash reporting
and catalog services; support bundles remain owned by `DiagnosticSupportBundleService`; database
health/journal evidence remains owned by the workflow health services.

## Correlation identity

`DiagnosticCorrelationId` is opaque, bounded, copy/search friendly and generated from injected
entropy. It encodes no error text, path, subject identity, credential, payload, username or
user-identifying timestamp. It is not an authorization token. The same ID is used in episode,
safe feedback, notification and diagnostic reference.

## Safe diagnostic record

A record contains only:

- correlation ID, operation kind, episode ID and typed reason code;
- aware occurrence time and application/build version;
- bounded structured safe context with closed field names;
- diagnostic owner kind and opaque evidence reference;
- redaction/contract version;
- optional parent correlation ID.

The safe record contains no raw exception, traceback, path, URL query/fragment, SQL, provider body,
credential or file content. Owner-private artifacts may contain policy-approved technical evidence
and are accessed only through the existing owner.

## Registry semantics

- Registration is idempotent for equal ID + fingerprint and rejects conflicting reuse.
- Retrieval is exact ID lookup with no substring/path probing.
- Missing/expired/unavailable evidence returns a new typed safe failure; it never reveals the
  internal reference.
- Dismiss/read of feedback or notification does not delete evidence.
- Retention and deletion remain those of the artifact owner. The correlation index may drop an
  expired reference but cannot delete owner artifacts.
- The default implementation is bounded in-memory/adapter-backed for the application session;
  persistence requires explicit owner evidence and is not introduced in schema v1 notifications.

## Actionable retrieval routes

| Diagnostic kind | Existing owner and safe route |
|---|---|
| crash report | `CrashReportCatalogService`; open existing report center with report identity |
| support bundle | `DiagnosticSupportBundleService`; show safe bundle label/inspection result |
| workflow health | system-health center/journal owner; open health surface |
| collector run | collector run/registry evidence; open canonical collector/registry surface |
| AI/document analysis | existing analysis repository/dialog; open exact RM-149 tender identity |
| generic transient failure | safe record only; no fabricated artifact action |

Routes reuse RM-142 IDs and existing controllers. Action target uses stable identity/freshness, not
path, row number, display title or current selection.

## Support bundle boundary

The support service's own redactor, manifest and inspection remain authoritative. User feedback
shows a neutral bundle label and correlation ID, not an absolute output path. A failed create/open/
inspect operation receives a new correlation while the original record remains intact. Tests use
synthetic reports and roots only.

## Tests

Expected-red covers ID validation, conflicting registration, exact retrieval, missing/expired
evidence, dismissal independence, parent correlation, bounded registry and malicious safe context.
Integration covers crash -> safe feedback -> report center, support bundle success/failure and
workflow health evidence. No test reads live reports, environment secrets or keyring.

