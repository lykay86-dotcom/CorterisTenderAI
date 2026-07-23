# Портал поставщиков Москвы (`mos_supplier`)

Проверено: 23 июля 2026 года. Readiness:
`BLOCKED_EXTERNAL / CREDENTIAL_AND_LIVE_VERIFICATION_REQUIRED`; offline level
`IMPLEMENTED_OFFLINE`.

## Identity and access

- Official portal/API owner: <https://zakupki.mos.ru/>.
- Canonical ID/source: `mos_supplier` / `TenderSource.MOS_SUPPLIER`.
- Official bearer API; token only from existing keyring/environment credential owner.
- Missing token returns `NOT_CONFIGURED` before network.

## Contract and fixtures

- Contract/parser: `mos-supplier-api-v1` / `mos-supplier-api-1`.
- Documentation-derived fixtures:
  `tests/fixtures/mos_supplier_search_documented_contract.json` and card companion.
- Server pagination was not documented and is not guessed; bounded terminal documented scope is
  explicit. Mapping/artifact/checkpoint/redaction evidence:
  `docs/PRE_RM156_COLLECTOR_P4_MOS_SUPPLIER_VALIDATION.md`.

## Live, disable and rollback

Lawful token and live approval отсутствуют; live status `NOT_RUN`. Offline fixture is not a captured
live response and does not grant `WORKING`. Disable through existing Provider Manager. Rollback
does not delete token, settings, artifacts, checkpoints or history.
