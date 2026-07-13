"""Исключения слоя хранения данных."""


class DatabaseError(RuntimeError):
    """Базовая ошибка базы данных приложения."""


class DatabaseNotInitializedError(DatabaseError):
    """База данных ещё не была инициализирована."""


class EntityNotFoundError(DatabaseError):
    """Запрошенная сущность не найдена."""


class DuplicateEntityError(DatabaseError):
    """Нарушено ограничение уникальности сущности."""
