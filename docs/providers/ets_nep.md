# ETS/НЭП (`ets_nep`)

Проверено: 23 июля 2026 года, Codex, official read-only identity/access audit.

Readiness: `BLOCKED_EXTERNAL / IDENTITY_REAUDIT_REQUIRED`.

## Identity

- Оператор: АО «Электронные торговые системы» (АО «ЭТС»).
- Legacy homepage: <https://www.etp-ets.ru/>; it redirects to <https://44.fabrikant.ru/>.
- Current platform: <https://www.fabrikant.ru/> and <https://44.fabrikant.ru/>.
- Repository IDs `ets_nep` and `fabrikant` currently describe the same operator platform after the
  official 1 February 2025 domain/account migration.
- Runtime remains `NOT_CONFIGURED`; no native adapter or working claim exists.

`ets_nep` cannot receive a second adapter. A separate audited identity package must decide legacy
alias/storage compatibility with `fabrikant` before provider implementation.

## Access basis

Official public human search and cards exist, but no public procurement API/feed or explicitly
permitted stable HTML collection contract was found. Fabrikant `robots.txt` disallows explicit
XML/CSV export actions and file/download paths. Rate, pagination/completeness, schema/version,
timezone/currency, document and raw-retention/reuse rules are not published for Collector.

No fixture or live request was captured. Login, private paths, credentials, disallowed exports,
CAPTCHA/anti-bot bypass and bulk collection were not used.

## Unblock checklist

1. reconcile `ets_nep` and `fabrikant` identity/history/settings/credentials;
2. obtain permitted API/feed or stable HTML contract and exact section coverage;
3. document schema/version, pagination/completeness, rate/retry and normalization;
4. approve raw response/document retention and redacted fixtures;
5. define one adapter owner, live diagnostic, disable and rollback path.

`ets_nep` and `fabrikant` remain disabled placeholders. Audit rollback is a docs-only revert.
