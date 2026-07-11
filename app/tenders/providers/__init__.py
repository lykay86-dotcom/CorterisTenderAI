"""Built-in tender provider adapters."""

from app.tenders.providers.placeholders import (
    PlaceholderTenderProvider,
    create_builtin_providers,
)

__all__ = [
    "PlaceholderTenderProvider",
    "create_builtin_providers",
]
