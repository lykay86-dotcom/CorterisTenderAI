"""Tender-document browser with background-download controls."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.tenders.document_storage import (
    DocumentDownloadStatus,
    StoredTenderDocument,
    TenderDocumentDownloadResult,
    TenderDocumentStore,
)
from app.tenders.models import UnifiedTender
from app.tenders.tender_registry import tender_registry_key
from app.ui.theme.colors import ThemeName, get_palette


_STATUS_LABELS: dict[DocumentDownloadStatus, str] = {
    DocumentDownloadStatus.DOWNLOADED: "Загружен",
    DocumentDownloadStatus.REUSED: "Уже сохранён",
    DocumentDownloadStatus.DEDUPLICATED: "Объединён",
    DocumentDownloadStatus.FAILED: "Ошибка",
}


class TenderDocumentsDialog(QDialog):
    """Show local tender files and request background downloads."""

    download_requested = Signal(object, bool)
    analysis_requested = Signal(str)

    def __init__(
        self,
        tender: UnifiedTender,
        store: TenderDocumentStore,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.tender = tender
        self.store = store
        self.registry_key = tender_registry_key(tender)
        try:
            self._theme = ThemeName(theme)
        except (TypeError, ValueError, AttributeError):
            self._theme = ThemeName.DARK

        self._documents: tuple[StoredTenderDocument, ...] = ()
        self._download_busy = False

        self.setWindowTitle("Corteris Tender AI — документация закупки")
        self.setModal(False)
        self.resize(1120, 650)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        summary = QFrame(self)
        summary.setObjectName("TenderDocumentsSummary")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(14, 12, 14, 12)
        summary_layout.setSpacing(20)

        heading = QVBoxLayout()
        title = QLabel(tender.title, summary)
        title.setObjectName("TenderDocumentsTitle")
        title.setWordWrap(True)
        subtitle = QLabel(
            (f"Закупка № {tender.procurement_number} · Источник: {tender.source.value}"),
            summary,
        )
        subtitle.setObjectName("TenderDocumentsSubtitle")
        subtitle.setWordWrap(True)
        heading.addWidget(title)
        heading.addWidget(subtitle)
        summary_layout.addLayout(heading, 1)

        self.total_metric = self._add_metric(
            summary_layout,
            summary,
            "Документов",
        )
        self.available_metric = self._add_metric(
            summary_layout,
            summary,
            "Локально",
        )
        self.failed_metric = self._add_metric(
            summary_layout,
            summary,
            "Ошибок",
        )
        root.addWidget(summary)

        table_frame = QFrame(self)
        table_frame.setObjectName("TenderDocumentsTableFrame")
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(10, 10, 10, 10)
        table_layout.setSpacing(8)

        self.table = QTableWidget(table_frame)
        self.table.setObjectName("TenderDocumentsTable")
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            (
                "Статус",
                "Документ",
                "Размер",
                "Загружен",
                "Локальный файл",
                "Ошибка",
            )
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        self.table.horizontalHeader().setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.Stretch,
        )
        self.table.itemSelectionChanged.connect(self._update_selection_actions)
        self.table.cellDoubleClicked.connect(lambda _row, _column: self._open_selected_file())
        table_layout.addWidget(self.table, 1)
        root.addWidget(table_frame, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        self.download_button = QPushButton(
            "Скачать/обновить",
            self,
        )
        self.download_button.setObjectName("PrimaryActionButton")
        self.download_button.clicked.connect(
            lambda: self.download_requested.emit(
                self.tender,
                False,
            )
        )

        self.force_download_button = QPushButton(
            "Скачать заново",
            self,
        )
        self.force_download_button.clicked.connect(
            lambda: self.download_requested.emit(
                self.tender,
                True,
            )
        )

        self.analysis_button = QPushButton(
            "Анализировать требования",
            self,
        )
        self.analysis_button.setObjectName("PrimaryActionButton")
        self.analysis_button.clicked.connect(
            lambda: self.analysis_requested.emit(self.registry_key)
        )

        self.open_file_button = QPushButton(
            "Открыть файл",
            self,
        )
        self.open_file_button.clicked.connect(self._open_selected_file)

        self.open_folder_button = QPushButton(
            "Открыть папку",
            self,
        )
        self.open_folder_button.clicked.connect(self._open_tender_folder)

        self.refresh_button = QPushButton(
            "Обновить список",
            self,
        )
        self.refresh_button.clicked.connect(self.refresh_documents)

        actions.addWidget(self.download_button)
        actions.addWidget(self.force_download_button)
        actions.addWidget(self.analysis_button)
        actions.addWidget(self.open_file_button)
        actions.addWidget(self.open_folder_button)
        actions.addWidget(self.refresh_button)
        actions.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
            self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Закрыть")
        buttons.rejected.connect(self.reject)
        actions.addWidget(buttons)
        root.addLayout(actions)

        self.status_label = QLabel("", self)
        self.status_label.setObjectName("TenderDocumentsStatus")
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.status_label)

        self.apply_theme(self._theme)
        self.refresh_documents()

    @property
    def documents(self) -> tuple[StoredTenderDocument, ...]:
        return self._documents

    @property
    def download_busy(self) -> bool:
        return self._download_busy

    @staticmethod
    def _add_metric(
        layout: QHBoxLayout,
        parent: QWidget,
        label: str,
    ) -> QLabel:
        column = QVBoxLayout()
        value = QLabel("0", parent)
        value.setObjectName("TenderDocumentsMetricValue")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption = QLabel(label, parent)
        caption.setObjectName("TenderDocumentsMetricLabel")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(value)
        column.addWidget(caption)
        layout.addLayout(column)
        return value

    def refresh_documents(self) -> None:
        selected_key = (
            self.selected_document().document_key if self.selected_document() is not None else ""
        )
        try:
            self._documents = self.store.list_documents(self.registry_key)
        except Exception as exc:
            self._documents = ()
            self._populate_table()
            self.set_status(
                f"Не удалось прочитать каталог документов: {exc}",
                error=True,
            )
            return

        self._populate_table(selected_key)
        available_count = sum(document.available_locally for document in self._documents)
        failed_count = sum(
            document.status == DocumentDownloadStatus.FAILED for document in self._documents
        )
        self.total_metric.setText(str(len(self._documents)))
        self.available_metric.setText(str(available_count))
        self.failed_metric.setText(str(failed_count))

        if not self._download_busy:
            if self._documents:
                self.set_status((f"Локальная папка: {self.store.tender_folder(self.tender)}"))
            else:
                self.set_status("Документы ещё не загружены. Нажмите «Скачать/обновить».")

    def _populate_table(self, selected_key: str = "") -> None:
        self.table.setRowCount(len(self._documents))
        selected_row = -1

        for row, document in enumerate(self._documents):
            local_path = str(document.local_path) if document.local_path is not None else "—"
            values = (
                _STATUS_LABELS.get(
                    document.status,
                    document.status.value,
                ),
                document.name,
                _format_bytes(document.size_bytes),
                _format_timestamp(document.downloaded_at),
                local_path,
                document.error_message or "—",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        document.document_key,
                    )
                self.table.setItem(row, column, item)

            if document.document_key == selected_key:
                selected_row = row

        if self._documents:
            self.table.selectRow(selected_row if selected_row >= 0 else 0)
        self._update_selection_actions()

    def selected_document(self) -> StoredTenderDocument | None:
        row = self.table.currentRow()
        if not 0 <= row < len(self._documents):
            return None
        return self._documents[row]

    def set_download_busy(
        self,
        busy: bool,
        *,
        message: str = "",
    ) -> None:
        self._download_busy = bool(busy)
        self.download_button.setEnabled(not busy)
        self.force_download_button.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy)
        self.table.setEnabled(not busy)
        self._update_selection_actions()

        if busy:
            self.set_status(message or "Загрузка документации выполняется в фоне…")

    def set_download_result(
        self,
        result: TenderDocumentDownloadResult,
    ) -> None:
        self.set_download_busy(False)
        self.refresh_documents()

        parts = [
            f"Документов: {result.total_count}",
            f"загружено: {result.downloaded_count}",
            f"уже было локально: {result.reused_count}",
            f"ошибок: {result.failed_count}",
        ]
        if result.catalog_warning:
            parts.append(f"предупреждение: {result.catalog_warning}")
        self.set_status("; ".join(parts), error=result.failed_count > 0)

    def set_download_error(self, message: str) -> None:
        self.set_download_busy(False)
        self.set_status(
            f"Не удалось скачать документацию: {message}",
            error=True,
        )

    def _update_selection_actions(self) -> None:
        document = self.selected_document()
        available = not self._download_busy and document is not None and document.available_locally
        has_local_documents = not self._download_busy and any(
            item.available_locally for item in self._documents
        )
        self.analysis_button.setEnabled(has_local_documents)
        self.open_file_button.setEnabled(available)
        self.open_folder_button.setEnabled(not self._download_busy)

    def _open_selected_file(self) -> None:
        document = self.selected_document()
        if document is None or document.local_path is None or not document.local_path.is_file():
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(document.local_path)))

    def _open_tender_folder(self) -> None:
        folder = self.store.tender_folder(self.tender)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("error", error)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {palette.app_background};
                color: {palette.text_primary};
            }}
            QFrame#TenderDocumentsSummary,
            QFrame#TenderDocumentsTableFrame {{
                background-color: {palette.card_background};
                border: 1px solid {palette.border_default};
                border-radius: 9px;
            }}
            QLabel#TenderDocumentsTitle {{
                color: {palette.text_primary};
                font-size: 20px;
                font-weight: 700;
            }}
            QLabel#TenderDocumentsSubtitle,
            QLabel#TenderDocumentsMetricLabel {{
                color: {palette.text_secondary};
            }}
            QLabel#TenderDocumentsMetricValue {{
                color: {palette.brand_accent};
                font-size: 21px;
                font-weight: 700;
            }}
            QLabel#TenderDocumentsStatus {{
                color: {palette.text_secondary};
            }}
            QLabel#TenderDocumentsStatus[error="true"] {{
                color: {palette.danger};
            }}
            QTableWidget#TenderDocumentsTable {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                alternate-background-color: {palette.panel_background};
                border: 1px solid {palette.border_default};
                gridline-color: {palette.divider};
                selection-background-color: {palette.selected_background};
                selection-color: {palette.text_primary};
            }}
            QHeaderView::section {{
                color: {palette.text_secondary};
                background-color: {palette.elevated_background};
                border: none;
                border-right: 1px solid {palette.divider};
                border-bottom: 1px solid {palette.divider};
                padding: 7px;
                font-weight: 600;
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
            """
        )


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "Не указан"
    size = float(value)
    units = ("Б", "КБ", "МБ", "ГБ")
    unit = units[0]
    for current in units:
        unit = current
        if size < 1024 or current == units[-1]:
            break
        size /= 1024
    return f"{int(size)} {unit}" if unit == "Б" else f"{size:.1f} {unit}"


def _format_timestamp(value: str) -> str:
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.strftime("%d.%m.%Y %H:%M")


__all__ = ["TenderDocumentsDialog"]
