# OTC (`otc`)

Проверено: 23 июля 2026 года. Readiness:
`BLOCKED_EXTERNAL / PUBLIC_HTML_WITHOUT_MACHINE_CONTRACT`.

- Canonical source: `otc`; homepage: <https://otc.ru/>.
- Public search/card HTML and account CRM/EIS integration do not provide an external procurement
  discovery API/feed or automation/reuse permission.
- Schema/pagination/completeness/rate/timezone/currency/retention and approved fixtures are absent;
  evidence: `docs/PRE_RM156_COLLECTOR_P7_OTC_ACCESS_AUDIT.md`.
- HTML/XHR reverse engineering, login, bulk collection, fixture capture and live diagnostic
  `NOT_RUN`.
- Disable through existing Provider Manager; rollback is docs-only and preserves settings,
  credentials, identity and history.
