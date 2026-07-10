# Sprint 1.2.1 — Database Core

Реализована новая локальная платформа данных:

- SQLAlchemy 2.x и SQLite WAL;
- UUID первичные ключи;
- soft delete и восстановление;
- версия каждой записи;
- Company, AppSetting, AuditLog;
- совместимые Tender, Document, Analysis;
- Repository Pattern и Unit of Work;
- версионирование схемы;
- идемпотентный seed ООО «КОРТЕРИС»;
- резервное копирование SQLite;
- подготовка к PostgreSQL.

## Путь базы

База создаётся в пользовательском каталоге, определяемом `PathManager`, а не рядом с EXE и не в Program Files.

## Проверка

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
