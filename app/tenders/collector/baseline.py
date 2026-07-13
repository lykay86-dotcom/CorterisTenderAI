"""Read-only architecture baseline for Corteris Tender Collector.

This module performs no network requests and does not modify application data.
It records the current provider and service graph so collector changes can be
introduced incrementally without breaking the existing tender workflow.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.tenders.provider_registry import TenderProviderRegistry
from app.tenders.search_runtime import TenderSearchRuntime


COLLECTOR_ARCHITECTURE_VERSION = 1


@dataclass(frozen=True, slots=True)
class CollectorProviderBaseline:
    """Provider metadata captured without checking the external source."""

    provider_id: str
    display_name: str
    source: str
    implementation_status: str
    enabled: bool
    priority: int
    supports_search: bool
    supports_details: bool
    supports_documents: bool
    requires_authentication: bool
    public_api: bool


@dataclass(frozen=True, slots=True)
class CollectorArchitectureBaseline:
    """Compatibility snapshot of the existing tender subsystem."""

    version: int
    providers: tuple[CollectorProviderBaseline, ...]
    has_search_engine: bool
    has_tender_registry: bool
    has_document_store: bool
    has_text_extraction: bool
    has_requirement_analysis: bool

    @property
    def provider_ids(self) -> tuple[str, ...]:
        return tuple(item.provider_id for item in self.providers)

    @property
    def implemented_provider_ids(self) -> tuple[str, ...]:
        return tuple(
            item.provider_id
            for item in self.providers
            if item.implementation_status != "placeholder"
        )

    @property
    def placeholder_provider_ids(self) -> tuple[str, ...]:
        return tuple(
            item.provider_id
            for item in self.providers
            if item.implementation_status == "placeholder"
        )


def build_collector_baseline(
    registry: TenderProviderRegistry,
    *,
    runtime: TenderSearchRuntime | None = None,
) -> CollectorArchitectureBaseline:
    """Build a deterministic, side-effect-free architecture snapshot."""

    providers = tuple(
        CollectorProviderBaseline(
            provider_id=entry.id,
            display_name=entry.provider.descriptor.display_name,
            source=entry.provider.descriptor.source.value,
            implementation_status=(entry.provider.descriptor.implementation_status),
            enabled=entry.enabled,
            priority=entry.priority,
            supports_search=(entry.provider.descriptor.capabilities.search),
            supports_details=(entry.provider.descriptor.capabilities.tender_details),
            supports_documents=(entry.provider.descriptor.capabilities.documents),
            requires_authentication=(entry.provider.descriptor.capabilities.authentication),
            public_api=(entry.provider.descriptor.capabilities.public_api),
        )
        for entry in registry.list_registered()
    )

    return CollectorArchitectureBaseline(
        version=COLLECTOR_ARCHITECTURE_VERSION,
        providers=providers,
        has_search_engine=(runtime is not None and runtime.engine is not None),
        has_tender_registry=(runtime is not None and runtime.tender_registry is not None),
        has_document_store=(runtime is not None and runtime.document_store is not None),
        has_text_extraction=(runtime is not None and runtime.text_extraction_service is not None),
        has_requirement_analysis=(
            runtime is not None and runtime.requirement_analysis_service is not None
        ),
    )


__all__ = [
    "COLLECTOR_ARCHITECTURE_VERSION",
    "CollectorArchitectureBaseline",
    "CollectorProviderBaseline",
    "build_collector_baseline",
]
