"""Deterministic demonstration data for Dashboard visual review.

All procurement numbers and organizations in this module are synthetic.
They must never be presented as real tenders.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Mapping

from app.ui.dashboard.activity_feed import (
    ActivityEntry,
    ActivityTone,
)
from app.ui.viewmodels.dashboard_viewmodel import (
    AiRecommendation,
    DashboardKpi,
    RecentTender,
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


def build_empty_dashboard_kpis() -> tuple[DashboardKpi, ...]:
    """Return the normal zero-state KPI set."""
    return (
        DashboardKpi(
            key="potential_profit",
            title="Потенциальная прибыль",
            value="0 ₽",
            trend="Расчёты не выполнены",
            tone="info",
            icon_text="₽",
        ),
        DashboardKpi(
            key="new_tenders",
            title="Новые тендеры",
            value="0",
            trend="За сегодня",
            tone="info",
            icon_text="T",
        ),
        DashboardKpi(
            key="recommended",
            title="AI рекомендует",
            value="0",
            trend="После анализа",
            tone="success",
            icon_text="AI",
        ),
        DashboardKpi(
            key="proposals_in_work",
            title="КП в работе",
            value="0",
            trend="Нет активных КП",
            tone="default",
            icon_text="КП",
        ),
        DashboardKpi(
            key="active_projects",
            title="Активные проекты",
            value="0",
            trend="Нет активных проектов",
            tone="default",
            icon_text="P",
        ),
        DashboardKpi(
            key="attention",
            title="Требуют внимания",
            value="0",
            trend="Нет срочных задач",
            tone="warning",
            icon_text="!",
        ),
    )


def build_demo_snapshot(
    now: datetime | None = None,
) -> DashboardDemoSnapshot:
    """Build a realistic, deterministic Corteris demonstration snapshot."""
    anchor = now or datetime.now()

    def deadline(days: int) -> str:
        return (anchor.date() + timedelta(days=days)).strftime("%d.%m.%Y")

    kpis = (
        DashboardKpi(
            key="potential_profit",
            title="Потенциальная прибыль",
            value="3 480 000 ₽",
            trend="+18% к прошлой неделе",
            tone="success",
            icon_text="₽",
        ),
        DashboardKpi(
            key="new_tenders",
            title="Новые тендеры",
            value="24",
            trend="+5 за сегодня",
            tone="info",
            icon_text="T",
        ),
        DashboardKpi(
            key="recommended",
            title="AI рекомендует",
            value="8",
            trend="3 с высоким приоритетом",
            tone="success",
            icon_text="AI",
        ),
        DashboardKpi(
            key="proposals_in_work",
            title="КП в работе",
            value="3",
            trend="1 требуется отправить сегодня",
            tone="warning",
            icon_text="КП",
        ),
        DashboardKpi(
            key="active_projects",
            title="Активные проекты",
            value="5",
            trend="2 объекта на монтаже",
            tone="info",
            icon_text="P",
        ),
        DashboardKpi(
            key="attention",
            title="Требуют внимания",
            value="3",
            trend="Ближайший срок — 2 дня",
            tone="warning",
            icon_text="!",
        ),
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
