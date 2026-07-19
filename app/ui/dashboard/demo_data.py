"""Deterministic demonstration data for Dashboard visual review.

All procurement numbers and organizations in this module are synthetic.
They must never be presented as real tenders.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Mapping

from app.ui.dashboard.activity_feed import (
    ActivityEntry,
    ActivityTone,
)
from app.ui.viewmodels.dashboard_viewmodel import (
    APP_TIMEZONE,
    DASHBOARD_KPI_REGISTRY,
    AiRecommendation,
    DashboardKpi,
    DashboardKpiState,
    DashboardSourceEvidence,
    RecentTender,
    aware_dashboard_time,
)


DEMO_ENVIRONMENT_VARIABLE = "CORTERIS_DASHBOARD_DEMO"


@dataclass(frozen=True, slots=True)
class DashboardDemoSnapshot:
    """Complete synthetic dataset for Dashboard visual review."""

    kpis: tuple[DashboardKpi, ...]
    tenders: tuple[RecentTender, ...]
    recommendations: tuple[AiRecommendation, ...]
    activities: tuple[ActivityEntry, ...]
    generated_at: datetime

    @property
    def priority_tender(self) -> RecentTender | None:
        if not self.tenders:
            return None
        return max(
            self.tenders,
            key=lambda tender: tender.score if tender.score is not None else -1,
        )


def demo_mode_from_environment(
    environment: Mapping[str, str] | None = None,
) -> bool:
    """Return whether optional Dashboard demo mode is enabled."""
    source = os.environ if environment is None else environment
    value = source.get(DEMO_ENVIRONMENT_VARIABLE, "")
    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def build_empty_dashboard_kpis(now: datetime | None = None) -> tuple[DashboardKpi, ...]:
    """Return the normal zero-state KPI set."""
    observed_at = aware_dashboard_time(now or datetime.now(APP_TIMEZONE))
    evidence = (
        DashboardSourceEvidence(
            source_id="empty_state",
            generation=0,
            observed_at=observed_at,
            record_count=0,
        ),
    )
    return tuple(
        DashboardKpi.from_definition(
            definition,
            raw_value=Decimal("0") if definition.unit.value == "rub" else 0,
            state=DashboardKpiState.ZERO,
            source_evidence=evidence,
        )
        for definition in DASHBOARD_KPI_REGISTRY
    )


def build_demo_snapshot(
    now: datetime | None = None,
) -> DashboardDemoSnapshot:
    """Build a realistic, deterministic Corteris demonstration snapshot."""
    anchor = aware_dashboard_time(now or datetime.now(APP_TIMEZONE))

    def deadline(days: int) -> str:
        return (anchor.date() + timedelta(days=days)).strftime("%d.%m.%Y")

    demo_values: dict[str, int | Decimal] = {
        "potential_profit": Decimal("3480000"),
        "new_tenders": 24,
        "recommended": 8,
        "proposals_in_work": 3,
        "active_projects": 5,
        "attention": 3,
    }
    demo_trends = {
        "potential_profit": "+18% к прошлой неделе",
        "new_tenders": "+5 за сегодня",
        "recommended": "8 тендеров с числовой оценкой 80+",
        "proposals_in_work": "1 требуется отправить сегодня",
        "active_projects": "2 объекта на монтаже",
        "attention": "Ближайший срок — 2 дня",
    }
    kpis = tuple(
        replace(
            DashboardKpi.from_definition(
                definition,
                raw_value=demo_values[definition.key],
                state=DashboardKpiState.READY,
                source_evidence=(
                    DashboardSourceEvidence(
                        source_id="DEMO",
                        generation=0,
                        observed_at=anchor,
                        record_count=int(demo_values[definition.key]),
                        demo=True,
                    ),
                ),
                trend=demo_trends[definition.key],
            ),
            action=None,
        )
        for definition in DASHBOARD_KPI_REGISTRY
    )

    tenders = (
        RecentTender(
            number="DEMO-44-FZ-001",
            title=("Монтаж системы видеонаблюдения в административном комплексе"),
            customer="Демонстрационный государственный заказчик",
            nmck="12 480 000 ₽",
            deadline=deadline(7),
            score=94,
            status="Рекомендуется",
            platform="ЕИС — демонстрация",
            recommendation=("Высокое соответствие опыту, оборудованию и целевой маржинальности."),
        ),
        RecentTender(
            number="DEMO-223-FZ-002",
            title=("Комплекс «умный шлагбаум» с распознаванием автомобильных номеров"),
            customer="Демонстрационная управляющая компания",
            nmck="7 950 000 ₽",
            deadline=deadline(10),
            score=91,
            status="Высокий приоритет",
            platform="РТС-тендер — демонстрация",
            recommendation=("Подходит ПАК Entercam и типовое решение Corteris."),
        ),
        RecentTender(
            number="DEMO-44-FZ-003",
            title=("Поставка и монтаж системы контроля и управления доступом"),
            customer="Демонстрационное бюджетное учреждение",
            nmck="4 860 000 ₽",
            deadline=deadline(5),
            score=86,
            status="Рекомендуется",
            platform="Сбер А — демонстрация",
            recommendation=("Техническое задание соответствует компетенциям СКУД."),
        ),
        RecentTender(
            number="DEMO-44-FZ-004",
            title=("Техническое обслуживание охранно-пожарной сигнализации"),
            customer="Демонстрационный промышленный объект",
            nmck="2 140 000 ₽",
            deadline=deadline(3),
            score=72,
            status="Проверить документы",
            platform="ЕЭТП — демонстрация",
            recommendation=("Нужна дополнительная проверка лицензий и регламента SLA."),
        ),
        RecentTender(
            number="DEMO-COM-005",
            title=("Модернизация системы видеонаблюдения на складском комплексе"),
            customer="Демонстрационный коммерческий заказчик",
            nmck="3 650 000 ₽",
            deadline=deadline(2),
            score=58,
            status="Требует внимания",
            platform="Коммерческая ЭТП — демонстрация",
            recommendation=("Срок подготовки заявки короткий, а архив требует уточнения."),
        ),
    )

    recommendations = (
        AiRecommendation(
            title="Высокое соответствие компетенциям",
            description=(
                "Видеонаблюдение, СКУД и автоматизация КПП соответствуют профилю Corteris."
            ),
            severity="success",
            action_text="Открыть тендер",
        ),
        AiRecommendation(
            title="Подходящее оборудование",
            description=("Основные позиции можно закрыть решениями Trassir, Entercam и DoorHan."),
            severity="success",
        ),
        AiRecommendation(
            title="Целевая маржинальность",
            description=("Предварительная валовая прибыль выше внутреннего порога участия."),
            severity="info",
        ),
        AiRecommendation(
            title="Аналогичный опыт",
            description=("В базе есть сопоставимые проекты по видеонаблюдению и умным шлагбаумам."),
            severity="info",
        ),
        AiRecommendation(
            title="Сжатый срок подачи",
            description=(
                "По тендеру DEMO-COM-005 осталось два дня. Нужно проверить комплект документов."
            ),
            severity="warning",
            action_text="Проверить документы",
        ),
    )

    activities = (
        ActivityEntry(
            key="demo-analysis-complete",
            title="AI-анализ завершён",
            description=("Проверено 24 новых закупки, 8 рекомендованы для детального анализа."),
            timestamp=anchor - timedelta(minutes=4),
            tone=ActivityTone.SUCCESS,
            icon_text="AI",
        ),
        ActivityEntry(
            key="demo-priority-selected",
            title="Выбран приоритетный тендер",
            description=("DEMO-44-FZ-001 получил AI Score 94/100."),
            timestamp=anchor - timedelta(minutes=9),
            tone=ActivityTone.INFO,
            icon_text="T",
            action_text="Открыть",
            action_key="open_tender:DEMO-44-FZ-001",
        ),
        ActivityEntry(
            key="demo-proposal-draft",
            title="Черновик КП сохранён",
            description=("Коммерческое предложение по умному шлагбауму готово на 70%."),
            timestamp=anchor - timedelta(minutes=18),
            tone=ActivityTone.SUCCESS,
            icon_text="КП",
            action_text="Продолжить",
            action_key="create_proposal",
        ),
        ActivityEntry(
            key="demo-deadline-warning",
            title="Приближается срок подачи",
            description=("По DEMO-COM-005 необходимо принять решение об участии до конца дня."),
            timestamp=anchor - timedelta(minutes=31),
            tone=ActivityTone.WARNING,
            icon_text="!",
            action_text="Открыть",
            action_key="open_tender:DEMO-COM-005",
        ),
        ActivityEntry(
            key="demo-estimate-updated",
            title="Смета пересчитана",
            description=("Обновлены цены оборудования и монтажных работ."),
            timestamp=anchor - timedelta(hours=1, minutes=7),
            tone=ActivityTone.NEUTRAL,
            icon_text="₽",
        ),
    )

    return DashboardDemoSnapshot(
        kpis=kpis,
        tenders=tenders,
        recommendations=recommendations,
        activities=activities,
        generated_at=anchor,
    )


__all__ = [
    "DEMO_ENVIRONMENT_VARIABLE",
    "DashboardDemoSnapshot",
    "build_demo_snapshot",
    "build_empty_dashboard_kpis",
    "demo_mode_from_environment",
]
