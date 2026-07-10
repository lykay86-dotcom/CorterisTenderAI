# Sprint 1.1 — Core Platform

Реализованы:

- `PathManager` для исходников и PyInstaller EXE;
- атомарный `ConfigManager`;
- `ResourceManager`;
- ротационное логирование с фильтром секретов;
- единая версия приложения 1.5.1;
- `StartupContext`;
- исправленный `.spec` без абсолютных путей;
- новый PowerShell-сценарий сборки;
- набор модульных тестов Core.

## Сборка

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\build_exe.ps1
```

Файл результата:

```text
dist\CorterisTenderAI.exe
```
