"""Read-only C20 queue showing aggregator discoveries awaiting official checks."""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.tenders.collector.aggregator_discovery import (
    AggregatorDiscoveryRecord,
    AggregatorDiscoveryRepository,
)


class AggregatorDiscoveryDialog(QDialog):
    def __init__(
        self,
        repository: AggregatorDiscoveryRepository,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self._records: tuple[AggregatorDiscoveryRecord, ...] = ()
        self.setWindowTitle("Очередь официальной проверки C20")
        self.resize(1050, 620)
        root = QVBoxLayout(self)
        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels(
            (
                "Статус",
                "Агрегатор",
                "Название",
                "Запрос в официальный источник",
                "Обнаружено",
                "Примечание",
            )
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemDoubleClicked.connect(lambda _item: self.open_selected_source())
        root.addWidget(self.table, 1)
        actions = QHBoxLayout()
        refresh = QPushButton("Обновить", self)
        open_source = QPushButton("Открыть карточку агрегатора", self)
        refresh.clicked.connect(self.refresh)
        open_source.clicked.connect(self.open_selected_source)
        actions.addWidget(refresh)
        actions.addWidget(open_source)
        actions.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        actions.addWidget(buttons)
        root.addLayout(actions)
        self.refresh()

    def refresh(self) -> None:
        self._records = self.repository.list_all()
        self.table.setRowCount(len(self._records))
        for row, record in enumerate(self._records):
            values = (
                record.status.value,
                record.aggregator_source,
                record.title,
                record.official_query,
                record.last_discovered_at,
                record.verification_note,
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))

    def open_selected_source(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self._records):
            QDesktopServices.openUrl(QUrl(self._records[row].source_url))


__all__ = ["AggregatorDiscoveryDialog"]
