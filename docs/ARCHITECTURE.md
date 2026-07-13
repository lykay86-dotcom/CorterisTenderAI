# Архитектура CorterisTenderAI

## Слои
1. UI.
2. Application Services.
3. Domain.
4. Repositories.
5. Infrastructure.
6. Source/Provider Adapters.

## Границы
- UI не рассчитывает риск, цену, решение и лицензионные права.
- Domain не зависит от PySide6, HTTP и SQLite.
- Каждый источник имеет отдельный адаптер.
- AI получает только подготовленный контекст.
- Каждый вывод хранит provenance.
- Платные функции проверяются central entitlement service.

## Данные
- Decimal для денег.
- Timezone-aware datetime.
- Неизвестное значение не равно нулю.
- Отсутствие сведений не означает отрицательный результат.
