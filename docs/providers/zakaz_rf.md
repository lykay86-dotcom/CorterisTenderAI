# ZakazRF (`zakaz_rf`)

Проверено: 22 июля 2026 года, Codex, read-only public access audit.

Readiness: `BLOCKED_EXTERNAL`.

## Identity

- Оператор: АО «Агентство по государственному заказу Республики Татарстан» (АО «АГЗРТ»).
- Публичный homepage оператора: <https://www.agzrt.ru/>.
- Публичный homepage площадки: <https://zakazrf.ru/>.
- Canonical provider ID: `zakaz_rf`.
- Предполагаемый trust level после полной приёмки: `OFFICIAL_OPERATOR`.
- Текущий runtime status остаётся `NOT_CONFIGURED`; adapter и working claim отсутствуют.

## Access basis

Официальный сайт публикует HTML-страницу «Сводный реестр извещений» по адресу
<https://zakazrf.ru/NotificationEx>. Однако на дату проверки не найдены опубликованные оператором
API/feed specification, условия разрешённого автоматизированного сбора или лицензия повторного
использования данных. Публичная доступность HTML сама по себе не является таким разрешением.

`robots.txt` (<https://zakazrf.ru/robots.txt>) запрещает, среди прочего, `/Services/`,
`/QueryForms/`, account, document и file paths. Эти paths не исследовались и не должны
использоваться как предполагаемый API. Отсутствие `/NotificationEx` в списке `Disallow` не заменяет
явный access/data-use contract.

Разрешённый тип доступа: **не подтверждён**. Для продолжения нужен опубликованный официальный
machine-readable contract либо письменное подтверждение оператора, разрешающее конкретный
public HTML/feed/API collection contour и хранение необходимых raw artifacts.

## Contract fields

| Поле | Состояние |
|---|---|
| Hostname allowlist | Только catalog baseline: `zakazrf.ru`, `www.zakazrf.ru`; для adapter не утверждён |
| Auth scheme | Не опубликована для разрешённого data access |
| Endpoint paths/templates | Не утверждены; guessed/private endpoints запрещены |
| Pagination/cursor/date window | Не документированы |
| Rate limit / `Retry-After` | Не документированы |
| Response format/encoding | Публичный реестр наблюдался как `text/html; charset=utf-8`; adapter contract отсутствует |
| Source timezone | Не подтверждена |
| Currency semantics | Не подтверждены |
| Field mapping | Не утверждён |
| Documents/archives | Не исследовались: document/file paths ограничены `robots.txt` и contract отсутствует |
| Raw retention permission | Не подтверждена |

## Fixture inventory and redaction

Contract fixtures отсутствуют. Публичная HTML-страница не сохранена в `tests/fixtures`: без
access/schema/retention contract это создало бы ложное доказательство готовности. Во время аудита
не сохранялись cookies, account data, tender bodies, документы или персональные данные.

## Live verification

Статус: `NOT_RUN`. Выполнялись только bounded GET/HEAD проверки публичных страниц без входа,
credentials, CAPTCHA/anti-bot bypass и private endpoint discovery. Это не live verification
adapter-а и не повышает readiness до `FIXTURE_VERIFIED` или `IMPLEMENTED_OFFLINE`.

## Unblock checklist

До expected-red tests и application-кода владелец должен получить от оператора или найти в
официальной опубликованной документации:

1. разрешённый access method и правила повторного использования/хранения;
2. точные hosts, paths, auth и secret handling;
3. schema/versioning, pagination/cursor/date-window и stable identity rules;
4. rate limits, retry/`Retry-After`, response size и encoding;
5. timezone, currency, status/procedure/law и document mapping;
6. минимум один реальный обезличенный positive fixture и fixtures empty/page/error/auth/rate/schema
   drift с redaction approval;
7. raw artifact retention и explicit live diagnostic procedure.

Официальный контакт оператора, опубликованный на <https://www.agzrt.ru/>:
`agzrt@tatar.ru`. Codex не отправлял сообщений и не инициировал внешнюю координацию.

## Disable and rollback

`zakaz_rf` остаётся disabled/not configured через существующий `CollectorProviderManager` и
provider settings owner. Сети при offline composition нет. Этот audit package не меняет schema,
settings, endpoints, credentials или application-код; rollback — revert docs commit. После будущей
реализации аварийное отключение должно использовать тот же existing manager без удаления history,
artifacts или checkpoints.
