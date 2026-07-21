"""Synthetic, isolated widget factories for the RM-154 catalog."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QWidget

from app.config.user_settings import UserPreferences
from app.repositories.business_metrics import BusinessMetricsRepository
from app.tenders.collector.participation_score import (
    CorterisParticipationScore,
    ParticipationRecommendation,
    ParticipationScoreComponent,
)
from app.tenders.participation_decision import (
    ParticipationDecision,
    ParticipationDecisionEvidence,
    ParticipationDecisionInput,
    ParticipationDecisionRecommendation,
)
from app.ui.component_gallery import ComponentGallery
from app.ui.modern_main_window import ModernMainWindow
from app.ui.navigation import NavigationCause, RouteId, RouteRequest
from app.ui.tender_participation_score_dialog import TenderParticipationScoreDialog
from app.ui.theme.colors import ThemeName
from app.ui.viewmodels.dashboard_viewmodel import APP_TIMEZONE, DashboardViewModel, RecentTender

from .contracts import VisualCase


class _TenderRepository:
    def list(self) -> list[object]:
        return []


class _SettingsStore:
    def load(self) -> UserPreferences:
        return UserPreferences()


class _PriceCatalog:
    def search(self, _query: str, _limit: int) -> list[object]:
        return []


class _PriceOfferRepository:
    def __init__(self, _path: object) -> None:
        self.offers: list[object] = []

    def load(self) -> list[object]:
        return []


class _MemorySettings:
    """Minimal QSettings substitute that never reads the Windows registry."""

    def __init__(self, _organization: str, _application: str) -> None:
        self._values: dict[str, object] = {}

    def value(self, key: str, default: object = None) -> object:
        return self._values.get(key, default)

    def setValue(self, key: str, value: object) -> None:  # noqa: N802
        self._values[key] = value


@dataclass(slots=True)
class BuiltVisual:
    widget: QWidget
    privacy_values: tuple[str, ...]
    _cleanup: Callable[[], None]

    def dispose(self, app: QApplication) -> None:
        self.widget.close()
        self.widget.deleteLater()
        app.processEvents()
        self._cleanup()


def _shell(runtime_root: Path) -> tuple[ModernMainWindow, ExitStack]:
    stack = ExitStack()
    fixed_dashboard_time = datetime(2026, 7, 21, 9, 0, 0, tzinfo=APP_TIMEZONE)
    stack.enter_context(
        patch(
            "app.ui.pages.dashboard_page.DashboardViewModel",
            lambda parent=None: DashboardViewModel(
                parent,
                clock=lambda: fixed_dashboard_time,
            ),
        )
    )
    stack.enter_context(
        patch("app.ui.pages.tender_workspace_page.TenderRepository", _TenderRepository)
    )
    stack.enter_context(
        patch("app.ui.pages.tender_workspace_page.UserSettingsStore", _SettingsStore)
    )
    stack.enter_context(
        patch("app.ui.pages.tender_workspace_page.PriceCatalog", lambda _path: _PriceCatalog())
    )
    stack.enter_context(
        patch("app.ui.pages.tender_workspace_page.PriceOfferRepository", _PriceOfferRepository)
    )
    stack.enter_context(
        patch(
            "app.ui.pages.tender_workspace_page.AiProviderSettingsWidget.load", lambda _self: None
        )
    )
    stack.enter_context(
        patch("app.ui.modern_main_window.DashboardController.start", lambda _self: None)
    )
    stack.enter_context(patch("app.ui.modern_main_window.QSettings", _MemorySettings))
    stack.enter_context(
        patch(
            "app.ui.pages.business_workflow_page.SystemHealthMonitor.request_refresh",
            lambda _self: False,
        )
    )
    stack.enter_context(
        patch(
            "app.ui.modern_main_window.BusinessMetricsRepository",
            lambda: BusinessMetricsRepository(runtime_root / "workflow.json"),
        )
    )
    try:
        return ModernMainWindow(), stack
    except BaseException:
        stack.close()
        raise


def _route_for_fixture(fixture_id: str) -> RouteId:
    if fixture_id.startswith("shell-dashboard"):
        return RouteId.DASHBOARD
    if fixture_id == "shell-tenders-empty-v1":
        return RouteId.TENDERS
    if fixture_id == "shell-workflow-empty-v1":
        return RouteId.WORKFLOW
    if fixture_id == "shell-analytics-empty-v1":
        return RouteId.FUTURE_ANALYTICS
    raise KeyError(fixture_id)


def _dashboard_ready(window: ModernMainWindow) -> tuple[str, ...]:
    tenders = [
        RecentTender(
            number="VISUAL-154-001",
            title="Монтаж системы видеонаблюдения",
            customer="Учебный заказчик Альфа",
            deadline="31.07.2026",
            score=87,
            recommendation="Проверить стоп-факторы",
            nmck="2 450 000,00 ₽",
            status="review",
            platform="ЕИС",
            identity_kind="synthetic",
            identity_value="VISUAL-154-001",
        ),
        RecentTender(
            number="VISUAL-154-002",
            title="Техническое обслуживание камер",
            customer="Учебный заказчик Бета",
            deadline="05.08.2026",
            score=72,
            recommendation="Требуется проверка",
            nmck="980 000,00 ₽",
            status="partial",
            platform="РТС",
            identity_kind="synthetic",
            identity_value="VISUAL-154-002",
        ),
    ]
    page = window.dashboard_page
    page.set_kpi("new_tenders", "2", trend="Фиксированный снимок", tone="info")
    page.set_kpi("recommended", "1", trend="Порог 80+", tone="success")
    page.set_kpi("attention", "1", trend="Требует проверки", tone="warning")
    page.set_recent_tenders(tenders)
    return tuple(
        value
        for tender in tenders
        for value in (tender.number, tender.title, tender.customer, tender.identity_value)
    )


def _participation_dialog(
    theme: ThemeName,
) -> tuple[TenderParticipationScoreDialog, tuple[str, ...]]:
    registry_key = "synthetic:VISUAL-154-STOP"
    score = CorterisParticipationScore(
        total_score=87,
        recommendation=ParticipationRecommendation.NOT_RECOMMENDED,
        recommendation_text="Не участвовать: действует критический стоп-фактор",
        components=(
            ParticipationScoreComponent(
                "technical-fit",
                "Соответствие профилю",
                60,
                60,
                "Синтетическое соответствие подтверждено.",
            ),
            ParticipationScoreComponent(
                "commercial-fit",
                "Коммерческая оценка",
                27,
                40,
                "Требуется проверка исходных допущений.",
            ),
            ParticipationScoreComponent(
                "critical-license",
                "Критический стоп-фактор",
                0,
                0,
                "Обязательная лицензия не подтверждена.",
            ),
        ),
        positive_factors=("Соответствие профилю",),
        negative_factors=("Не подтверждена обязательная лицензия",),
        matched_keywords=("видеонаблюдение",),
        matched_okpd2=(),
        stop_factors=("Не подтверждена обязательная лицензия",),
        missing_documents=("Копия лицензии",),
        directions=("security",),
        hard_excluded=True,
        scored_at="2026-07-21T09:00:00+03:00",
        profile_version="visual-fixture-v1",
        input_fingerprint="f" * 64,
        evidence_sources=("synthetic-fixture",),
    )
    decision = ParticipationDecision(
        decision_id="VISUAL-154-DECISION",
        registry_key=registry_key,
        recommendation=ParticipationDecisionRecommendation.DO_NOT_PARTICIPATE,
        confidence=0.96,
        summary="Критический стоп-фактор имеет приоритет над числовой оценкой.",
        evidence=(
            ParticipationDecisionEvidence(
                code="critical-license",
                title="Обязательная лицензия",
                detail="Подтверждающий документ отсутствует в синтетическом комплекте.",
                confidence=0.96,
                source="deterministic-policy",
                impact=-100,
            ),
        ),
        input=ParticipationDecisionInput(registry_key=registry_key, score=score),
        decided_at="2026-07-21T09:00:00+03:00",
        policy_version="visual-fixture-v1",
        score=87,
        stop_factors=("Не подтверждена обязательная лицензия",),
        missing=("Копия лицензии",),
        actions=("Запросить документ до решения об участии",),
    )
    dialog = TenderParticipationScoreDialog(registry_key, score=score, theme=theme)
    dialog.set_decision(decision)
    dialog.set_status("Синтетический снимок решения; внешние источники не использовались.")
    values = (
        registry_key,
        decision.decision_id,
        decision.summary,
        score.recommendation_text,
        *decision.stop_factors,
        *decision.missing,
        *decision.actions,
    )
    return dialog, values


def build_visual(case: VisualCase, runtime_root: Path) -> BuiltVisual:
    """Construct one catalog case without touching live application state."""

    theme = ThemeName(case.theme)
    if case.fixture_id.startswith("shell-"):
        window, stack = _shell(runtime_root)
        window.apply_theme(theme)
        result = window.workspace.navigate(
            RouteRequest(_route_for_fixture(case.fixture_id), cause=NavigationCause.PROGRAMMATIC)
        )
        if not result.succeeded:
            stack.close()
            raise RuntimeError(f"synthetic route failed: {case.fixture_id}")
        privacy_values: tuple[str, ...] = ()
        if case.fixture_id == "shell-dashboard-ready-v1":
            privacy_values = _dashboard_ready(window)
        return BuiltVisual(window, privacy_values, stack.close)

    if case.fixture_id == "component-gallery-core-v1":
        gallery = ComponentGallery(theme=theme)
        return BuiltVisual(gallery, (gallery.synthetic_long_label,), lambda: None)

    if case.fixture_id == "participation-critical-stop-v1":
        dialog, values = _participation_dialog(theme)
        return BuiltVisual(dialog, values, lambda: None)

    raise KeyError(case.fixture_id)
