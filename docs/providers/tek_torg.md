# ТЭК-Торг (`tek_torg`)

Проверено: 23 июля 2026 года, Codex, official read-only public access audit.

Readiness: `BLOCKED_EXTERNAL`.

## Identity

- Оператор: АО «ТЭК-Торг».
- Homepage: <https://www.tektorg.ru/>.
- Canonical provider ID: `tek_torg`; отдельный legacy alias не зарегистрирован.
- Предполагаемый trust level после полной приёмки: `OFFICIAL_OPERATOR`.
- Runtime status остаётся `NOT_CONFIGURED`; native adapter и working claim отсутствуют.

## Access basis

Официальный <https://api.tektorg.ru/> публикует unauthenticated discovery document и называет
`/procedures` публичным разделом экспорта процедур. Документированные
<https://api.tektorg.ru/procedures>, <https://api.tektorg.ru/procedures/wsdl>,
<https://api.tektorg.ru/lists/sections> и <https://api.tektorg.ru/lists/types> подтверждают SOAP
operation, filters, page fields/totals and reference dictionaries. Это разрешённая основа для
дальнейшего contract audit, а не guessed endpoint.

Отдельный SOAP-регламент внешней интеграции использует integration login/password token и
user-scoped customer operations. Он не подменяет public-export contract и не подтверждает, что
существующий generic `collector.tek_torg.api_key` соответствует будущей auth schema.

Публичные документы не определяют rate/retry limits, maximum page size and snapshot consistency,
schema/version lifecycle, exact timezone/currency/money semantics, raw response/document retention
or reuse rights. Поэтому доступ к metadata подтверждён, но разрешённый production Collector
contract ещё не полон.

## Contract fields

| Поле | Состояние |
|---|---|
| Hostname allowlist | Existing baseline only `tektorg.ru`, `www.tektorg.ru`; `api.tektorg.ru` не добавлен до implementation package |
| Auth scheme | Public export appears unauthenticated; separate customer SOAP token is out of scope |
| Endpoint | Official WSDL advertises `https://api.tektorg.ru/procedures/soap` |
| Filters | Publication/update windows, section, registry numbers, type and organizer/customer INN |
| Pagination | `limitPage`, `page`, current/total pages and total procedures; bounds/maximum/consistency missing |
| Rate/retry | Не опубликованы; inspected responses had no rate headers |
| Format/encoding | SOAP/XML, UTF-8 WSDL; schema version policy missing |
| Timezone | `xsd:dateTime`; source-wide offset/default rules not published |
| Currency/money | Currency string; price fields are `xsd:float`, exact decimal semantics not published |
| Sections | Official section dictionary exists; completeness/change policy missing |
| Documents | WSDL fields exist; retention/reuse and download semantics not approved |
| Raw retention permission | Не подтверждена |

## Fixtures and live verification

Contract fixtures отсутствуют и не сохранялись. Audit read only discovery metadata, WSDL,
reference dictionaries, public pages and `robots.txt`. No procedure SOAP request, login, form,
private endpoint, credentials, CAPTCHA/anti-bot bypass, hidden protocol or bulk collection was used.

Live status: `NOT_RUN`. Audit metadata access не является adapter live verification.

## Unblock checklist

До fixture/tests/application-кода нужны:

1. documented rate/concurrency/retry behavior;
2. page bounds/default/max and snapshot/completeness rules;
3. schema/version/change-notification and section-coverage contract;
4. timezone/currency/exact-money and stable field/status/document mapping;
5. written raw response/document retention and reuse rules;
6. approved redacted positive/empty/page/error/rate/schema-drift fixtures;
7. explicit live diagnostic and rollback procedure.

Официальный support contact: `help@tektorg.ru`. Codex сообщений не отправлял.

## Disable and rollback

`tek_torg` остаётся disabled/not configured через existing provider manager/settings owner.
Generic credential account `collector.tek_torg.api_key` сохраняется; значение не читалось и не
менялось. Audit package не меняет application code/schema/dependencies; rollback — revert docs
commit.
