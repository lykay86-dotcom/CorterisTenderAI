# Сборка Corteris Tender AI 1.5.1 для Windows

## Требования

- Windows 10 или Windows 11 x64;
- Python 3.12 или Python 3.13 x64;
- Inno Setup 6 для создания установщика;
- доступ к PyPI для первой установки зависимостей;
- свободное место не менее 4 ГБ.

Финальную сборку следует выполнять из чистого состояния Git. Скрипт по
умолчанию запускает полный набор тестов и проверяет собранный EXE до создания
установщика.

## Полная сборка

Откройте PowerShell в корне проекта:

```powershell
cd C:\CorterisTenderAI_1_5_1
powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1
```

Этапы:

1. проверка структуры проекта;
2. проверка Python x64;
3. установка runtime- и build-зависимостей;
4. build preflight;
5. `compileall`;
6. полный `pytest`;
7. PyInstaller OneFile;
8. автономный `--self-test` собранного EXE;
9. Inno Setup;
10. создание SHA-256 manifest.

## Результаты

```text
dist\CorterisTenderAI.exe
dist\frozen_self_test.json
dist\build_manifest.json
installer\output\CorterisTenderAI_Setup_x64.exe
logs\build_<дата>.log
logs\build_preflight_<дата>.json
```

## Сборка только EXE

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1 -SkipInstaller
```

Пропуск тестов или frozen self-test разрешён только для локальной диагностики:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1 `
    -SkipTests `
    -SkipFrozenSmokeTest `
    -SkipInstaller
```

Такую сборку нельзя считать финальной.

## Пересоздание виртуального окружения

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1 -RecreateVenv
```

## Ручной preflight

```powershell
.\.venv\Scripts\python.exe scripts\validate_build_environment.py `
    --output .\logs\manual_preflight.json
```

Preflight не выполняет сетевые запросы к тендерным площадкам.

## Ручной self-test EXE

```powershell
powershell -ExecutionPolicy Bypass `
    -File .\scripts\run_frozen_smoke_test.ps1 `
    -ExePath .\dist\CorterisTenderAI.exe `
    -ReportPath .\dist\manual_self_test.json
```

Проверяются зависимости, шаблоны, writable-пути, сертификаты, схема SQLite,
провайдеры Collector и безопасная распаковка ZIP. Внешняя сеть не используется.

## Сертификаты

Проверка TLS не отключается. Приложение загружает системные корневые
сертификаты Windows и дополняет их пакетом `certifi`, включённым в PyInstaller.
Для корпоративного центра сертификации можно задать:

```powershell
$env:CORTERIS_CA_BUNDLE = "C:\Certificates\company-ca.pem"
```

Путь должен указывать на существующий PEM-файл. `verify=False` не применяется.

## Проверка manifest

```powershell
Get-Content .\dist\build_manifest.json -Raw | ConvertFrom-Json
Get-FileHash .\dist\CorterisTenderAI.exe -Algorithm SHA256
Get-FileHash .\installer\output\CorterisTenderAI_Setup_x64.exe -Algorithm SHA256
```

Хеши должны совпадать со значениями в manifest.

## Установка на другом компьютере

1. перенесите `CorterisTenderAI_Setup_x64.exe`;
2. сравните SHA-256 с manifest;
3. запустите установщик от имени администратора;
4. запустите программу;
5. откройте «Тендеры → Источники тендеров»;
6. выполните проверку ЕИС;
7. добавьте bearer-токен Портала поставщиков через переменную окружения или
   защищённое хранилище;
8. выполните демонстрационный поиск до включения планировщика.

Пользовательские базы и документы сохраняются в каталогах `platformdirs`, а не
рядом с EXE, поэтому обновление приложения не должно удалять рабочие данные.
