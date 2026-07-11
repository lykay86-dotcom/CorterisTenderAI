"""Built-in tender provider adapters."""

from app.tenders.providers.eis import (
    EisAccessBlockedError,
    EisHtmlParser,
    EisParseError,
    EisProviderConfig,
    EisTenderProvider,
)
from app.tenders.providers.placeholders import (
    PlaceholderTenderProvider,
    create_builtin_providers,
)

__all__ = [
    "EisAccessBlockedError",
    "EisHtmlParser",
    "EisParseError",
    "EisProviderConfig",
    "EisTenderProvider",
    "PlaceholderTenderProvider",
    "create_builtin_providers",
]
