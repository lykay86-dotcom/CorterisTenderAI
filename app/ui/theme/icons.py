"""Semantic icon identities backed by repository-owned SVG resources."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Final, Mapping

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

from app.core.path_manager import PathManager
from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.tokens import IconSize


class IconId(StrEnum):
    NAV_DASHBOARD = "navigation.dashboard"
    NAV_TENDERS = "navigation.tenders"
    NAV_WORKFLOW = "navigation.workflow"
    NAV_ANALYTICS = "navigation.analytics"
    TOPBAR_SEARCH = "topbar.search"
    TOPBAR_AI = "topbar.ai"
    TOPBAR_NOTIFICATIONS = "topbar.notifications"
    TOPBAR_THEME = "topbar.theme"
    TOPBAR_PROFILE = "topbar.profile"
    ACTION_ADD = "action.add"
    ACTION_EDIT = "action.edit"
    ACTION_DELETE = "action.delete"
    ACTION_REFRESH = "action.refresh"
    ACTION_IMPORT = "action.import"
    ACTION_EXPORT = "action.export"
    ACTION_BACK = "action.back"
    ACTION_CLOSE = "action.close"
    STATE_INFO = "state.info"
    STATE_SUCCESS = "state.success"
    STATE_WARNING = "state.warning"
    STATE_DANGER = "state.danger"
    STATE_LOADING = "state.loading"
    STATE_EMPTY = "state.empty"
    DOCUMENTS = "neutral.documents"
    SETTINGS = "neutral.settings"
    HISTORY = "neutral.history"
    SCHEDULE = "neutral.schedule"
    FALLBACK = "fallback"


@dataclass(frozen=True, slots=True)
class IconSpec:
    filename: str
    label: str


_SPECS: Final[dict[IconId, IconSpec]] = {
    IconId.NAV_DASHBOARD: IconSpec("dashboard.svg", "Рабочий стол"),
    IconId.NAV_TENDERS: IconSpec("tenders.svg", "Тендеры"),
    IconId.NAV_WORKFLOW: IconSpec("workflow.svg", "Рабочие процессы"),
    IconId.NAV_ANALYTICS: IconSpec("analytics.svg", "Аналитика тендеров"),
    IconId.TOPBAR_SEARCH: IconSpec("search.svg", "Поиск"),
    IconId.TOPBAR_AI: IconSpec("ai.svg", "AI-помощник"),
    IconId.TOPBAR_NOTIFICATIONS: IconSpec("notifications.svg", "Уведомления"),
    IconId.TOPBAR_THEME: IconSpec("theme.svg", "Сменить тему"),
    IconId.TOPBAR_PROFILE: IconSpec("profile.svg", "Профиль"),
    IconId.ACTION_ADD: IconSpec("add.svg", "Добавить"),
    IconId.ACTION_EDIT: IconSpec("edit.svg", "Изменить"),
    IconId.ACTION_DELETE: IconSpec("delete.svg", "Удалить"),
    IconId.ACTION_REFRESH: IconSpec("refresh.svg", "Обновить"),
    IconId.ACTION_IMPORT: IconSpec("import.svg", "Импортировать"),
    IconId.ACTION_EXPORT: IconSpec("export.svg", "Экспортировать"),
    IconId.ACTION_BACK: IconSpec("back.svg", "Назад"),
    IconId.ACTION_CLOSE: IconSpec("close.svg", "Закрыть"),
    IconId.STATE_INFO: IconSpec("info.svg", "Информация"),
    IconId.STATE_SUCCESS: IconSpec("success.svg", "Успешно"),
    IconId.STATE_WARNING: IconSpec("warning.svg", "Предупреждение"),
    IconId.STATE_DANGER: IconSpec("danger.svg", "Ошибка"),
    IconId.STATE_LOADING: IconSpec("loading.svg", "Загрузка"),
    IconId.STATE_EMPTY: IconSpec("empty.svg", "Нет данных"),
    IconId.DOCUMENTS: IconSpec("documents.svg", "Документы"),
    IconId.SETTINGS: IconSpec("settings.svg", "Настройки"),
    IconId.HISTORY: IconSpec("history.svg", "История"),
    IconId.SCHEDULE: IconSpec("schedule.svg", "Расписание"),
    IconId.FALLBACK: IconSpec("fallback.svg", "Неизвестная иконка"),
}

ICON_REGISTRY: Final[Mapping[IconId, IconSpec]] = MappingProxyType(_SPECS)


class IconProvider:
    """Resolve semantic IDs with a bounded in-memory cache and safe fallback."""

    def __init__(self, asset_root: Path | None = None) -> None:
        self._asset_root = asset_root or (PathManager.instance().paths.assets_dir / "icons")
        self._cache: dict[tuple[IconId, ThemeName], QIcon] = {}
        self._fallback_count = 0

    @property
    def fallback_count(self) -> int:
        return self._fallback_count

    def icon(self, icon_id: IconId | str, *, theme: ThemeName | str = ThemeName.DARK) -> QIcon:
        try:
            normalized = icon_id if isinstance(icon_id, IconId) else IconId(icon_id)
        except (TypeError, ValueError):
            normalized = IconId.FALLBACK
        normalized_theme = ThemeName(theme)
        key = (normalized, normalized_theme)
        if key in self._cache:
            return QIcon(self._cache[key])

        spec = ICON_REGISTRY.get(normalized, ICON_REGISTRY[IconId.FALLBACK])
        path = self._asset_root / spec.filename
        icon = QIcon(str(path)) if path.is_file() else QIcon()
        if icon.isNull():
            self._fallback_count += 1
            icon = self._safe_fallback(normalized_theme)
        if len(self._cache) < len(IconId) * len(ThemeName):
            self._cache[key] = QIcon(icon)
        return icon

    @staticmethod
    def _safe_fallback(theme: ThemeName) -> QIcon:
        size = int(IconSize.L)
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        pen = QPen(QColor(get_palette(theme).text_secondary))
        pen.setWidth(2)
        painter.setPen(pen)
        inset = 2
        painter.drawRoundedRect(inset, inset, size - (inset * 2), size - (inset * 2), 4, 4)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "?")
        painter.end()
        return QIcon(pixmap)


_DEFAULT_PROVIDER: IconProvider | None = None


def get_icon_provider() -> IconProvider:
    global _DEFAULT_PROVIDER
    if _DEFAULT_PROVIDER is None:
        _DEFAULT_PROVIDER = IconProvider()
    return _DEFAULT_PROVIDER


__all__ = ["ICON_REGISTRY", "IconId", "IconProvider", "IconSpec", "get_icon_provider"]
