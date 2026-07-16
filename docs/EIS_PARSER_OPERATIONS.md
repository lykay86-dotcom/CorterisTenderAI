# Эксплуатация парсера ЕИС

## Режим работы

Провайдер `eis` использует только публичный HTML `zakupki.gov.ru` через общий
`AsyncHttpClient`. Он не обходит CAPTCHA, HTTP 403 и rate limits, не использует браузер,
cookies или авторизацию. Основной parser version search-карточек — `eis-search-v3`;
detail versions — `eis-notice-44-v1` и `eis-notice-223-v1`, документы —
`eis-documents-v2`.

## Health

`AsyncEisTenderProvider.check_health_components()` делает один минимальный search request
и возвращает два независимых статуса:

- `network_status`: HTTP/transport доступность публичной выдачи;
- `parser_status`: распознавание page type, container и обязательной структуры.

`check_health()` агрегирует худший статус в совместимый `ProviderHealth`. Probe не пишет
checkpoint или registry, не запускает AI и не загружает документы.

Типичные случаи:

| Network | Parser | Значение |
|---|---|---|
| available | available | сеть и HTML contract исправны |
| available | degraded | ЕИС ответила, но parser обнаружил drift/maintenance |
| unavailable | unknown | parser не запускался из-за transport/HTTP failure |
| degraded | degraded | получена CAPTCHA/страница защиты, обход запрещён |

## Structural errors

`EisParserStructureChangedError` означает fail-closed остановку: заявленный `total` без
карточек, нулевая/низкая доля разбора, неизвестная page/law, maintenance/error page или
отсутствие обязательных detail fields. Такая ошибка не должна превращаться в корректную
пустую выдачу. `EisAccessBlockedError` означает CAPTCHA/403; повтор с обходом защиты
запрещён. `EisUnsafeUrlError` означает, что URL не прошёл allowlist.

## Snapshots

Snapshots выключены по умолчанию. Для диагностического экземпляра передайте
`snapshot_directory=Path(<data_directory>)` в `AsyncEisTenderProvider`. Файлы появятся в:

```text
<data_directory>/collector/debug/eis/YYYY-MM-DD/
```

Сохраняются body HTML, allowlisted metadata и sanitized error text. Writer API не принимает
headers/cookies/Authorization; metadata keys вне allowlist отбрасываются. Перед передачей
snapshot третьим лицам всё равно выполните ручную проверку содержимого публичной страницы.

## Live canary

Явный ручной запуск:

```powershell
python scripts/check_eis_parser_live.py --search "оборудование" --limit 10
```

Canary выполняет ровно один публичный search request, печатает JSON, не пишет registry,
не запускает AI и не загружает documents/detail pages. Exit code `0` означает успешный
разбор, `1` — typed network/parser failure. Запуск не входит в offline CI и требует
разрешённого сетевого доступа.

## Offline проверка

```powershell
python -m pytest -q tests/test_eis_parser_stage1.py tests/test_eis_parser.py `
  tests/test_eis_provider.py tests/test_collector_eis_async_provider.py
python -m ruff check app/tenders/providers/eis.py `
  app/tenders/providers/eis_async.py app/tenders/providers/eis_parser `
  scripts/check_eis_parser_live.py
```

Fixtures в `tests/fixtures/eis/` являются единственным входом unit/integration tests; тесты
не обращаются к live ЕИС.
