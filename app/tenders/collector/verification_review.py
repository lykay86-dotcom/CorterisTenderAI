"""Read-model and manual-resolution service for verification UI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.verification import (
    CRITICAL_FIELD_NAMES,
    FieldCandidate,
    FieldConflict,
    FieldResolutionRecord,
    SourceTrustLevel,
    TenderVerificationState,
    TenderVerificationStatus,
)


FIELD_LABELS: Mapping[str, str] = {
    "procurement_number": "Номер закупки",
    "price": "НМЦК / цена",
    "application_deadline": "Срок подачи",
    "status": "Статус процедуры",
    "law": "Закон",
    "customer.name": "Заказчик",
    "customer.inn": "ИНН заказчика",
    "platform": "Площадка",
    "application_security": "Обеспечение заявки",
    "contract_security": "Обеспечение контракта",
    "documentation_url": "Ссылка на документацию",
    "source_url": "Карточка закупки",
}

TRUST_LABELS: Mapping[SourceTrustLevel, str] = {
    SourceTrustLevel.UNKNOWN: "Неизвестный источник",
    SourceTrustLevel.AGGREGATOR: "Агрегатор",
    SourceTrustLevel.PUBLIC_CARD: "Публичная карточка",
    SourceTrustLevel.CUSTOMER_SITE: "Сайт заказчика",
    SourceTrustLevel.OFFICIAL_API: "Официальный API",
    SourceTrustLevel.OFFICIAL_PLATFORM: "Официальная ЭТП",
    SourceTrustLevel.EIS: "ЕИС",
    SourceTrustLevel.OFFICIAL_DOCUMENTATION: "Официальная документация",
}

STATUS_LABELS: Mapping[TenderVerificationStatus, str] = {
    TenderVerificationStatus.MISSING: "Данные отсутствуют",
    TenderVerificationStatus.UNVERIFIED: "Не проверено",
    TenderVerificationStatus.AGGREGATOR_ONLY: "Только агрегатор",
    TenderVerificationStatus.PUBLIC_CARD: "Публичная карточка",
    TenderVerificationStatus.CUSTOMER_SITE: "Сайт заказчика",
    TenderVerificationStatus.VERIFIED_OFFICIAL_API: "Подтверждено API",
    TenderVerificationStatus.VERIFIED_PLATFORM: "Подтверждено на ЭТП",
    TenderVerificationStatus.VERIFIED_EIS: "Подтверждено в ЕИС",
    TenderVerificationStatus.VERIFIED_DOCUMENTATION: "Подтверждено документами",
    TenderVerificationStatus.INCOMPLETE: "Проверено частично",
    TenderVerificationStatus.CONFLICT: "Конфликт данных",
}


@dataclass(frozen=True, slots=True)
class VerificationFieldReview:
    field_name: str
    label: str
    candidates: tuple[FieldCandidate, ...]
    selected_candidate_id: str
    conflict: FieldConflict | None
    manually_selected: bool

    @property
    def selected_candidate(self) -> FieldCandidate | None:
        for item in self.candidates:
            if item.candidate_id == self.selected_candidate_id:
                return item
        return None


@dataclass(frozen=True, slots=True)
class TenderVerificationReview:
    registry_key: str
    state: TenderVerificationState | None
    fields: tuple[VerificationFieldReview, ...]
    conflicts: tuple[FieldConflict, ...]
    resolutions: tuple[FieldResolutionRecord, ...]

    @property
    def unresolved_conflicts(self) -> int:
        return sum(item.unresolved for item in self.conflicts)

    @property
    def manual_field_count(self) -> int:
        return sum(item.manually_selected for item in self.fields)


class TenderVerificationReviewService:
    """Compose verification evidence and commit explicit user choices."""

    def __init__(self, repository: CollectorStateRepository) -> None:
        self.repository = repository

    def load(self, registry_key: str) -> TenderVerificationReview:
        normalized = registry_key.strip()
        if not normalized:
            raise ValueError("registry_key must not be empty")
        state = self.repository.get_verification_state(normalized)
        candidates = self.repository.list_field_candidates(normalized)
        conflicts = self.repository.list_field_conflicts(normalized)
        resolutions = self.repository.list_field_resolutions(normalized)
        by_field: dict[str, list[FieldCandidate]] = {}
        for candidate in candidates:
            by_field.setdefault(candidate.field_name, []).append(candidate)
        conflict_by_field: dict[str, FieldConflict] = {}
        for conflict in conflicts:
            conflict_by_field.setdefault(conflict.field_name, conflict)
        ordered_fields = list(CRITICAL_FIELD_NAMES)
        ordered_fields.extend(field for field in sorted(by_field) if field not in ordered_fields)
        fields: list[VerificationFieldReview] = []
        for field_name in ordered_fields:
            field_candidates = tuple(by_field.get(field_name, ()))
            selected = next(
                (item for item in field_candidates if item.selected),
                None,
            )
            fields.append(
                VerificationFieldReview(
                    field_name=field_name,
                    label=FIELD_LABELS.get(field_name, field_name),
                    candidates=field_candidates,
                    selected_candidate_id=(selected.candidate_id if selected is not None else ""),
                    conflict=conflict_by_field.get(field_name),
                    manually_selected=any(item.manual_override for item in field_candidates),
                )
            )
        return TenderVerificationReview(
            registry_key=normalized,
            state=state,
            fields=tuple(fields),
            conflicts=conflicts,
            resolutions=resolutions,
        )

    def resolve(
        self,
        registry_key: str,
        field_name: str,
        candidate_id: str,
        *,
        note: str = "",
        resolved_by: str = "user",
    ) -> TenderVerificationReview:
        self.repository.resolve_field_candidate(
            registry_key,
            field_name,
            candidate_id,
            note=note,
            resolved_by=resolved_by,
        )
        return self.load(registry_key)

    def clear(
        self,
        registry_key: str,
        field_name: str,
        *,
        note: str = "",
        resolved_by: str = "user",
    ) -> TenderVerificationReview:
        self.repository.clear_manual_field_resolution(
            registry_key,
            field_name,
            note=note,
            resolved_by=resolved_by,
        )
        return self.load(registry_key)


__all__ = [
    "FIELD_LABELS",
    "STATUS_LABELS",
    "TRUST_LABELS",
    "TenderVerificationReview",
    "TenderVerificationReviewService",
    "VerificationFieldReview",
]
