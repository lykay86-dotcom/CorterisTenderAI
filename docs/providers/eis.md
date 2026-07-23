# ЕИС (`eis`)

Проверено: 23 июля 2026 года. Readiness:
`BLOCKED_EXTERNAL / LIVE_VERIFICATION_NOT_APPROVED`; offline level `IMPLEMENTED_OFFLINE`.

## Identity and access

- Official public source: <https://zakupki.gov.ru/>.
- Canonical ID/source: `eis` / `TenderSource.EIS`.
- Connection mode: bounded public HTML fallback, не official API.
- CAPTCHA/access-denied/structure drift fail closed; обход ограничений запрещён.

## Contract and fixtures

- Contract/parser: `eis-public-html-v1` / `eis-search-v3`.
- Approved offline fixtures: `tests/fixtures/eis/`.
- Pagination, response size, checkpoint, artifact, cancellation and provenance bounds приняты в
  `docs/PRE_RM156_COLLECTOR_P4_EIS_VALIDATION.md`.
- Dates remain timezone-aware; money remains Decimal; unsupported data is not invented.

## Live, disable and rollback

Live canary `NOT_RUN`: отдельное разрешение на external request отсутствует. Health response без
полного C19 evidence не даёт `WORKING`. Disable через existing Provider Manager. Rollback —
revert P4 adapter package без schema downgrade или удаления artifacts/checkpoints/history.
