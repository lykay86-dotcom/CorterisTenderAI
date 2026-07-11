"""Dashboard-specific UI components."""

from app.ui.dashboard.activity_feed import (
    ActivityEntry,
    ActivityFeed,
    ActivityFeedItem,
    ActivityTone,
)
from app.ui.dashboard.ai_advisor import AiAdvisor, AiStatus
from app.ui.dashboard.keyboard_navigation import (
    DEFAULT_DASHBOARD_SHORTCUTS,
    DashboardShortcutManager,
    DashboardShortcutSpec,
)
from app.ui.dashboard.kpi_center import KeyboardKpiCard, KpiCenter
from app.ui.dashboard.quick_actions import (
    DEFAULT_QUICK_ACTIONS,
    QuickActionSpec,
    QuickActionTile,
    QuickActionTone,
    QuickActions,
)
from app.ui.dashboard.responsive import (
    DashboardDensity,
    DashboardLayoutSpec,
    dashboard_layout_for_width,
)
from app.ui.dashboard.section import DashboardSection
from app.ui.dashboard.status_banner import (
    DashboardStatusBanner,
    StatusTone,
)
from app.ui.dashboard.tender_feed import (
    COLUMNS,
    TenderColumn,
    TenderFeed,
    TenderFeedModel,
)

__all__ = [
    "ActivityEntry",
    "ActivityFeed",
    "ActivityFeedItem",
    "ActivityTone",
    "AiAdvisor",
    "AiStatus",
    "COLUMNS",
    "DEFAULT_DASHBOARD_SHORTCUTS",
    "DEFAULT_QUICK_ACTIONS",
    "DashboardDensity",
    "DashboardLayoutSpec",
    "DashboardSection",
    "DashboardShortcutManager",
    "DashboardShortcutSpec",
    "DashboardStatusBanner",
    "KeyboardKpiCard",
    "KpiCenter",
    "QuickActionSpec",
    "QuickActionTile",
    "QuickActionTone",
    "QuickActions",
    "StatusTone",
    "TenderColumn",
    "TenderFeed",
    "TenderFeedModel",
    "dashboard_layout_for_width",
]
