"""Editable C17 matching-catalog table."""

from __future__ import annotations

from uuid import uuid4

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.tenders.corteris_filter import TenderDirection
from app.tenders.matching_catalog import (
    MatchingCatalogEntry,
    MatchingCatalogRepository,
    MatchingCatalogSettings,
    MatchingEntryKind,
)


_HEADERS = (
    "Активно", "Группа", "Значение", "Тип", "Направление",
    "Каноническое значение", "Вес, %", "Категория", "Источник",
)


class MatchingCatalogDialog(QDialog):
    catalog_saved = Signal(object)

    def __init__(
        self,
        repository: MatchingCatalogRepository,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self._settings = MatchingCatalogSettings()
        self.setWindowTitle("Corteris Tender AI — каталог сопоставления C17")
        self.resize(1280, 720)

        root = QVBoxLayout(self)
        note = QLabel(
            "Ключевые слова, сокращения, синонимы, транслитерация, ОКПД2 и "
            "исключения применяются к поиску и рейтингу. Жёсткое исключение "
            "задаётся только типом «Исключение».",
            self,
        )
        note.setWordWrap(True)
        root.addWidget(note)

        thresholds = QHBoxLayout()
        self.minimum_score = self._spin(0, 100)
        self.medium_score = self._spin(0, 100)
        self.high_score = self._spin(0, 100)
        for label, widget in (
            ("Минимум", self.minimum_score),
            ("Средний", self.medium_score),
            ("Высокий", self.high_score),
        ):
            thresholds.addWidget(QLabel(label, self))
            thresholds.addWidget(widget)
        thresholds.addStretch(1)
        root.addLayout(thresholds)

        self.table = QTableWidget(0, len(_HEADERS), self)
        self.table.setHorizontalHeaderLabels(_HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        add_button = QPushButton("Добавить", self)
        remove_button = QPushButton("Удалить выбранные", self)
        reset_button = QPushButton("Сбросить к исходному каталогу", self)
        save_button = QPushButton("Сохранить", self)
        close_button = QPushButton("Закрыть", self)
        add_button.clicked.connect(self.add_empty_row)
        remove_button.clicked.connect(self.remove_selected_rows)
        reset_button.clicked.connect(self.reset_defaults)
        save_button.clicked.connect(self.save_catalog)
        close_button.clicked.connect(self.close)
        for button in (add_button, remove_button, reset_button):
            actions.addWidget(button)
        actions.addStretch(1)
        actions.addWidget(save_button)
        actions.addWidget(close_button)
        root.addLayout(actions)

    @staticmethod
    def _spin(minimum: int, maximum: int) -> QSpinBox:
        widget = QSpinBox()
        widget.setRange(minimum, maximum)
        return widget

    def load_catalog(self) -> None:
        catalog = self.repository.load()
        self._settings = catalog.settings
        self.minimum_score.setValue(catalog.settings.minimum_score)
        self.medium_score.setValue(catalog.settings.medium_score)
        self.high_score.setValue(catalog.settings.high_score)
        self.table.setRowCount(0)
        for entry in catalog.entries:
            self._append_entry(entry)

    def _append_entry(self, entry: MatchingCatalogEntry) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        active = QCheckBox(self.table)
        active.setChecked(entry.active)
        self.table.setCellWidget(row, 0, active)
        for column, value in (
            (1, entry.group_key), (2, entry.term),
            (5, entry.canonical_term), (7, entry.category), (8, entry.source),
        ):
            item = QTableWidgetItem(value)
            if column == 2:
                item.setData(Qt.ItemDataRole.UserRole, entry.entry_id)
            self.table.setItem(row, column, item)
        kind = QComboBox(self.table)
        for value in MatchingEntryKind:
            kind.addItem(_kind_label(value), value.value)
        kind.setCurrentIndex(kind.findData(entry.kind.value))
        self.table.setCellWidget(row, 3, kind)
        direction = QComboBox(self.table)
        direction.addItem("—", "")
        for value in TenderDirection:
            direction.addItem(value.value, value.value)
        direction.setCurrentIndex(
            direction.findData(entry.direction.value if entry.direction else "")
        )
        self.table.setCellWidget(row, 4, direction)
        weight = self._spin(0, 500)
        weight.setValue(entry.weight_percent)
        self.table.setCellWidget(row, 6, weight)

    def add_empty_row(self) -> None:
        self._append_entry(MatchingCatalogEntry(
            entry_id=uuid4().hex,
            group_key="new_group",
            term="новое значение",
            kind=MatchingEntryKind.STRONG_KEYWORD,
            direction=TenderDirection.VIDEO_SURVEILLANCE,
            source="user",
        ))

    def remove_selected_rows(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)

    def save_catalog(self) -> None:
        try:
            settings = MatchingCatalogSettings(
                **{
                    **{name: getattr(self._settings, name) for name in self._settings.__dataclass_fields__},
                    "minimum_score": self.minimum_score.value(),
                    "medium_score": self.medium_score.value(),
                    "high_score": self.high_score.value(),
                }
            )
            catalog = self.repository.save(self._entries(), settings)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Каталог не сохранён", str(exc))
            return
        self._settings = catalog.settings
        self.catalog_saved.emit(catalog)
        QMessageBox.information(self, "Каталог", f"Сохранена ревизия {catalog.revision}.")

    def reset_defaults(self) -> None:
        answer = QMessageBox.question(
            self,
            "Сброс каталога",
            "Заменить текущие правила исходным каталогом? Предыдущая ревизия сохранится в истории.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        catalog = self.repository.reset_defaults()
        self.catalog_saved.emit(catalog)
        self.load_catalog()

    def _entries(self) -> tuple[MatchingCatalogEntry, ...]:
        result = []
        for row in range(self.table.rowCount()):
            kind_widget = self.table.cellWidget(row, 3)
            direction_widget = self.table.cellWidget(row, 4)
            active_widget = self.table.cellWidget(row, 0)
            weight_widget = self.table.cellWidget(row, 6)
            assert isinstance(kind_widget, QComboBox)
            assert isinstance(direction_widget, QComboBox)
            assert isinstance(active_widget, QCheckBox)
            assert isinstance(weight_widget, QSpinBox)
            term_item = self.table.item(row, 2)
            entry_id = str(term_item.data(Qt.ItemDataRole.UserRole) or uuid4().hex)
            direction_value = str(direction_widget.currentData() or "")
            result.append(MatchingCatalogEntry(
                entry_id=entry_id,
                group_key=self._text(row, 1),
                term=self._text(row, 2),
                kind=MatchingEntryKind(str(kind_widget.currentData())),
                direction=TenderDirection(direction_value) if direction_value else None,
                canonical_term=self._text(row, 5),
                weight_percent=weight_widget.value(),
                category=self._text(row, 7),
                source=self._text(row, 8) or "user",
                active=active_widget.isChecked(),
            ))
        return tuple(result)

    def _text(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        return item.text().strip() if item is not None else ""


def _kind_label(kind: MatchingEntryKind) -> str:
    return {
        MatchingEntryKind.STRONG_KEYWORD: "Ключевое слово — сильное",
        MatchingEntryKind.WEAK_KEYWORD: "Ключевое слово — слабое",
        MatchingEntryKind.ACTION: "Действие",
        MatchingEntryKind.ABBREVIATION: "Сокращение",
        MatchingEntryKind.SYNONYM: "Синоним",
        MatchingEntryKind.TRANSLITERATION: "Транслитерация",
        MatchingEntryKind.OKPD2: "ОКПД2",
        MatchingEntryKind.EXCLUSION: "Исключение",
    }[kind]


__all__ = ["MatchingCatalogDialog"]
