# Roseltorg (`roseltorg`)

Проверено: 23 июля 2026 года, Codex, read-only public access audit.

Readiness: `BLOCKED_EXTERNAL`.

## Identity

- Оператор: АО «Единая электронная торговая площадка» (АО «ЕЭТП»).
- Homepage: <https://www.roseltorg.ru/>.
- Canonical provider ID: `roseltorg`; `roseltorg_commercial` остаётся только legacy alias.
- Предполагаемый trust level после полной приёмки: `OFFICIAL_OPERATOR`.
- Runtime status остаётся `NOT_CONFIGURED`; native adapter и working claim отсутствуют.

## Access basis

Оператор публикует HTML-поиск <https://www.roseltorg.ru/procedures/search>, HTML-карточки
`/procedure/<id>` и [документы/регламенты](https://www.roseltorg.ru/knowledge_db/docs/documents).
`robots.txt` (<https://www.roseltorg.ru/robots.txt>) явно допускает
`/procedures/search?page=`, но это правило индексации не является лицензией на повторное
использование/хранение данных и не определяет production collection contract.

На дату проверки не опубликованы API/feed для procurement notices, schema/versioning, rate limits,
raw retention permission или единый contract для государственных, 223-ФЗ, коммерческих и
корпоративных секций. Найденная официальная документация API относится к отдельному платному
продукту электронного документооборота и не разрешает использовать его как tender data API.

Разрешённый тип доступа для Collector: **не подтверждён**. Требуется официальный procurement
API/feed contract либо письменное разрешение на конкретный public HTML contour и хранение raw
artifacts.

## Contract fields

| Поле | Состояние |
|---|---|
| Hostname allowlist | Catalog baseline: `roseltorg.ru`, `www.roseltorg.ru`; adapter allowlist не утверждён |
| Auth scheme | Не опубликована для procurement data access |
| Endpoints | Public HTML search/detail наблюдаются; machine-readable contract отсутствует |
| Pagination | HTML `?page=` индексируется; bounds/cursor/completeness не документированы |
| Rate limit / `Retry-After` | Не документированы |
| Format/encoding | Public pages: `text/html; charset=UTF-8`; stable parser schema не подтверждена |
| Timezone | Карточки показывают GMT+3/МСК, но source-wide contract не подтверждён |
| Currency/mapping | Не утверждены |
| Sections | Много section subdomains; одна schema/strategy не подтверждена |
| Documents/archives | Публичные ссылки существуют; download/retention contract не подтверждён |
| Raw retention permission | Не подтверждена |

## Fixtures and live verification

Contract fixtures отсутствуют. HTML bodies не сохранены в Git: без access/schema/retention
contract это создало бы ложное доказательство готовности. Выполнялись только bounded GET/HEAD
проверки homepage, robots, sitemap, public search/detail и documentation page; login, forms,
private endpoints, credentials, CAPTCHA/anti-bot bypass и массовый сбор не использовались.

Live status: `NOT_RUN`. Audit requests не являются adapter live verification.

## Unblock checklist

До expected-red tests и application-кода нужны:

1. procurement data-use/access и raw retention permission;
2. exact hosts/sections/paths, auth и secret handling;
3. schema/version, stable external ID и section strategy;
4. pagination/cursor/date-window, completeness и finite limits;
5. rate/retry/`Retry-After`, size, encoding, timezone и currency;
6. approved real redacted positive/empty/page/error/auth/rate/schema-drift fixtures;
7. field/document mapping и explicit live diagnostic procedure.

Официальный контакт на сайте: `info@roseltorg.ru`. Codex сообщений не отправлял.

## Disable and rollback

`roseltorg` остаётся disabled/not configured через existing provider manager/settings owner.
Legacy credential account `collector.roseltorg_commercial.api_key` сохраняется; значение не
читалось и не менялось. Audit package не меняет application code/schema/dependencies; rollback —
revert docs commit.
