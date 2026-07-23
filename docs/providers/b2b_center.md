# B2B-Center (`b2b_center`)

Проверено: 23 июля 2026 года. Readiness:
`BLOCKED_EXTERNAL / CONTRACT_AND_PERMISSION_GATED`.

- Canonical source: `b2b_center`; homepage: <https://www.b2b-center.ru/>.
- Machine access and data reuse require a confirmed contract/permission; public pages do not grant
  it.
- Endpoint/auth/schema/pagination/rate/timezone/currency/retention and approved fixtures remain
  missing; evidence: `docs/PRE_RM156_COLLECTOR_P7_B2B_CENTER_ACCESS_AUDIT.md`.
- Registration/login, fixture capture, adapter and live diagnostic `NOT_RUN`; anti-bot/private
  endpoint bypass forbidden.
- Disable through existing Provider Manager; rollback does not delete settings/credentials/history.
