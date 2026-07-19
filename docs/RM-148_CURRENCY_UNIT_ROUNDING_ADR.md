# RM-148 ADR — currency, unit and rounding

Status: accepted for implementation. Date: 19.07.2026.

## Decision

Legacy workflow v2 is RUB (audit variant A). Evidence is the accepted RM-145 `Decimal, RUB` KPI
contract plus production workflow input, table, detail, import/export headers/templates and number
formats, all of which expose only RUB. A v2 record is migrated to explicit `currency: "RUB"`.
Future/foreign/mixed codes fail closed; tender FX contracts are not reused to convert workflow data.

Money uses unit `MONEY`; margin uses `PERCENTAGE_POINT` (`15.00` means 15%); counters use `COUNT`.
Chart series and exports carry both stable unit and currency code; glyph `₽` is presentation only.

Rounding mode is `ROUND_HALF_UP`. Rounding occurs only at named persistence/presentation
boundaries. Inputs with scale >2 are rejected before commit; exact calculations retain all Decimal
digits until the named boundary. Aggregates sum first and round once. Excel numeric cells are
display projections; exact canonical text metadata is authoritative.

## Literal tie expectations

| Exact calculation | Money projection |
|---|---|
| `1.005` | `1.01` |
| `2.675` | `2.68` |
| `10.115` | `10.12` |
| `999999999.995` | `1000000000.00` |

Negative money is outside the current domain. Negative zero normalizes to `0.00`. RUB full display
uses two fractional digits; compact Dashboard display may abbreviate only when exact text remains
available. JSON/CSV use fixed-point strings and `RUB`; XLSX includes `RUB` and exact text metadata.

## Rejected alternatives

- Binary float: loses canonical cents and lexical evidence.
- Inferring/combining arbitrary currencies: no workflow FX contract.
- `ROUND_HALF_EVEN` inherited from Python/Qt/Excel: product behavior would be implicit.
- Rounding each contributor: breaks sum parity.
- Storing both float and Decimal as equal sources: creates conflict without an owner.

