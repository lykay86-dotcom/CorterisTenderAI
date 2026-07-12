"""Tests for explainable Corteris participation scoring."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from app.tenders.collector.participation_score import (
    CorterisParticipationRanker,
    ParticipationRecommendation,
    ParticipationScoringContext,
)
from tests.collector_c3_helpers import make_tender


def _now() -> datetime:
    return datetime(2026, 7, 12, tzinfo=timezone.utc)


def test_relevant_security_tender_gets_explainable_score() -> None:
    tender = make_tender(
        title=(
            "Поставка и монтаж системы видеонаблюдения "
            "Trassir и СКУД"
        ),
        description=(
            "IP-камеры, видеорегистратор, контроллеры "
            "доступа и пусконаладочные работы"
        ),
        deadline_day=30,
    )

    score = CorterisParticipationRanker().score(
        tender,
        ParticipationScoringContext(now=_now()),
    )

    assert score.total_score >= 65
    assert score.recommendation in {
        ParticipationRecommendation.RECOMMENDED,
        ParticipationRecommendation.MANUAL_REVIEW,
    }
    assert len(score.components) == 9
    assert score.matched_keywords
    assert score.matched_okpd2 == ("26.40.33.190",)


def test_medical_camera_is_hard_excluded() -> None:
    tender = replace(
        make_tender(
            title="Поставка медицинской видеокамеры",
            description=(
                "Медицинская видеокамера для операционной"
            ),
        ),
        tags=(),
        classification_codes=(),
    )

    score = CorterisParticipationRanker().score(tender)

    assert score.total_score == 0
    assert score.hard_excluded
    assert score.recommendation == (
        ParticipationRecommendation.NOT_RECOMMENDED
    )


def test_protected_security_repair_is_not_excluded() -> None:
    tender = make_tender(
        title="Капитальный ремонт системы видеонаблюдения",
        description="Замена камер, кабельных линий и регистратора",
    )

    score = CorterisParticipationRanker().score(
        tender,
        ParticipationScoringContext(now=_now()),
    )

    assert not score.hard_excluded
    assert score.total_score > 0


def test_document_text_participates_in_matching() -> None:
    tender = replace(
        make_tender(
            title="Оказание услуг",
            description="Работы согласно документации",
        ),
        tags=(),
        classification_codes=(),
    )

    score = CorterisParticipationRanker().score(
        tender,
        ParticipationScoringContext(
            document_texts=(
                "Монтаж СКУД, турникетов и "
                "электромагнитных замков.",
            ),
            now=_now(),
            evidence_sources=("Техническое задание.docx",),
        ),
    )

    assert "скуд" in {
        item.casefold() for item in score.matched_keywords
    }
    assert "Техническое задание.docx" in score.evidence_sources


def test_foreign_currency_requires_manual_financial_review() -> None:
    tender = make_tender(title="Монтаж видеонаблюдения")
    tender = replace(
        tender,
        price=replace(tender.price, currency="USD"),
    )

    score = CorterisParticipationRanker().score(
        tender,
        ParticipationScoringContext(now=_now()),
    )
    price = next(
        item for item in score.components if item.key == "price"
    )

    assert price.score == 4
    assert "Требуется ручной курс" in price.explanation
