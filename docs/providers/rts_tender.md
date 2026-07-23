# РТС-тендер (`rts_tender`)

Проверено: 23 июля 2026 года. Readiness:
`BLOCKED_EXTERNAL / MACHINE_CONTRACT_REQUIRED`.

- Canonical source: `rts_tender`; homepage: <https://www.rts-tender.ru/>.
- Public human surfaces and user documentation do not provide complete permitted procurement
  collection API/feed contract.
- Endpoint/auth/schema/pagination/rate/timezone/currency/retention and approved fixtures remain
  missing; details: `docs/PRE_RM156_COLLECTOR_P6_RTS_TENDER_ACCESS_AUDIT.md`.
- Fixture capture, adapter and live diagnostic `NOT_RUN`; private protocol/XHR guessing forbidden.
- Disable through existing Provider Manager; rollback does not delete settings, legacy credential
  compatibility, history or provider identity.
