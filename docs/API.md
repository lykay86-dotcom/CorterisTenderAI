# Внутренний API и расширения

## Connector
`search(criteria) -> list[TenderSummary]`
`fetch_metadata(external_id) -> TenderPayload`
`download_documents(external_id, target_dir) -> list[Path]`

Коннектор обязан соблюдать правила площадки, не обходить CAPTCHA/2FA и поддерживать rate limit.

## AI Provider
`analyze(prompt, documents) -> structured JSON`. Ответ валидируется Pydantic-схемой. Любой вывод должен иметь source_document/page/quote; иначе помечается как неподтверждённый.

## Добавление площадки
Создать модуль `app/connectors/<name>.py`, реализовать интерфейс Connector, добавить конфигурацию, unit-тесты на фикстурах и регистрацию в фабрике.
