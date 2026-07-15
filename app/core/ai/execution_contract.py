"""Pure identity contract for one Tender Intelligence execution."""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.provider import AiProviderMetadata
from app.core.ai.citations import CITATION_RESOLVER_VERSION
from app.core.ai.document_context import AI_CONTEXT_VERSION
from app.core.ai.output_schema import AI_PROVIDER_OUTPUT_SCHEMA_VERSION
from app.core.ai.prompts import AI_PROMPT_VERSION
from app.core.ai.schemas import AI_ANALYSIS_SCHEMA_VERSION, AiAnalysisProvenance


AI_EXECUTION_CONTRACT_VERSION = "1"
AI_ANALYZER_VERSION = "12"


@dataclass(frozen=True, slots=True)
class AiExecutionContract:
    """Exact, sanitized identity of executable AI semantics."""

    contract_version: str
    prompt_version: str
    provider_output_schema_version: str
    persisted_schema_version: int
    analyzer_version: str
    context_version: str
    citation_resolver_version: str
    provider_id: str
    provider_model: str


def current_execution_contract(provider_metadata: AiProviderMetadata) -> AiExecutionContract:
    """Build the current contract from already sanitized public provider metadata."""
    if not isinstance(provider_metadata, AiProviderMetadata):
        raise TypeError("provider_metadata must be AiProviderMetadata")
    return AiExecutionContract(
        contract_version=AI_EXECUTION_CONTRACT_VERSION,
        prompt_version=AI_PROMPT_VERSION,
        provider_output_schema_version=AI_PROVIDER_OUTPUT_SCHEMA_VERSION,
        persisted_schema_version=AI_ANALYSIS_SCHEMA_VERSION,
        analyzer_version=AI_ANALYZER_VERSION,
        context_version=AI_CONTEXT_VERSION,
        citation_resolver_version=CITATION_RESOLVER_VERSION,
        provider_id=provider_metadata.provider_id,
        provider_model=provider_metadata.model,
    )


def execution_contract_from_provenance(
    provenance: AiAnalysisProvenance | None,
) -> AiExecutionContract | None:
    """Read the execution identity already represented by safe provenance."""
    if not isinstance(provenance, AiAnalysisProvenance):
        return None
    return AiExecutionContract(
        contract_version=AI_EXECUTION_CONTRACT_VERSION,
        prompt_version=provenance.prompt_version,
        provider_output_schema_version=provenance.output_schema_version,
        persisted_schema_version=provenance.persisted_schema_version,
        analyzer_version=provenance.analyzer_version,
        context_version=provenance.context_version,
        citation_resolver_version=provenance.citation_resolver_version,
        provider_id=provenance.provider_id,
        provider_model=provenance.provider_model,
    )


def execution_contract_matches(
    provenance: AiAnalysisProvenance | None,
    expected_contract: AiExecutionContract,
) -> bool:
    """Return exact equality without fuzzy or provider-specific matching."""
    return execution_contract_from_provenance(provenance) == expected_contract


__all__ = [
    "AI_ANALYZER_VERSION",
    "AI_EXECUTION_CONTRACT_VERSION",
    "AiExecutionContract",
    "current_execution_contract",
    "execution_contract_from_provenance",
    "execution_contract_matches",
]
