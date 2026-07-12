# Collector C12 — финальная стабилизация и Windows Release Pipeline

## Исправления

- исправлен Inno Setup: удалён несуществующий OneDir wildcard, вызывавший
  ошибку `No files found matching dist\CorterisTenderAI\*`;
- PyInstaller явно включает `certifi/cacert.pem`, metadata сетевых библиотек и
  динамические backend-модули;
- `assets`, `data` и `config` включаются только при наличии, а `templates`
  остаётся обязательным ресурсом;
- добавлена Windows version information для EXE;
- TLS-контекст использует системное доверенное хранилище и certifi без
  отключения проверки сертификатов;
- добавлен build preflight и автономный frozen self-test;
- создаётся SHA-256 manifest EXE, установщика и self-test отчёта;
- build-зависимости вынесены в `requirements-build.txt`;
- сборка принимает Python 3.12 и 3.13 x64 согласно `pyproject.toml`.

## Frozen self-test

Ключ запуска:

```text
CorterisTenderAI.exe --self-test --self-test-output <report.json>
```

Проверка запускается до импорта Qt-интерфейса и не обращается к внешним сайтам.
Код возврата `0` означает успешную проверку, `1` — обнаруженную проблему.

## Известные ограничения

- реальная доступность ЕИС и Портала поставщиков проверяется отдельно, поскольку
  release self-test намеренно не использует внешнюю сеть;
- API коммерческих площадок остаются в честном состоянии `not_configured`, пока
  не получены договор, ключ и подтверждённый API-контракт;
- установщик не подписан сертификатом Authenticode;
- планировщик Collector работает, пока запущено настольное приложение;
- RAR и 7Z не извлекаются внешними исполняемыми архиваторами.
