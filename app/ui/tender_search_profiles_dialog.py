"""Search-profile management panel and dialog."""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from PySide6.QtCore import (
    QSignalBlocker,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.tenders.search_profile_repository import (
    BuiltinSearchProfileError,
    SearchProfileCatalogLoadStatus,
    SearchProfileCatalogMutationError,
    SearchProfileNotFoundError,
    TenderSearchProfileRepository,
)
from app.tenders.search_profiles import TenderSearchProfile
from app.ui.tender_search_profile_editor import (
    TenderSearchProfileEditor,
)
from app.ui.theme.colors import ThemeName, get_palette


class TenderSearchProfilesPanel(QWidget):
    """Manage built-in and custom search profiles without modal prompts."""

    profile_run_requested = Signal(str)
    profile_saved = Signal(str)
    profile_deleted = Signal(str)

    def __init__(
        self,
        repository: TenderSearchProfileRepository,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.repository = repository
        self._theme = ThemeName(theme)
        self._draft_is_new = False
        self._search_busy = False
        self._catalog_mutation_blocked = False
        self._catalog_status_message = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        heading_row = QHBoxLayout()
        heading_column = QVBoxLayout()
        heading_column.setSpacing(2)

        title = QLabel("Профили поиска тендеров", self)
        title.setObjectName("SearchProfilesTitle")
        subtitle = QLabel(
            ("Настройка направлений, регионов, цены, законов и тендерных площадок."),
            self,
        )
        subtitle.setObjectName("SearchProfilesSubtitle")
        subtitle.setWordWrap(True)

        heading_column.addWidget(title)
        heading_column.addWidget(subtitle)
        heading_row.addLayout(heading_column, 1)

        self.restore_button = QPushButton(
            "Восстановить пресеты",
            self,
        )
        self.restore_button.clicked.connect(self._restore_builtins)
        heading_row.addWidget(
            self.restore_button,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        root.addLayout(heading_row)

        splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self,
        )
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        left = QFrame(splitter)
        left.setObjectName("SearchProfilesSidebar")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(9)

        list_label = QLabel("Сохранённые профили", left)
        list_label.setObjectName("SearchProfilesListTitle")
        left_layout.addWidget(list_label)

        self.profile_list = QListWidget(left)
        self.profile_list.setObjectName("SearchProfilesList")
        self.profile_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.profile_list.currentItemChanged.connect(self._on_current_item_changed)
        left_layout.addWidget(self.profile_list, 1)

        sidebar_actions = QHBoxLayout()
        sidebar_actions.setSpacing(7)

        self.create_button = QPushButton(
            "Создать копию",
            left,
        )
        self.create_button.clicked.connect(self._create_copy)

        self.delete_button = QPushButton(
            "Удалить",
            left,
        )
        self.delete_button.clicked.connect(self._delete_selected)

        sidebar_actions.addWidget(self.create_button)
        sidebar_actions.addWidget(self.delete_button)
        left_layout.addLayout(sidebar_actions)

        self.toggle_button = QPushButton(
            "Отключить профиль",
            left,
        )
        self.toggle_button.clicked.connect(self._toggle_selected)
        left_layout.addWidget(self.toggle_button)

        splitter.addWidget(left)

        right = QFrame(splitter)
        right.setObjectName("SearchProfilesEditorFrame")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.editor = TenderSearchProfileEditor(
            theme=self._theme,
            parent=right,
        )
        right_layout.addWidget(self.editor, 1)

        editor_actions = QHBoxLayout()
        editor_actions.setContentsMargins(14, 0, 14, 12)
        editor_actions.setSpacing(8)

        self.cancel_button = QPushButton(
            "Отменить создание",
            right,
        )
        self.cancel_button.clicked.connect(self._cancel_draft)

        self.save_button = QPushButton(
            "Сохранить профиль",
            right,
        )
        self.save_button.setObjectName("PrimaryActionButton")
        self.save_button.clicked.connect(self._save_profile)

        self.run_button = QPushButton(
            "Запустить поиск",
            right,
        )
        self.run_button.setObjectName("PrimaryActionButton")
        self.run_button.clicked.connect(self._run_selected)

        editor_actions.addWidget(self.cancel_button)
        editor_actions.addStretch(1)
        editor_actions.addWidget(self.save_button)
        editor_actions.addWidget(self.run_button)
        right_layout.addLayout(editor_actions)

        splitter.addWidget(right)
        splitter.setSizes([330, 790])

        self.status_label = QLabel("", self)
        self.status_label.setObjectName("SearchProfilesStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.repository.initialize()
        self._refresh_profiles()
        self.apply_theme(self._theme)

    def refresh_profiles(
        self,
        *,
        select_id: str | None = None,
    ) -> None:
        self._refresh_profiles(select_id=select_id)

    def set_search_busy(
        self,
        busy: bool,
        *,
        profile_id: str | None = None,
    ) -> None:
        self._search_busy = bool(busy)
        self.profile_list.setEnabled(not self._search_busy)
        if self._search_busy:
            profile = None
            if profile_id:
                try:
                    profile = self.repository.get(profile_id)
                except SearchProfileNotFoundError:
                    profile = None
            name = profile.name if profile is not None else "профиля"
            self._set_status(f"Выполняется поиск по профилю «{name}»…")
        self._update_actions()

    def set_status(
        self,
        message: str,
        *,
        error: bool = False,
    ) -> None:
        self._set_status(message, error=error)

    def selected_profile_id(self) -> str | None:
        item = self.profile_list.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value else None

    def selected_profile(self) -> TenderSearchProfile | None:
        profile_id = self.selected_profile_id()
        if profile_id is None:
            return None
        try:
            return self.repository.get(profile_id)
        except SearchProfileNotFoundError:
            return None

    def _refresh_profiles(
        self,
        *,
        select_id: str | None = None,
    ) -> None:
        result = self.repository.load_result()
        profiles = result.profiles
        self._catalog_mutation_blocked = result.status in {
            SearchProfileCatalogLoadStatus.CORRUPT,
            SearchProfileCatalogLoadStatus.UNSUPPORTED_FUTURE,
        }
        self._catalog_status_message = self._catalog_message(result.status)
        preferred_id = (
            select_id or self.selected_profile_id() or (profiles[0].id if profiles else None)
        )

        blocker = QSignalBlocker(self.profile_list)
        self.profile_list.clear()

        selected_row = -1
        for row, profile in enumerate(profiles):
            item = QListWidgetItem(self._profile_item_text(profile))
            item.setData(
                Qt.ItemDataRole.UserRole,
                profile.id,
            )
            item.setToolTip(profile.description)
            self.profile_list.addItem(item)
            if profile.id == preferred_id:
                selected_row = row

        if selected_row >= 0:
            self.profile_list.setCurrentRow(selected_row)
        elif self.profile_list.count():
            self.profile_list.setCurrentRow(0)
        del blocker

        current = self.selected_profile()
        if current is not None:
            self.editor.load_profile(current)
        else:
            self.editor.clear_editor()
        self._draft_is_new = False
        self._update_actions()
        if self._catalog_status_message:
            self._set_status(
                self._catalog_status_message,
                error=self._catalog_mutation_blocked,
            )

    @staticmethod
    def _profile_item_text(
        profile: TenderSearchProfile,
    ) -> str:
        state = "●" if profile.enabled else "○"
        kind = "Встроенный" if profile.is_builtin else "Мой"
        return f"{state}  {profile.name}\n    {kind} · {profile.id}"

    def _on_current_item_changed(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        del previous
        self._draft_is_new = False

        if current is None:
            self.editor.clear_editor()
            self._update_actions()
            return

        profile_id = current.data(Qt.ItemDataRole.UserRole)
        try:
            profile = self.repository.get(str(profile_id))
        except SearchProfileNotFoundError:
            self.editor.clear_editor()
            self._set_status(
                "Выбранный профиль больше не существует.",
                error=True,
            )
            self._update_actions()
            return

        self.editor.load_profile(profile)
        if self._catalog_status_message:
            self._set_status(
                self._catalog_status_message,
                error=self._catalog_mutation_blocked,
            )
        else:
            self._set_status("")
        self._update_actions()

    def _create_copy(self) -> None:
        source = self.selected_profile()
        if source is None:
            profiles = self.repository.list_profiles()
            source = profiles[0] if profiles else None
        if source is None:
            self._set_status(
                "Нет профиля, который можно использовать как основу.",
                error=True,
            )
            return

        draft_id = f"custom-{uuid4().hex[:10]}"
        draft = source.clone_as_custom(
            profile_id=draft_id,
            name=f"{source.name} — копия",
        )
        draft = replace(draft, enabled=True)

        self._draft_is_new = True
        self.editor.load_profile(
            draft,
            allow_id_edit=True,
        )
        self._set_status(
            ("Создана несохранённая копия. Проверьте параметры и нажмите «Сохранить профиль».")
        )
        self._update_actions()

    def _cancel_draft(self) -> None:
        if not self._draft_is_new:
            return

        self._draft_is_new = False
        profile = self.selected_profile()
        if profile is not None:
            self.editor.load_profile(profile)
        else:
            self.editor.clear_editor()
        self._set_status("Создание профиля отменено.")
        self._update_actions()

    def _save_profile(self) -> None:
        if self.editor.profile is None:
            self._set_status(
                "Сначала выберите или создайте профиль.",
                error=True,
            )
            return

        try:
            profile = self.editor.build_profile()
            saved = self.repository.save(
                profile,
                replace_existing=not self._draft_is_new,
            )
        except (TypeError, ValueError, SearchProfileCatalogMutationError) as exc:
            message = str(exc)
            self.editor.show_validation_error(message)
            self._set_status(message, error=True)
            return

        was_new = self._draft_is_new
        self._draft_is_new = False
        self._refresh_profiles(select_id=saved.id)
        self.editor.show_validation_success("Профиль сохранён.")
        self._set_status((f"Профиль «{saved.name}» " + ("создан." if was_new else "обновлён.")))
        self.profile_saved.emit(saved.id)

    def _delete_selected(self) -> None:
        profile = self.selected_profile()
        if profile is None:
            return

        try:
            removed = self.repository.delete(profile.id)
        except BuiltinSearchProfileError:
            self._set_status(
                ("Встроенный профиль удалить нельзя. Его можно отключить или изменить."),
                error=True,
            )
            return
        except SearchProfileNotFoundError:
            self._set_status(
                "Профиль уже удалён.",
                error=True,
            )
            return
        except SearchProfileCatalogMutationError as exc:
            self._set_status(exc.public_message, error=True)
            return

        self._refresh_profiles()
        self._set_status(f"Профиль «{removed.name}» удалён.")
        self.profile_deleted.emit(removed.id)

    def _toggle_selected(self) -> None:
        profile = self.selected_profile()
        if profile is None or self._draft_is_new:
            return

        try:
            updated = self.repository.set_enabled(
                profile.id,
                not profile.enabled,
            )
        except SearchProfileCatalogMutationError as exc:
            self._set_status(exc.public_message, error=True)
            return
        self._refresh_profiles(select_id=updated.id)
        self._set_status(
            (f"Профиль «{updated.name}» " + ("включён." if updated.enabled else "отключён."))
        )

    def _restore_builtins(self) -> None:
        selected_id = self.selected_profile_id()
        try:
            self.repository.restore_builtin_profiles()
        except SearchProfileCatalogMutationError as exc:
            self._set_status(exc.public_message, error=True)
            return
        self._refresh_profiles(select_id=selected_id)
        self._set_status(("Стандартные профили восстановлены. Пользовательские профили сохранены."))

    def _run_selected(self) -> None:
        if self._search_busy:
            self._set_status(
                "Поиск уже выполняется. Дождитесь завершения.",
                error=True,
            )
            return

        if self._draft_is_new:
            self._set_status(
                "Перед запуском сохраните новый профиль.",
                error=True,
            )
            return

        profile = self.selected_profile()
        if profile is None:
            return
        if not profile.enabled:
            self._set_status(
                "Профиль отключён. Сначала включите его.",
                error=True,
            )
            return

        self.profile_run_requested.emit(profile.id)
        self._set_status(f"Запрошен запуск профиля «{profile.name}».")

    def _update_actions(self) -> None:
        profile = self.selected_profile()
        has_profile = profile is not None

        interactive = not self._search_busy and not self._catalog_mutation_blocked
        self.restore_button.setEnabled(interactive)
        self.create_button.setEnabled(has_profile and interactive)
        self.save_button.setEnabled(self.editor.profile is not None and interactive)
        self.cancel_button.setVisible(self._draft_is_new)
        self.cancel_button.setEnabled(interactive)
        self.delete_button.setEnabled(
            has_profile and not self._draft_is_new and not profile.is_builtin and interactive
        )
        self.toggle_button.setEnabled(has_profile and not self._draft_is_new and interactive)
        self.run_button.setEnabled(
            has_profile and not self._draft_is_new and profile.enabled and interactive
        )
        self.run_button.setText("Идёт поиск…" if self._search_busy else "Запустить поиск")

        if has_profile:
            self.toggle_button.setText(
                "Отключить профиль" if profile.enabled else "Включить профиль"
            )
        else:
            self.toggle_button.setText("Отключить профиль")

    @staticmethod
    def _catalog_message(status: SearchProfileCatalogLoadStatus) -> str:
        if status is SearchProfileCatalogLoadStatus.MIGRATED_V1:
            return (
                "Каталог загружен из schema v1. Первая правка создаст резервную "
                "копию и сохранит schema v2."
            )
        if status is SearchProfileCatalogLoadStatus.CORRUPT:
            return (
                "Каталог профилей повреждён. Исходный файл сохранён без изменений; "
                "изменение и запуск заблокированы."
            )
        if status is SearchProfileCatalogLoadStatus.UNSUPPORTED_FUTURE:
            return "Версия каталога новее поддерживаемой. Изменение и запуск заблокированы."
        return ""

    def _set_status(
        self,
        message: str,
        *,
        error: bool = False,
    ) -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("semanticTone", "danger" if error else "success")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def apply_theme(
        self,
        theme: ThemeName | str,
    ) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)
        self.editor.apply_theme(self._theme)

        self.setStyleSheet(
            f"""
            QWidget {{
                color: {palette.text_primary};
            }}
            TenderSearchProfilesPanel {{
                background-color: {palette.app_background};
            }}
            QLabel#SearchProfilesTitle {{
                color: {palette.text_primary};
                font-size: 22px;
                font-weight: 700;
            }}
            QLabel#SearchProfilesSubtitle {{
                color: {palette.text_secondary};
                font-size: 13px;
            }}
            QLabel#SearchProfilesListTitle {{
                color: {palette.text_primary};
                font-size: 14px;
                font-weight: 700;
            }}
            QFrame#SearchProfilesSidebar {{
                background-color: {palette.card_background};
                border: 1px solid {palette.border_default};
                border-radius: 9px;
            }}
            QFrame#SearchProfilesEditorFrame {{
                background-color: {palette.panel_background};
                border: 1px solid {palette.border_default};
                border-radius: 9px;
            }}
            QListWidget#SearchProfilesList {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_default};
                border-radius: 7px;
                padding: 4px;
                outline: none;
            }}
            QListWidget#SearchProfilesList::item {{
                border-radius: 6px;
                padding: 9px 7px;
                margin: 2px 0;
            }}
            QListWidget#SearchProfilesList::item:hover {{
                background-color: {palette.hover_background};
            }}
            QListWidget#SearchProfilesList::item:selected {{
                color: {palette.text_primary};
                background-color: {palette.selected_background};
            }}
            QPushButton {{
                min-height: 32px;
                color: {palette.text_primary};
                background-color: {palette.elevated_background};
                border: 1px solid {palette.border_default};
                border-radius: 7px;
                padding: 4px 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {palette.hover_background};
            }}
            QPushButton:disabled {{
                color: {palette.text_disabled};
                background-color: {palette.neutral_background};
            }}
            QPushButton#PrimaryActionButton {{
                color: {palette.text_on_brand};
                background-color: {palette.brand_primary};
                border-color: {palette.brand_primary};
            }}
            QPushButton#PrimaryActionButton:hover {{
                background-color: {palette.brand_primary_hover};
            }}
            QSplitter::handle {{
                background-color: transparent;
                width: 8px;
            }}
            QLabel#SearchProfilesStatus {{
                min-height: 20px;
                font-size: 12px;
            }}
            """
        )


class TenderSearchProfilesDialog(QDialog):
    """Dialog wrapper suitable for opening from the main application."""

    profile_run_requested = Signal(str)

    def __init__(
        self,
        repository: TenderSearchProfileRepository,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Corteris Tender AI — профили поиска")
        self.setModal(True)
        self.resize(1180, 780)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.panel = TenderSearchProfilesPanel(
            repository,
            theme=theme,
            parent=self,
        )
        self.panel.profile_run_requested.connect(self.profile_run_requested.emit)
        root.addWidget(self.panel, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
            self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Закрыть")
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def refresh_profiles(
        self,
        *,
        select_id: str | None = None,
    ) -> None:
        self.panel.refresh_profiles(select_id=select_id)

    def set_search_busy(
        self,
        busy: bool,
        *,
        profile_id: str | None = None,
    ) -> None:
        self.panel.set_search_busy(
            busy,
            profile_id=profile_id,
        )

    def set_status(
        self,
        message: str,
        *,
        error: bool = False,
    ) -> None:
        self.panel.set_status(message, error=error)


__all__ = [
    "TenderSearchProfilesDialog",
    "TenderSearchProfilesPanel",
]
