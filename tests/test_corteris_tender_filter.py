"""Tests for Corteris tender classification and filtering."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.tenders.corteris_filter import (
    CorterisTenderClassifier,
    CorterisTenderFilter,
    RelevanceGrade,
    TenderDirection,
    TenderFilterOptions,
    normalize_text,
)
from app.tenders.models import (
    TenderCustomer,
    TenderMoney,
    TenderSource,
    TenderStatus,
    UnifiedTender,
)


NOW = datetime(2026, 7, 12, 12, 0)


def make_tender(
    *,
    title: str,
    description: str = "",
    region: str = "Москва",
    law: str = "44-ФЗ",
    amount: str = "1000000",
    status: TenderStatus = TenderStatus.ACCEPTING_APPLICATIONS,
    tags: tuple[str, ...] = (),
    deadline_minutes: int = 120,
) -> UnifiedTender:
    identity = abs(hash((title, description, region))) % 1_000_000
    return UnifiedTender(
        source=TenderSource.EIS,
        external_id=str(identity),
        procurement_number=f"03731000001{identity:010d}",
        title=title,
        customer=TenderCustomer(
            name="Государственный заказчик",
            region=region,
        ),
        source_url=f"https://example.org/{identity}",
        application_deadline=NOW
        + timedelta(minutes=deadline_minutes),
        price=TenderMoney.from_value(amount),
        status=status,
        law=law,
        region=region,
        description=description,
        tags=tags,
    )


def test_normalize_text_handles_punctuation_and_yo() -> None:
    assert normalize_text("СКУД / Видеонаблюдение, Ёлка") == (
        "скуд видеонаблюдение елка"
    )


def test_video_surveillance_tender_is_highly_relevant() -> None:
    tender = make_tender(
        title="Монтаж системы видеонаблюдения",
        description=(
            "Поставка IP-видеокамер, видеорегистратора "
            "и выполнение пусконаладочных работ."
        ),
    )

    result = CorterisTenderClassifier().evaluate(tender)

    assert result.relevant
    assert result.grade in {
        RelevanceGrade.HIGH,
        RelevanceGrade.MEDIUM,
    }
    assert TenderDirection.VIDEO_SURVEILLANCE in (
        result.directions
    )
    assert result.score >= 40


def test_ambiguous_cold_chamber_is_hard_excluded() -> None:
    tender = make_tender(
        title="Поставка холодильной камеры",
        description="Камера для хранения пищевой продукции.",
    )

    result = CorterisTenderClassifier().evaluate(tender)

    assert result.hard_excluded
    assert result.score == 0
    assert result.grade == RelevanceGrade.EXCLUDED


def test_integrated_security_gets_multiple_directions() -> None:
    tender = make_tender(
        title=(
            "Монтаж комплексной системы безопасности: "
            "видеонаблюдение, СКУД и шлагбаум"
        ),
        description=(
            "Настройка распознавания автомобильных номеров "
            "на въезде."
        ),
    )

    result = CorterisTenderClassifier().evaluate(tender)

    assert result.score >= 65
    assert {
        TenderDirection.VIDEO_SURVEILLANCE,
        TenderDirection.SKUD,
        TenderDirection.BARRIERS,
        TenderDirection.ANPR,
        TenderDirection.INTEGRATED_SECURITY,
    }.issubset(set(result.directions))


def test_filter_rejects_closed_tender_by_default() -> None:
    tender = make_tender(
        title="Обслуживание системы видеонаблюдения",
        status=TenderStatus.COMPLETED,
    )

    result = CorterisTenderFilter().filter((tender,))

    assert result.accepted_count == 0
    assert result.rejected_count == 1
    assert "Приём заявок не открыт" in (
        result.rejected[0].rejection_reasons
    )


def test_filter_can_require_specific_direction() -> None:
    video = make_tender(
        title="Монтаж видеонаблюдения",
    )
    barrier = make_tender(
        title="Поставка автоматического шлагбаума",
    )

    result = CorterisTenderFilter().filter(
        (video, barrier),
        TenderFilterOptions(
            required_directions=(TenderDirection.BARRIERS,)
        ),
    )

    assert result.accepted_count == 1
    assert result.accepted[0].tender.title == (
        "Поставка автоматического шлагбаума"
    )


def test_filter_applies_region_and_price() -> None:
    moscow = make_tender(
        title="Монтаж СКУД",
        region="Москва",
        amount="500000",
    )
    kazan = make_tender(
        title="Монтаж СКУД",
        region="Республика Татарстан",
        amount="500000",
    )
    expensive = make_tender(
        title="Монтаж СКУД и турникетов",
        region="Москва",
        amount="15000000",
    )

    result = CorterisTenderFilter().filter(
        (moscow, kazan, expensive),
        TenderFilterOptions(
            regions=("Москва",),
            max_price=2_000_000,
        ),
    )

    assert result.accepted_count == 1
    assert result.accepted[0].tender is moscow


def test_results_are_ranked_by_relevance_then_deadline() -> None:
    medium = make_tender(
        title="Поставка шлагбаума",
        deadline_minutes=30,
    )
    strong = make_tender(
        title=(
            "Монтаж видеонаблюдения, СКУД, шлагбаума "
            "и распознавания номеров"
        ),
        deadline_minutes=300,
    )

    result = CorterisTenderFilter().filter((medium, strong))

    assert result.accepted[0].tender is strong
    assert (
        result.accepted[0].relevance.score
        >= result.accepted[1].relevance.score
    )


def test_direction_counts_are_calculated() -> None:
    tenders = (
        make_tender(title="Монтаж видеонаблюдения"),
        make_tender(title="Обслуживание видеонаблюдения"),
        make_tender(title="Поставка шлагбаума"),
    )

    result = CorterisTenderFilter().filter(tenders)

    assert result.direction_counts[
        TenderDirection.VIDEO_SURVEILLANCE
    ] == 2
    assert result.direction_counts[
        TenderDirection.BARRIERS
    ] == 1
