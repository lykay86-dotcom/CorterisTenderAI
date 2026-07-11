"""Dashboard-specific UI components."""

from app.ui.dashboard.ai_advisor import AiAdvisor, AiStatus
from app.ui.dashboard.kpi_center import KpiCenter
from app.ui.dashboard.section import DashboardSection
from app.ui.dashboard.tender_feed import (
    COLUMNS,
    TenderColumn,
    TenderFeed,
    TenderFeedModel,
)

__all__ = [
    "AiAdvisor",
    "AiStatus",
    "COLUMNS",
    "DashboardSection",
    "KpiCenter",
    "TenderColumn",
    "TenderFeed",
    "TenderFeedModel",
]
