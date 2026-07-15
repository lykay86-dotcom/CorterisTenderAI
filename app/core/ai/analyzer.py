"""Safe adapter from an AI provider to evidence-first Tender Intelligence."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import math
import re
from typing import Any, Mapping, TypeVar, cast
from uuid import uuid4

from app.ai.provider import AIProvider, MAX_RAW_RESPONSE_ID_LENGTH
from app.core.ai.citations import CITATION_RESOLVER_VERSION, resolve_citation
from app.core.ai.competition_review import assess_competition_conditions
from app.core.ai.document_context import AI_CONTEXT_VERSION, TenderDocumentContextBuilder
from app.core.ai.financial_risk import assess_financial_risks
from app.core.ai.legal_risk import assess_legal_risks
from app.core.ai.output_schema import (
    AI_PROVIDER_OUTPUT_SCHEMA_VERSION,
    build_responses_text_format,
    decode_and_validate_provider_output,
)
from app.core.ai.prompts import AI_PROMPT_VERSION, SYSTEM_PROMPT
from app.core.ai.repository import (
    AI_ANALYZER_VERSION,
    AiDocumentAnalysisRepository,
    context_fingerprint,
)
from app.core.ai.schemas import (
    AI_ANALYSIS_SCHEMA_VERSION,
    AiApplicationRequirementsStatus,
    AiAnalysisProvenance,
    AiAnalysisStatus,
    AiDocument,
    AiDocumentAnalysis,
    AiDraftContractAnalysis,
    AiDraftContractStatus,
    AiFinding,
    AiFindingStatus,
    AiSourceSnapshot,
    AiTechnicalSpecificationAnalysis,
    AiTechnicalSpecificationStatus,
    TenderRequirements,
    _APPLICATION_REQUIREMENTS_FINDING_FIELDS,
)
from app.core.document_classification import (
    APPLICATION_REQUIREMENTS_SOURCE_KINDS,
    DocumentKind,
)


MAX_SUMMARY_LENGTH = 12_000
MAX_STATEMENT_LENGTH = 4_000
MAX_QUOTE_LENGTH = 8_000
MAX_SECTION_LENGTH = 1_000
_MAX_PROVIDER_ID_LENGTH = 80
_MAX_PROVIDER_MODEL_LENGTH = 200
_RESOLVER_FAILURE_WARNING = "Citation evidence could not be resolved safely."
_PROVENANCE_FAILURE_WARNING = "Provenance metadata could not be recorded safely."
_PUBLIC_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_MODEL_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*(?:[/:][A-Za-z0-9][A-Za-z0-9._-]*)*")
_CREDENTIAL_WORDS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "bearer",
        "credential",
        "password",
        "secret",
        "token",
    }
)
_CREDENTIAL_PREFIXES = tuple(sorted(_CREDENTIAL_WORDS))


class TenderDocumentAiAnalyzer:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def analyze(
        self,
        registry_key: str,
        documents: tuple[AiDocument, ...],
        *,
        context_fingerprint: str,
    ) -> AiDocumentAnalysis:
        if not documents:
            return AiDocumentAnalysis(
                registry_key,
                "No documents available.",
                missing_documents=("Tender documentation",),
                status=AiAnalysisStatus.NO_DOCUMENTS,
                requirements=TenderRequirements(status=AiApplicationRequirementsStatus.NOT_FOUND),
                technical_specification=AiTechnicalSpecificationAnalysis(
                    status=AiTechnicalSpecificationStatus.NOT_FOUND
                ),
                draft_contract=AiDraftContractAnalysis(status=AiDraftContractStatus.NOT_FOUND),
            )
        try:
            response = self.provider.analyze(
                SYSTEM_PROMPT,
                [self._render(item) for item in documents],
                output_format=build_responses_text_format(),
            )
        except Exception:
            return _safe_failure(registry_key, AiAnalysisStatus.PROVIDER_ERROR, documents)
        if not isinstance(response, Mapping):
            return _safe_failure(registry_key, AiAnalysisStatus.INVALID_RESPONSE, documents)
        try:
            provider_status = response.get("status")
            if provider_status == "disabled":
                return _safe_failure(registry_key, AiAnalysisStatus.PROVIDER_DISABLED, documents)
            if provider_status != "ok":
                return _safe_failure(registry_key, AiAnalysisStatus.PROVIDER_ERROR, documents)
        except Exception:
            return _safe_failure(registry_key, AiAnalysisStatus.PROVIDER_ERROR, documents)

        try:
            payload = decode_and_validate_provider_output(response.get("text"))
        except Exception:
            return _safe_failure(registry_key, AiAnalysisStatus.INVALID_RESPONSE, documents)
        if payload is None:
            return _safe_failure(registry_key, AiAnalysisStatus.INVALID_RESPONSE, documents)
        result = self._normalize(
            registry_key,
            payload.model_dump(),
            documents,
            context_fingerprint,
        )
        try:
            raw_response_id = response.get("raw_id")
            provenance = self._build_provenance(
                documents,
                context_fingerprint=context_fingerprint,
                provider_response_id=_provider_response_reference(raw_response_id),
            )
        except Exception:
            return _add_warning(
                _without_verified_findings(result),
                _PROVENANCE_FAILURE_WARNING,
            )
        result = replace(result, provenance=provenance)
        result = replace(result, legal_risk_assessment=assess_legal_risks(result))
        result = replace(result, financial_risk_assessment=assess_financial_risks(result))
        return replace(
            result,
            competition_assessment=assess_competition_conditions(result),
        )

    def _build_provenance(
        self,
        documents: tuple[AiDocument, ...],
        *,
        context_fingerprint: str,
        provider_response_id: str,
    ) -> AiAnalysisProvenance:
        metadata = self.provider.metadata
        sources = tuple(
            sorted(
                (
                    AiSourceSnapshot(
                        document_id=document.document_id,
                        display_name=document.name,
                        document_type=document.document_type,
                        checksum_sha256=document.checksum_sha256,
                        verification_status=document.verification_status,
                        received_at=document.received_at,
                        truncated=document.truncated,
                        included_character_count=len(document.text),
                        original_character_count=max(
                            len(document.text),
                            document.original_character_count,
                        ),
                        document_kind=document.document_kind,
                    )
                    for document in documents
                ),
                key=_source_sort_key,
            )
        )
        return AiAnalysisProvenance(
            analysis_id=uuid4().hex,
            context_fingerprint=context_fingerprint,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            prompt_version=AI_PROMPT_VERSION,
            output_schema_version=AI_PROVIDER_OUTPUT_SCHEMA_VERSION,
            persisted_schema_version=AI_ANALYSIS_SCHEMA_VERSION,
            analyzer_version=AI_ANALYZER_VERSION,
            context_version=AI_CONTEXT_VERSION,
            citation_resolver_version=CITATION_RESOLVER_VERSION,
            provider_id=_provenance_identifier(
                metadata.provider_id,
                limit=_MAX_PROVIDER_ID_LENGTH,
                pattern=_PUBLIC_ID_PATTERN,
            ),
            provider_model=_provenance_identifier(
                metadata.model,
                limit=_MAX_PROVIDER_MODEL_LENGTH,
                pattern=_MODEL_ID_PATTERN,
            ),
            provider_response_id=provider_response_id,
            sources=sources,
        )

    def _normalize(
        self,
        registry_key: str,
        payload: Mapping[str, object],
        documents: tuple[AiDocument, ...],
        context_fingerprint: str,
    ) -> AiDocumentAnalysis:
        issues: list[str] = []
        raw_requirements = payload.get("requirements", {})
        if not isinstance(raw_requirements, Mapping):
            issues.append("requirements")
            raw_requirements = {}

        requirement_values, requirement_document_ids, requirement_issues = self._scoped_findings(
            raw_requirements,
            documents,
            context_fingerprint,
            category_prefix="requirements",
            document_kinds=APPLICATION_REQUIREMENTS_SOURCE_KINDS,
            finding_fields=_APPLICATION_REQUIREMENTS_FINDING_FIELDS,
        )
        requirement_values["contradictions"] = _require_independent_citations(
            requirement_values["contradictions"],
            requirement_issues,
            "requirements.contradictions.citations",
        )
        issues.extend(requirement_issues)
        if not requirement_document_ids:
            requirement_status = AiApplicationRequirementsStatus.NOT_FOUND
            requirement_values = {name: () for name in requirement_values}
        elif requirement_issues:
            requirement_status = AiApplicationRequirementsStatus.PARTIAL
        else:
            requirement_status = AiApplicationRequirementsStatus.COMPLETE
        requirements = TenderRequirements(
            status=requirement_status,
            document_ids=requirement_document_ids,
            included_document_ids=requirement_document_ids,
            **requirement_values,
            warnings=(
                ("Часть анализа требований к заявке не подтверждена.",)
                if requirement_issues
                else ()
            ),
        )
        raw_technical = payload.get("technical_specification", {})
        if not isinstance(raw_technical, Mapping):
            issues.append("technical_specification")
            raw_technical = {}
        technical_values, technical_document_ids, technical_issues = self._scoped_findings(
            raw_technical,
            documents,
            context_fingerprint,
            category_prefix="technical_specification",
            document_kinds=frozenset({DocumentKind.TECHNICAL_SPECIFICATION}),
            finding_fields=tuple(
                name
                for name in AiTechnicalSpecificationAnalysis.__dataclass_fields__
                if name not in {"status", "document_ids", "included_document_ids", "warnings"}
            ),
        )
        technical_values["contradictions"] = _require_multi_source_contradictions(
            technical_values["contradictions"], technical_issues
        )
        issues.extend(technical_issues)
        if not technical_document_ids:
            technical_status = AiTechnicalSpecificationStatus.NOT_FOUND
            technical_values = {name: () for name in technical_values}
        elif technical_issues:
            technical_status = AiTechnicalSpecificationStatus.PARTIAL
        else:
            technical_status = AiTechnicalSpecificationStatus.COMPLETE
        technical = AiTechnicalSpecificationAnalysis(
            status=technical_status,
            document_ids=technical_document_ids,
            included_document_ids=technical_document_ids,
            **technical_values,
            warnings=(
                ("Часть анализа технического задания не подтверждена.",) if technical_issues else ()
            ),
        )
        raw_contract = payload.get("draft_contract", {})
        if not isinstance(raw_contract, Mapping):
            issues.append("draft_contract")
            raw_contract = {}
        contract_values, contract_document_ids, contract_issues = self._scoped_findings(
            raw_contract,
            documents,
            context_fingerprint,
            category_prefix="draft_contract",
            document_kinds=frozenset({DocumentKind.DRAFT_CONTRACT}),
            finding_fields=tuple(
                name
                for name in AiDraftContractAnalysis.__dataclass_fields__
                if name not in {"status", "document_ids", "included_document_ids", "warnings"}
            ),
        )
        contract_values["contradictions"] = _require_independent_citations(
            contract_values["contradictions"],
            contract_issues,
            "draft_contract.contradictions.citations",
        )
        issues.extend(contract_issues)
        if not contract_document_ids:
            contract_status = AiDraftContractStatus.NOT_FOUND
            contract_values = {name: () for name in contract_values}
        elif contract_issues:
            contract_status = AiDraftContractStatus.PARTIAL
        else:
            contract_status = AiDraftContractStatus.COMPLETE
        contract = AiDraftContractAnalysis(
            status=contract_status,
            document_ids=contract_document_ids,
            included_document_ids=contract_document_ids,
            **contract_values,
            warnings=(
                ("Часть анализа проекта договора/контракта не подтверждена.",)
                if contract_issues
                else ()
            ),
        )
        missing_documents = self._strings(
            payload.get("missing_documents", ()),
            issues,
        )
        summary = _bounded_text(
            payload.get("summary", ""),
            MAX_SUMMARY_LENGTH,
            issues,
            "summary",
        )
        final_conclusion = _bounded_text(
            payload.get("final_ai_conclusion", ""),
            MAX_SUMMARY_LENGTH,
            issues,
            "final_ai_conclusion",
        )
        return AiDocumentAnalysis(
            registry_key=registry_key,
            summary=summary,
            requirements=requirements,
            risks=self._findings(
                payload.get("risks", ()),
                documents,
                context_fingerprint,
                "risk",
                issues,
            ),
            suspicious_conditions=self._findings(
                payload.get("suspicious_conditions", ()),
                documents,
                context_fingerprint,
                "suspicious",
                issues,
            ),
            contradictions=self._findings(
                payload.get("contradictions", ()),
                documents,
                context_fingerprint,
                "contradiction",
                issues,
            ),
            missing_documents=missing_documents,
            final_ai_conclusion=final_conclusion,
            status=(AiAnalysisStatus.PARTIAL if issues else AiAnalysisStatus.COMPLETE),
            warnings=(
                tuple(
                    dict.fromkeys(
                        (
                            "Часть ответа AI отклонена защитной проверкой.",
                            *(
                                (_RESOLVER_FAILURE_WARNING,)
                                if "resolver_exception" in issues
                                else ()
                            ),
                        )
                    )
                )
                if issues
                else ()
            ),
            technical_specification=technical,
            draft_contract=contract,
        )

    def _scoped_findings(
        self,
        raw_section: Mapping[str, object],
        documents: tuple[AiDocument, ...],
        context_fingerprint: str,
        *,
        category_prefix: str,
        document_kinds: frozenset[DocumentKind],
        finding_fields: tuple[str, ...],
    ) -> tuple[dict[str, tuple[AiFinding, ...]], tuple[str, ...], list[str]]:
        issues: list[str] = []
        document_ids = tuple(
            item.document_id
            for item in documents
            if item.document_kind in {kind.value for kind in document_kinds}
        )
        allowed_document_ids = frozenset(document_ids)
        values = {
            name: self._findings(
                raw_section.get(name, ()),
                documents,
                context_fingerprint,
                f"{category_prefix}.{name}",
                issues,
                allowed_document_ids=allowed_document_ids,
            )
            for name in finding_fields
        }
        return values, document_ids, issues

    @staticmethod
    def _render(document: AiDocument) -> str:
        marker = (
            f"\n[CONTEXT TRUNCATED: {len(document.text)} of "
            f"{document.original_character_count} characters]"
            if document.truncated
            else ""
        )
        return (
            f"DOCUMENT {document.document_id} | {document.name} | "
            f"KIND {document.document_kind}\n{document.text}{marker}"
        )

    @staticmethod
    def _findings(
        raw: object,
        documents: tuple[AiDocument, ...],
        context_fingerprint: str,
        category: str,
        issues: list[str],
        allowed_document_ids: frozenset[str] | None = None,
    ) -> tuple[AiFinding, ...]:
        if not isinstance(raw, (list, tuple)):
            if raw not in (None, ()):
                issues.append(category)
            return ()
        result: list[AiFinding] = []
        seen_candidates: set[tuple[str, str, str]] = set()
        for index, item in enumerate(raw):
            if not isinstance(item, Mapping):
                issues.append(f"{category}[{index}]")
                continue
            statement = _bounded_text(
                item.get("statement"),
                MAX_STATEMENT_LENGTH,
                issues,
                f"{category}.statement",
            )
            if not statement:
                issues.append(f"{category}.statement")
                continue
            document_id = _bounded_text(
                item.get("document_id"),
                500,
                issues,
                f"{category}.document_id",
            )
            quote = _exact_quote(
                item.get("quote"),
                issues,
                f"{category}.quote",
            )
            section = _bounded_text(
                item.get("section", ""),
                MAX_SECTION_LENGTH,
                issues,
                f"{category}.section",
            )
            confidence = _confidence(item.get("confidence"))
            if confidence is None:
                issues.append(f"{category}.confidence")
            page, page_valid = _page(item.get("page"))
            if not page_valid:
                issues.append(f"{category}.page")
            candidate_key = (statement.casefold(), document_id, quote)
            if candidate_key in seen_candidates:
                continue
            seen_candidates.add(candidate_key)
            try:
                resolution = (
                    resolve_citation(
                        document_id=document_id,
                        quote=quote,
                        section=section,
                        page=page,
                        confidence=confidence,
                        documents=documents,
                        context_fingerprint=context_fingerprint,
                    )
                    if confidence is not None and page_valid
                    else None
                )
            except Exception:
                issues.append("resolver_exception")
                resolution = None
            evidence = resolution.evidence if resolution is not None else None
            if evidence is not None and allowed_document_ids is not None:
                if evidence.document_id not in allowed_document_ids:
                    evidence = None
                    issues.append(f"{category}.document_kind")
            if evidence is None:
                issues.append(f"{category}.evidence")
            elif (section and section != evidence.section) or (
                page is not None and page != evidence.page
            ):
                issues.append(f"{category}.locator")
                evidence = None
            verified = evidence is not None
            result.append(
                AiFinding(
                    category,
                    statement,
                    evidence,
                    (AiFindingStatus.VERIFIED if verified else AiFindingStatus.UNVERIFIED),
                )
            )
        return tuple(result)

    @staticmethod
    def _strings(raw: object, issues: list[str]) -> tuple[str, ...]:
        if not isinstance(raw, (list, tuple)):
            if raw not in (None, ()):
                issues.append("missing_documents")
            return ()
        result: list[str] = []
        for value in raw:
            text = _bounded_text(value, 1_000, issues, "missing_documents")
            if text:
                result.append(text)
        return tuple(dict.fromkeys(result))


class TenderDocumentAiAnalysisService:
    """Build context, reuse identical results, analyze and persist safely."""

    def __init__(
        self,
        context_builder: TenderDocumentContextBuilder,
        analyzer: TenderDocumentAiAnalyzer,
        repository: AiDocumentAnalysisRepository,
    ) -> None:
        self.context_builder = context_builder
        self.analyzer = analyzer
        self.repository = repository

    def analyze(self, registry_key: str, *, force: bool = False) -> AiDocumentAnalysis:
        try:
            build_context = getattr(self.context_builder, "build_context", None)
            context = build_context(registry_key) if callable(build_context) else None
            documents = (
                context.documents
                if context is not None
                else self.context_builder.build(registry_key)
            )
        except Exception:
            return _add_warning(
                _safe_failure(registry_key, AiAnalysisStatus.INVALID_RESPONSE),
                "Не удалось подготовить локальный контекст AI-анализа.",
            )
        parameters = dict(getattr(self.context_builder, "fingerprint_parameters", {}))
        statistics = getattr(context, "statistics", None)
        statistic_fields = getattr(statistics, "__dataclass_fields__", {})
        if statistics is not None and statistic_fields:
            parameters["context_statistics"] = {
                name: getattr(statistics, name) for name in statistic_fields
            }
        fingerprint = context_fingerprint(documents, context_parameters=parameters)
        repository_warning = ""
        if not force:
            try:
                reused = self.repository.reusable(registry_key, fingerprint)
            except Exception:
                reused = None
                repository_warning = "Кеш AI-анализа временно недоступен."
            if reused is not None:
                return reused
            repository_warning = repository_warning or getattr(
                self.repository,
                "last_warning",
                "",
            )
        result = self.analyzer.analyze(
            registry_key,
            documents,
            context_fingerprint=fingerprint,
        )
        if statistics is not None:
            result = replace(
                result,
                context_document_count=statistics.included_document_count,
                context_character_count=statistics.character_count,
                context_truncated=statistics.truncated,
            )
            ts_found_ids = tuple(statistics.technical_specification_document_ids)
            ts_included_ids = tuple(statistics.included_technical_specification_document_ids)
            technical = result.technical_specification
            technical = _apply_scoped_context(
                technical,
                found_ids=ts_found_ids,
                included_ids=ts_included_ids,
                incomplete=statistics.technical_specification_truncated,
                not_found_status=AiTechnicalSpecificationStatus.NOT_FOUND,
                partial_status=AiTechnicalSpecificationStatus.PARTIAL,
                warning="Контекст технического задания неполон.",
            )
            contract = _apply_scoped_context(
                result.draft_contract,
                found_ids=tuple(statistics.draft_contract_document_ids),
                included_ids=tuple(statistics.included_draft_contract_document_ids),
                incomplete=statistics.draft_contract_truncated,
                not_found_status=AiDraftContractStatus.NOT_FOUND,
                partial_status=AiDraftContractStatus.PARTIAL,
                warning="Контекст проекта договора/контракта неполон.",
            )
            requirements = _apply_scoped_context(
                result.requirements,
                found_ids=tuple(statistics.application_requirements_document_ids),
                included_ids=tuple(statistics.included_application_requirements_document_ids),
                incomplete=statistics.application_requirements_truncated,
                not_found_status=AiApplicationRequirementsStatus.NOT_FOUND,
                partial_status=AiApplicationRequirementsStatus.PARTIAL,
                warning="Контекст требований к заявке неполон.",
            )
            result = replace(
                result,
                requirements=requirements,
                technical_specification=technical,
                draft_contract=contract,
            )
            if statistics.truncated:
                result = _add_warning(
                    result,
                    "Контекст AI-анализа был сокращён по безопасному лимиту.",
                )
        result = replace(result, legal_risk_assessment=assess_legal_risks(result))
        result = replace(result, financial_risk_assessment=assess_financial_risks(result))
        result = replace(
            result,
            competition_assessment=assess_competition_conditions(result),
        )
        if repository_warning:
            result = _add_warning(result, repository_warning)
        if result.status in {
            AiAnalysisStatus.COMPLETE,
            AiAnalysisStatus.PARTIAL,
            AiAnalysisStatus.NO_DOCUMENTS,
        }:
            try:
                self.repository.save(result, fingerprint)
            except Exception:
                result = _add_warning(
                    result,
                    "Не удалось сохранить историю AI-анализа.",
                )
        return result


def _safe_failure(
    registry_key: str,
    status: AiAnalysisStatus,
    documents: tuple[AiDocument, ...] = (),
) -> AiDocumentAnalysis:
    messages = {
        AiAnalysisStatus.PROVIDER_DISABLED: "AI provider is disabled.",
        AiAnalysisStatus.PROVIDER_ERROR: "AI analysis is temporarily unavailable.",
        AiAnalysisStatus.INVALID_RESPONSE: "AI response is invalid.",
    }
    ts_ids = tuple(
        item.document_id for item in documents if item.document_kind == "technical_specification"
    )
    contract_ids = tuple(
        item.document_id for item in documents if item.document_kind == "draft_contract"
    )
    requirement_ids = tuple(
        item.document_id
        for item in documents
        if item.document_kind in {kind.value for kind in APPLICATION_REQUIREMENTS_SOURCE_KINDS}
    )
    return AiDocumentAnalysis(
        registry_key,
        messages[status],
        status=status,
        requirements=TenderRequirements(
            status=(
                AiApplicationRequirementsStatus.UNAVAILABLE
                if requirement_ids
                else AiApplicationRequirementsStatus.NOT_FOUND
            ),
            document_ids=requirement_ids,
            included_document_ids=requirement_ids,
        ),
        technical_specification=AiTechnicalSpecificationAnalysis(
            status=(
                AiTechnicalSpecificationStatus.UNAVAILABLE
                if ts_ids
                else AiTechnicalSpecificationStatus.NOT_FOUND
            ),
            document_ids=ts_ids,
            included_document_ids=ts_ids,
        ),
        draft_contract=AiDraftContractAnalysis(
            status=(
                AiDraftContractStatus.UNAVAILABLE
                if contract_ids
                else AiDraftContractStatus.NOT_FOUND
            ),
            document_ids=contract_ids,
            included_document_ids=contract_ids,
        ),
    )


def _require_multi_source_contradictions(
    items: tuple[AiFinding, ...],
    issues: list[str],
) -> tuple[AiFinding, ...]:
    source_ids: dict[str, set[str]] = {}
    for item in items:
        if item.evidence is not None:
            source_ids.setdefault(item.statement.casefold(), set()).add(item.evidence.document_id)
    result: list[AiFinding] = []
    for item in items:
        if len(source_ids.get(item.statement.casefold(), set())) < 2:
            if item.verified:
                issues.append("technical_specification.contradictions.sources")
            result.append(replace(item, evidence=None, status=AiFindingStatus.UNVERIFIED))
        else:
            result.append(item)
    return tuple(result)


def _require_independent_citations(
    items: tuple[AiFinding, ...],
    issues: list[str],
    issue_key: str,
) -> tuple[AiFinding, ...]:
    citation_ids: dict[str, set[str]] = {}
    for item in items:
        if item.evidence is not None:
            citation_ids.setdefault(item.statement.casefold(), set()).add(item.evidence.citation_id)
    result: list[AiFinding] = []
    for item in items:
        if len(citation_ids.get(item.statement.casefold(), set())) < 2:
            if item.verified:
                issues.append(issue_key)
            result.append(replace(item, evidence=None, status=AiFindingStatus.UNVERIFIED))
        else:
            result.append(item)
    return tuple(result)


_ScopedAnalysis = TypeVar(
    "_ScopedAnalysis",
    TenderRequirements,
    AiTechnicalSpecificationAnalysis,
    AiDraftContractAnalysis,
)


def _apply_scoped_context(
    section: _ScopedAnalysis,
    *,
    found_ids: tuple[str, ...],
    included_ids: tuple[str, ...],
    incomplete: bool,
    not_found_status: (
        AiApplicationRequirementsStatus | AiTechnicalSpecificationStatus | AiDraftContractStatus
    ),
    partial_status: (
        AiApplicationRequirementsStatus | AiTechnicalSpecificationStatus | AiDraftContractStatus
    ),
    warning: str,
) -> _ScopedAnalysis:
    if not found_ids:
        return replace(
            section,
            status=not_found_status,
            document_ids=(),
            included_document_ids=(),
        )
    if incomplete:
        next_status = section.status if str(section.status) == "unavailable" else partial_status
        return replace(
            section,
            status=next_status,
            document_ids=found_ids,
            included_document_ids=included_ids,
            warnings=tuple(dict.fromkeys((*section.warnings, warning))),
        )
    return replace(
        section,
        document_ids=found_ids,
        included_document_ids=included_ids,
    )


def _bounded_text(
    value: object,
    limit: int,
    issues: list[str],
    field_name: str,
) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        issues.append(field_name)
        return ""
    try:
        rendered = str(value).strip()
    except Exception:
        issues.append(field_name)
        return ""
    if len(rendered) > limit:
        issues.append(field_name)
        return rendered[:limit]
    return rendered


def _exact_quote(
    value: object,
    issues: list[str],
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_QUOTE_LENGTH:
        issues.append(field_name)
        return ""
    return value


def _confidence(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    rendered = float(value)
    return rendered if math.isfinite(rendered) and 0.0 <= rendered <= 1.0 else None


def _page(value: object) -> tuple[int | None, bool]:
    if value is None:
        return None, True
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None, False
    return value, True


def _add_warning(
    analysis: AiDocumentAnalysis,
    warning: str,
) -> AiDocumentAnalysis:
    warnings = tuple(dict.fromkeys((*analysis.warnings, warning)))
    status = (
        AiAnalysisStatus.PARTIAL
        if analysis.status == AiAnalysisStatus.COMPLETE
        else analysis.status
    )
    return replace(analysis, warnings=warnings, status=status)


def _without_verified_findings(analysis: AiDocumentAnalysis) -> AiDocumentAnalysis:
    def downgrade(items: tuple[AiFinding, ...]) -> tuple[AiFinding, ...]:
        return tuple(
            replace(item, evidence=None, status=AiFindingStatus.UNVERIFIED)
            if item.status is AiFindingStatus.VERIFIED
            else item
            for item in items
        )

    requirements = replace(
        analysis.requirements,
        **cast(
            Any,
            {
                name: downgrade(getattr(analysis.requirements, name))
                for name in _APPLICATION_REQUIREMENTS_FINDING_FIELDS
            },
        ),
    )
    return replace(
        analysis,
        requirements=requirements,
        risks=downgrade(analysis.risks),
        suspicious_conditions=downgrade(analysis.suspicious_conditions),
        contradictions=downgrade(analysis.contradictions),
        provenance=None,
        technical_specification=replace(
            analysis.technical_specification,
            scope=downgrade(analysis.technical_specification.scope),
            deliverables=downgrade(analysis.technical_specification.deliverables),
            quantities_and_volumes=downgrade(
                analysis.technical_specification.quantities_and_volumes
            ),
            technical_characteristics=downgrade(
                analysis.technical_specification.technical_characteristics
            ),
            materials_and_equipment=downgrade(
                analysis.technical_specification.materials_and_equipment
            ),
            standards_and_regulations=downgrade(
                analysis.technical_specification.standards_and_regulations
            ),
            execution_conditions=downgrade(analysis.technical_specification.execution_conditions),
            stages_and_deadlines=downgrade(analysis.technical_specification.stages_and_deadlines),
            acceptance_and_quality=downgrade(
                analysis.technical_specification.acceptance_and_quality
            ),
            customer_inputs_and_dependencies=downgrade(
                analysis.technical_specification.customer_inputs_and_dependencies
            ),
            ambiguities=downgrade(analysis.technical_specification.ambiguities),
            contradictions=downgrade(analysis.technical_specification.contradictions),
            clarification_points=downgrade(analysis.technical_specification.clarification_points),
            status=(
                AiTechnicalSpecificationStatus.PARTIAL
                if analysis.technical_specification.document_ids
                else AiTechnicalSpecificationStatus.NOT_FOUND
            ),
        ),
        draft_contract=replace(
            analysis.draft_contract,
            **cast(
                Any,
                {
                    name: downgrade(getattr(analysis.draft_contract, name))
                    for name in AiDraftContractAnalysis.__dataclass_fields__
                    if name not in {"status", "document_ids", "included_document_ids", "warnings"}
                },
            ),
            status=(
                AiDraftContractStatus.PARTIAL
                if analysis.draft_contract.document_ids
                else AiDraftContractStatus.NOT_FOUND
            ),
        ),
    )


def _provider_response_reference(value: object) -> str:
    if not isinstance(value, str):
        return ""
    rendered = value.strip()
    if (
        not rendered
        or len(rendered) > MAX_RAW_RESPONSE_ID_LENGTH
        or any(ord(char) < 32 or ord(char) == 127 for char in rendered)
    ):
        return ""
    return f"resp_{hashlib.sha256(rendered.encode('utf-8')).hexdigest()}"


def _provenance_identifier(
    value: object,
    *,
    limit: int,
    pattern: re.Pattern[str],
) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > limit:
        return "unknown"
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value):
        return "unknown"
    if pattern.fullmatch(value) is None:
        return "unknown"
    lowered = value.casefold()
    words = {word for word in re.split(r"[/:._-]+", lowered) if word}
    if lowered.startswith(_CREDENTIAL_PREFIXES) or words & _CREDENTIAL_WORDS:
        return "unknown"
    return value


def _source_sort_key(source: AiSourceSnapshot) -> tuple[object, ...]:
    return (
        source.document_id,
        source.checksum_sha256,
        source.display_name,
        source.document_type,
        source.verification_status,
        source.received_at,
        source.truncated,
        source.included_character_count,
        source.original_character_count,
        source.document_kind,
    )


__all__ = [
    "AI_ANALYZER_VERSION",
    "TenderDocumentAiAnalyzer",
    "TenderDocumentAiAnalysisService",
]
