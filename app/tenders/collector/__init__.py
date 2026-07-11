"""Corteris Tender Collector integration namespace.

The package is intentionally side-effect free at import time. Network clients,
provider checks and schedulers are created only by an explicit composition
root in later collector commits.
"""

from app.tenders.collector.baseline import (
    COLLECTOR_ARCHITECTURE_VERSION,
    CollectorArchitectureBaseline,
    CollectorProviderBaseline,
    build_collector_baseline,
)

__all__ = [
    "COLLECTOR_ARCHITECTURE_VERSION",
    "CollectorArchitectureBaseline",
    "CollectorProviderBaseline",
    "build_collector_baseline",
]
