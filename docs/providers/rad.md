# Российский аукционный дом / Lot-online (`rad`)

Проверено: 23 июля 2026 года, Codex, official read-only public access audit.

Readiness: `BLOCKED_EXTERNAL`.

## Identity

- Оператор: АО «Российский аукционный дом» (АО «РАД»).
- Homepage: <https://lot-online.ru/>; operator page: <https://auction-house.ru/about/>.
- Canonical provider ID: `rad`; отдельный legacy alias не зарегистрирован.
- Предполагаемый trust level после полной приёмки: `OFFICIAL_OPERATOR`.
- Runtime status остаётся `NOT_CONFIGURED`; native adapter и working claim отсутствуют.

## Access basis

Оператор публикует разделы 44-ФЗ/615 <https://gz.lot-online.ru/> и 223-ФЗ
<https://tender.lot-online.ru/>, public procurement cards, regulations and user manuals.

[Действующее пользовательское соглашение Lot-online от 26 августа 2025 года](https://catalog.lot-online.ru/images/docs/%D0%9F%D0%BE%D0%BB%D1%8C%D0%B7%D0%BE%D0%B2%D0%B0%D1%82%D0%B5%D0%BB%D1%8C%D1%81%D0%BA%D0%BE%D0%B5%20%D1%81%D0%BE%D0%B3%D0%BB%D0%B0%D1%88%D0%B5%D0%BD%D0%B8%D0%B5%20%D0%BE%D1%82%2026.08.2025.pdf)
запрещает автоматические программы для доступа с целью извлечения, сбора, переработки,
копирования или распространения информации сайта/базы данных. Оно также отдельно запрещает без
письменного разрешения администрации скрипты для доступа, сбора информации или взаимодействия с
сайтом и сервисами. Footer 223-ФЗ раздела требует письменного согласия при любом использовании
материалов.

Разрешённый тип доступа для Collector: **не подтверждён и прямо заблокирован до письменного
разрешения**. Public HTML и индексируемые карточки не являются procurement collection contract.
Официальная документация описывает работу пользователей площадки, но не публикует API/feed,
machine schema, rate limits или raw retention permission. `api1.lot-online.ru` отображает обычный
website UI и не считается документированным API.

## Contract fields

| Поле | Состояние |
|---|---|
| Hostname allowlist | Existing baseline: `lot-online.ru`, `www.lot-online.ru`; procurement subdomains не утверждены |
| Auth scheme | User/ES/signature flows documented; Collector auth не разрешён |
| Endpoints | Public HTML sections/cards существуют; machine-readable contract отсутствует |
| Pagination | UI/search behavior наблюдается; bounds/cursor/completeness не документированы для automation |
| Rate limit / `Retry-After` | Не документированы |
| Format/encoding | Public HTML; stable parser schema не подтверждена |
| Timezone | Площадки показывают server/MSK time; source-wide mapping contract отсутствует |
| Currency/mapping | Не утверждены |
| Sections | `gz`, `tender`, `catalog` и другие contours; unified strategy не подтверждена |
| Documents/archives | Public links существуют; automated download/retention не разрешены |
| Raw retention permission | Требуется отдельное письменное разрешение |

## Fixtures and live verification

Contract fixtures отсутствуют и не сохранялись. Выполнялись только bounded read-only проверки
официальных operator/documentation/public-card pages through search/indexed public content. Login,
forms, private endpoints, credentials, CAPTCHA/anti-bot bypass, hidden protocols и массовый сбор
не использовались.

Live status: `NOT_RUN`. Audit browsing не является adapter live verification.

## Unblock checklist

До expected-red tests и application-кода нужны:

1. письменное разрешение automation, procurement collection and raw retention;
2. exact hosts/sections/paths, auth и secret handling;
3. API/feed or permitted stable HTML schema/version and stable external IDs;
4. pagination/date-window, completeness and finite limits;
5. rate/retry/`Retry-After`, size, encoding, timezone and currency;
6. approved redacted positive/empty/page/error/auth/rate/schema-drift fixtures;
7. field/document mapping and explicit live diagnostic procedure.

Официальные контакты на сайтах: `support@lot-online.ru`, `gz@lot-online.ru`. Codex сообщений не
отправлял.

## Disable and rollback

`rad` остаётся disabled/not configured через existing provider manager/settings owner. Generic
credential account `collector.rad.api_key` сохраняется; значение не читалось и не менялось. Audit
package не меняет application code/schema/dependencies; rollback — revert docs commit.
