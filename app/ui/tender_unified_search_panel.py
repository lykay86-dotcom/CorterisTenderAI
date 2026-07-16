"""Reusable presentation-only panel for unified tender search."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.tenders.collector.models import CollectionRunStatus, CollectorRunResult
from app.tenders.collector.progress import CollectorProgressEvent, CollectorProgressPhase
from app.tenders.collector.provider_control import ProviderDisplayState
from app.tenders.search_profiles import TenderSearchProfile
from app.tenders.unified_search import UnifiedTenderSearchRequest
from app.ui.theme.colors import ThemeName, get_palette


class TenderUnifiedSearchPanel(QFrame):
    """Collect UI input and render one existing Collector run state."""

    start_requested = Signal(object)
    stop_requested = Signal()
    profiles_requested = Signal()
    sources_requested = Signal()
    registry_requested = Signal()
    query_submitted = Signal(str)

    def __init__(
        self,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        try:
            self._theme = ThemeName(theme)
        except (TypeError, ValueError, AttributeError):
            self._theme = ThemeName.DARK
        self._profiles: tuple[TenderSearchProfile, ...] = ()
        self._provider_states: tuple[ProviderDisplayState, ...] = ()
        self._running = False
        self._completed_providers: set[str] = set()

        self.setObjectName("TenderUnifiedSearchPanel")
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        title = QLabel("Поиск тендеров", self)
        title.setObjectName("UnifiedTenderSearchTitle")
        root.addWidget(title)

        setup = QGridLayout()
        setup.setHorizontalSpacing(8)
        setup.setVerticalSpacing(6)
        setup.addWidget(QLabel("Профиль", self), 0, 0)
        self.profile_combo = QComboBox(self)
        self.profile_combo.setObjectName("UnifiedTenderSearchProfileCombo")
        self.profile_combo.currentIndexChanged.connect(self._profile_changed)
        setup.addWidget(self.profile_combo, 0, 1)

        self.profiles_button = QPushButton("Профили…", self)
        self.profiles_button.setObjectName("UnifiedTenderSearchProfilesButton")
        self.profiles_button.clicked.connect(lambda _checked=False: self.profiles_requested.emit())
        setup.addWidget(self.profiles_button, 0, 2)

        self.sources_button = QPushButton("Источники…", self)
        self.sources_button.setObjectName("UnifiedTenderSearchSourcesButton")
        self.sources_button.clicked.connect(lambda _checked=False: self.sources_requested.emit())
        setup.addWidget(self.sources_button, 0, 3)

        setup.addWidget(QLabel("Уточнение", self), 1, 0)
        self.query_edit = QLineEdit(self)
        self.query_edit.setObjectName("UnifiedTenderSearchQuery")
        self.query_edit.setPlaceholderText("Необязательно — без уточнения используется профиль")
        self.query_edit.returnPressed.connect(self._request_start)
        setup.addWidget(self.query_edit, 1, 1, 1, 3)
        setup.setColumnStretch(1, 1)
        root.addLayout(setup)

        self.profile_summary = QLabel("Нет доступных профилей поиска.", self)
        self.profile_summary.setObjectName("UnifiedTenderSearchProfileSummary")
        self.profile_summary.setWordWrap(True)
        root.addWidget(self.profile_summary)

        self.provider_list = QListWidget(self)
        self.provider_list.setObjectName("UnifiedTenderSearchProviders")
        self.provider_list.setMaximumHeight(110)
        self.provider_list.itemChanged.connect(lambda _item: self._update_start_enabled())
        root.addWidget(self.provider_list)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setObjectName("UnifiedTenderSearchProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        root.addWidget(self.progress_bar)

        self.status_label = QLabel("Выберите профиль и доступные источники.", self)
        self.status_label.setObjectName("UnifiedTenderSearchStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        actions = QHBoxLayout()
        self.start_button = QPushButton("Найти тендеры", self)
        self.start_button.setObjectName("UnifiedTenderSearchStartButton")
        self.start_button.clicked.connect(self._request_start)
        self.stop_button = QPushButton("Остановить", self)
        self.stop_button.setObjectName("UnifiedTenderSearchStopButton")
        self.stop_button.clicked.connect(lambda _checked=False: self.stop_requested.emit())
        self.stop_button.setEnabled(False)
        self.registry_button = QPushButton("Открыть реестр", self)
        self.registry_button.setObjectName("UnifiedTenderSearchRegistryButton")
        self.registry_button.clicked.connect(lambda _checked=False: self.registry_requested.emit())
        actions.addWidget(self.start_button)
        actions.addWidget(self.stop_button)
        actions.addWidget(self.registry_button)
        actions.addStretch(1)
        root.addLayout(actions)

        self.apply_theme(self._theme)
        self._update_start_enabled()

    @property
    def running(self) -> bool:
        return self._running

    def set_profiles(
        self,
        profiles: Iterable[TenderSearchProfile],
        *,
        select_id: str = "",
    ) -> None:
        current_id = str(select_id or self.selected_profile_id()).strip().casefold()
        self._profiles = tuple(profile for profile in profiles if profile.enabled)
        self.profile_combo.blockSignals(True)
        try:
            self.profile_combo.clear()
            selected_index = 0
            for index, profile in enumerate(self._profiles):
                self.profile_combo.addItem(profile.name, profile.id)
                if profile.id == current_id:
                    selected_index = index
            if self._profiles:
                self.profile_combo.setCurrentIndex(selected_index)
        finally:
            self.profile_combo.blockSignals(False)
        self._profile_changed()

    def set_provider_states(
        self,
        states: Iterable[ProviderDisplayState],
        *,
        preserve_selection: bool = True,
    ) -> None:
        had_items = self.provider_list.count() > 0
        previous = set(self.selected_provider_ids()) if preserve_selection and had_items else None
        self._provider_states = tuple(states)
        self.provider_list.blockSignals(True)
        try:
            self.provider_list.clear()
            for state in self._provider_states:
                item = QListWidgetItem(f"{state.display_name} — {state.status_text}")
                item.setData(Qt.ItemDataRole.UserRole, state.provider_id)
                if state.enabled:
                    item.setFlags(
                        Qt.ItemFlag.ItemIsSelectable
                        | Qt.ItemFlag.ItemIsEnabled
                        | Qt.ItemFlag.ItemIsUserCheckable
                    )
                    checked = previous is not None and state.provider_id in previous
                    item.setCheckState(
                        Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                    )
                else:
                    item.setFlags(Qt.ItemFlag.ItemIsSelectable)
                    item.setCheckState(Qt.CheckState.Unchecked)
                    item.setToolTip("Источник отключён в настройках.")
                self.provider_list.addItem(item)
        finally:
            self.provider_list.blockSignals(False)
        if previous is None:
            self._select_profile_defaults()
        else:
            self._update_start_enabled()
            if not self.selected_provider_ids():
                self.set_status("У выбранного профиля нет доступных источников.", error=True)

    def selected_profile_id(self) -> str:
        return str(self.profile_combo.currentData() or "").strip().casefold()

    def selected_provider_ids(self) -> tuple[str, ...]:
        selected: list[str] = []
        for index in range(self.provider_list.count()):
            item = self.provider_list.item(index)
            if item.checkState() != Qt.CheckState.Checked:
                continue
            provider_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip().casefold()
            if provider_id:
                selected.append(provider_id)
        return tuple(selected)

    def set_selected_provider_ids(self, provider_ids: Iterable[str]) -> None:
        selected = {str(item).strip().casefold() for item in provider_ids if str(item).strip()}
        self.provider_list.blockSignals(True)
        try:
            for index in range(self.provider_list.count()):
                item = self.provider_list.item(index)
                provider_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip().casefold()
                if bool(item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                    item.setCheckState(
                        Qt.CheckState.Checked
                        if provider_id in selected
                        else Qt.CheckState.Unchecked
                    )
        finally:
            self.provider_list.blockSignals(False)
        self._update_start_enabled()

    def submit_query(self, query: str) -> bool:
        normalized = " ".join(str(query).split())
        self.query_edit.setText(normalized)
        self.query_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        if not normalized:
            self.set_status("Введите поисковый запрос.", error=True)
            return False
        self.query_submitted.emit(normalized)
        return self._request_start()

    def focus_search(self) -> bool:
        self.query_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        return True

    def begin_run(self, profile_name: str, provider_ids: Iterable[str]) -> None:
        self._completed_providers.clear()
        self.progress_bar.setValue(1)
        self.set_status(f"Запуск поиска по профилю «{profile_name}»…")
        self.set_running(True)

    def set_running(self, running: bool) -> None:
        self._running = bool(running)
        self.profile_combo.setEnabled(not self._running)
        self.query_edit.setEnabled(not self._running)
        self.provider_list.setEnabled(not self._running)
        self.profiles_button.setEnabled(not self._running)
        self.sources_button.setEnabled(not self._running)
        self.stop_button.setEnabled(self._running)
        self._update_start_enabled()

    def mark_cancel_requested(self) -> None:
        self.stop_button.setEnabled(False)
        self.set_status("Остановка запрошена. Завершаются активные запросы…")

    def apply_progress(self, event: CollectorProgressEvent) -> None:
        if event.phase == CollectorProgressPhase.PREPARING:
            value = 3
        elif event.phase == CollectorProgressPhase.PROVIDER_COMPLETED:
            self._completed_providers.add(event.provider_id)
            value = 5 + round(len(self._completed_providers) / max(1, event.total_providers) * 65)
        else:
            value = {
                CollectorProgressPhase.NORMALIZING: 76,
                CollectorProgressPhase.DEDUPLICATING: 80,
                CollectorProgressPhase.VERIFYING: 86,
                CollectorProgressPhase.CHECKING_FRESHNESS: 89,
                CollectorProgressPhase.RANKING: 92,
                CollectorProgressPhase.SAVING: 95,
                CollectorProgressPhase.COMPLETED: 100,
                CollectorProgressPhase.CANCELLED: 100,
                CollectorProgressPhase.FAILED: 100,
            }.get(event.phase, self.progress_bar.value())
        self.progress_bar.setValue(max(self.progress_bar.value(), value))
        if event.message:
            self.set_status(event.message, error=event.phase == CollectorProgressPhase.FAILED)

    def set_result(self, result: CollectorRunResult) -> None:
        summary = result.persistence
        if result.status == CollectionRunStatus.CANCELLED:
            message = f"Поиск остановлен. Сохранено результатов: {summary.merged_count}."
        elif result.status == CollectionRunStatus.PARTIAL:
            message = (
                "Поиск завершён частично. "
                f"Новых: {summary.new_count}, изменённых: {summary.changed_count}."
            )
        elif result.status == CollectionRunStatus.COMPLETED:
            message = (
                f"Поиск завершён. Новых: {summary.new_count}, изменённых: {summary.changed_count}."
            )
        else:
            message = "Поиск завершён с неподдерживаемым состоянием."
        self.progress_bar.setValue(100)
        self.set_status(message, error=result.status == CollectionRunStatus.FAILED)
        self.set_running(False)

    def set_error(self, message: str) -> None:
        self.progress_bar.setValue(100)
        self.set_status(message, error=True)
        self.set_running(False)

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.status_label.setText(str(message))
        palette = get_palette(self._theme)
        self.status_label.setStyleSheet(
            f"color: {palette.danger if error else palette.text_secondary};"
        )

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)
        self.setStyleSheet(
            f"QFrame#TenderUnifiedSearchPanel {{ background: {palette.panel_background}; "
            f"border: 1px solid {palette.border_default}; border-radius: 8px; }}"
        )

    def _request_start(self) -> bool:
        profile_id = self.selected_profile_id()
        provider_ids = self.selected_provider_ids()
        if not profile_id:
            self.set_status("Выберите сохранённый профиль поиска.", error=True)
            self.focus_search()
            return False
        if not provider_ids:
            self.set_status("У выбранного профиля нет доступных источников.", error=True)
            return False
        request = UnifiedTenderSearchRequest(
            profile_id=profile_id,
            query_text=" ".join(self.query_edit.text().split()),
            provider_ids=provider_ids,
        )
        self.start_requested.emit(request)
        return True

    def _profile_changed(self, _index: int = -1) -> None:
        profile = self._selected_profile()
        if profile is None:
            self.profile_summary.setText("Нет доступных профилей поиска.")
        else:
            self.profile_summary.setText(profile.description or "Описание профиля не задано.")
        self._select_profile_defaults()

    def _select_profile_defaults(self) -> None:
        profile = self._selected_profile()
        enabled = {state.provider_id for state in self._provider_states if state.enabled}
        defaults = (
            ()
            if profile is None
            else tuple(
                provider_id for provider_id in profile.provider_ids if provider_id in enabled
            )
        )
        self.set_selected_provider_ids(defaults)
        if profile is not None and not defaults:
            self.set_status("У выбранного профиля нет доступных источников.", error=True)
        elif profile is not None:
            self.set_status("Параметры поиска готовы.")

    def _selected_profile(self) -> TenderSearchProfile | None:
        profile_id = self.selected_profile_id()
        return next((profile for profile in self._profiles if profile.id == profile_id), None)

    def _update_start_enabled(self) -> None:
        self.start_button.setEnabled(
            not self._running
            and bool(self.selected_profile_id())
            and bool(self.selected_provider_ids())
        )


__all__ = ["TenderUnifiedSearchPanel"]
