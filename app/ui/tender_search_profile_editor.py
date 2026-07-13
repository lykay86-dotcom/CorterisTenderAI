"""Editor widget for saved Corteris tender-search profiles."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.tenders.corteris_filter import TenderDirection
from app.tenders.search_profiles import TenderSearchProfile
from app.ui.theme.colors import ThemeName, get_palette


DIRECTION_LABELS: Final[tuple[tuple[TenderDirection, str], ...]] = (
    (
        TenderDirection.VIDEO_SURVEILLANCE,
        "Видеонаблюдение",
    ),
    (TenderDirection.OPS, "ОПС и пожарная автоматика"),
    (TenderDirection.SKUD, "СКУД и контроль доступа"),
    (TenderDirection.BARRIERS, "Шлагбаумы и ворота"),
    (TenderDirection.ANPR, "Распознавание номеров"),
    (TenderDirection.MAINTENANCE, "Обслуживание"),
    (
        TenderDirection.INTEGRATED_SECURITY,
        "Комплексные системы безопасности",
    ),
)


class TenderSearchProfileEditor(QWidget):
    """Form that converts UI fields to and from TenderSearchProfile."""

    profile_changed = Signal()

    def __init__(
        self,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._theme = ThemeName(theme)
        self._profile: TenderSearchProfile | None = None
        self._allow_id_edit = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget(self.scroll_area)
        content.setObjectName("SearchProfileEditorContent")
        self.scroll_area.setWidget(content)
        outer.addWidget(self.scroll_area)

        root = QVBoxLayout(content)
        root.setContentsMargins(18, 16, 18, 18)
        root.setSpacing(14)

        title = QLabel("Параметры профиля", content)
        title.setObjectName("ProfileEditorTitle")
        root.addWidget(title)

        self.kind_label = QLabel("", content)
        self.kind_label.setObjectName("ProfileKindLabel")
        root.addWidget(self.kind_label)

        identity_group = QGroupBox("Название и описание", content)
        identity_layout = QFormLayout(identity_group)
        identity_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.profile_id_edit = QLineEdit(identity_group)
        self.profile_id_edit.setPlaceholderText("Например: moscow-video-service")
        self.profile_id_edit.textChanged.connect(self._emit_changed)
        identity_layout.addRow("ID профиля", self.profile_id_edit)

        self.name_edit = QLineEdit(identity_group)
        self.name_edit.setPlaceholderText("Название, которое будет видно в списке")
        self.name_edit.textChanged.connect(self._emit_changed)
        identity_layout.addRow("Название", self.name_edit)

        self.description_edit = QPlainTextEdit(identity_group)
        self.description_edit.setPlaceholderText("Кратко опишите назначение профиля")
        self.description_edit.setFixedHeight(72)
        self.description_edit.textChanged.connect(self._emit_changed)
        identity_layout.addRow("Описание", self.description_edit)

        root.addWidget(identity_group)

        keyword_group = QGroupBox("Поисковые фразы", content)
        keyword_layout = QFormLayout(keyword_group)
        keyword_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.keywords_edit = QPlainTextEdit(keyword_group)
        self.keywords_edit.setPlaceholderText("Одна фраза на строку или через запятую")
        self.keywords_edit.setFixedHeight(105)
        self.keywords_edit.textChanged.connect(self._emit_changed)
        keyword_layout.addRow("Ключевые слова", self.keywords_edit)

        self.excluded_keywords_edit = QPlainTextEdit(keyword_group)
        self.excluded_keywords_edit.setPlaceholderText(
            "Непрофильные фразы, которые нужно исключить"
        )
        self.excluded_keywords_edit.setFixedHeight(82)
        self.excluded_keywords_edit.textChanged.connect(self._emit_changed)
        keyword_layout.addRow(
            "Исключаемые слова",
            self.excluded_keywords_edit,
        )
        root.addWidget(keyword_group)

        direction_group = QGroupBox(
            "Направления ООО «Кортерис»",
            content,
        )
        direction_layout = QGridLayout(direction_group)
        direction_layout.setColumnStretch(0, 1)
        direction_layout.setColumnStretch(1, 1)

        self.direction_checkboxes: dict[TenderDirection, QCheckBox] = {}
        for index, (direction, label) in enumerate(DIRECTION_LABELS):
            checkbox = QCheckBox(label, direction_group)
            checkbox.toggled.connect(self._emit_changed)
            self.direction_checkboxes[direction] = checkbox
            direction_layout.addWidget(
                checkbox,
                index // 2,
                index % 2,
            )

        self.require_all_directions_check = QCheckBox(
            "Требовать совпадение по всем выбранным направлениям",
            direction_group,
        )
        self.require_all_directions_check.toggled.connect(self._emit_changed)
        direction_layout.addWidget(
            self.require_all_directions_check,
            4,
            0,
            1,
            2,
        )
        root.addWidget(direction_group)

        geography_group = QGroupBox(
            "Регион, закон и период",
            content,
        )
        geography_layout = QFormLayout(geography_group)
        geography_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.regions_edit = QPlainTextEdit(geography_group)
        self.regions_edit.setPlaceholderText("Москва\nМосковская область\nСанкт-Петербург")
        self.regions_edit.setFixedHeight(82)
        self.regions_edit.textChanged.connect(self._emit_changed)
        geography_layout.addRow("Регионы", self.regions_edit)

        laws_widget = QWidget(geography_group)
        laws_layout = QHBoxLayout(laws_widget)
        laws_layout.setContentsMargins(0, 0, 0, 0)
        laws_layout.setSpacing(14)

        self.law_checkboxes: dict[str, QCheckBox] = {}
        for law in ("44-ФЗ", "223-ФЗ"):
            checkbox = QCheckBox(law, laws_widget)
            checkbox.toggled.connect(self._emit_changed)
            self.law_checkboxes[law] = checkbox
            laws_layout.addWidget(checkbox)

        self.additional_laws_edit = QLineEdit(laws_widget)
        self.additional_laws_edit.setPlaceholderText("Другие законы через запятую")
        self.additional_laws_edit.textChanged.connect(self._emit_changed)
        laws_layout.addWidget(self.additional_laws_edit, 1)
        geography_layout.addRow("Законы", laws_widget)

        self.lookback_days_spin = QSpinBox(geography_group)
        self.lookback_days_spin.setRange(-1, 3650)
        self.lookback_days_spin.setSpecialValueText("Без ограничения")
        self.lookback_days_spin.setSuffix(" дн.")
        self.lookback_days_spin.valueChanged.connect(self._emit_changed)
        geography_layout.addRow(
            "Искать за период",
            self.lookback_days_spin,
        )

        self.only_open_check = QCheckBox(
            "Показывать только тендеры с открытым приёмом заявок",
            geography_group,
        )
        self.only_open_check.toggled.connect(self._emit_changed)
        geography_layout.addRow("", self.only_open_check)
        root.addWidget(geography_group)

        finance_group = QGroupBox(
            "Цена и релевантность",
            content,
        )
        finance_layout = QFormLayout(finance_group)
        finance_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.min_price_spin = self._create_price_spin(finance_group)
        self.max_price_spin = self._create_price_spin(finance_group)
        self.min_price_spin.valueChanged.connect(self._emit_changed)
        self.max_price_spin.valueChanged.connect(self._emit_changed)
        finance_layout.addRow(
            "Минимальная цена",
            self.min_price_spin,
        )
        finance_layout.addRow(
            "Максимальная цена",
            self.max_price_spin,
        )

        score_widget = QWidget(finance_group)
        score_layout = QHBoxLayout(score_widget)
        score_layout.setContentsMargins(0, 0, 0, 0)
        score_layout.setSpacing(10)

        self.minimum_score_slider = QSlider(
            Qt.Orientation.Horizontal,
            score_widget,
        )
        self.minimum_score_slider.setRange(0, 100)

        self.minimum_score_spin = QSpinBox(score_widget)
        self.minimum_score_spin.setRange(0, 100)
        self.minimum_score_spin.setSuffix(" балл.")

        self.minimum_score_slider.valueChanged.connect(self.minimum_score_spin.setValue)
        self.minimum_score_spin.valueChanged.connect(self.minimum_score_slider.setValue)
        self.minimum_score_spin.valueChanged.connect(self._emit_changed)

        score_layout.addWidget(self.minimum_score_slider, 1)
        score_layout.addWidget(self.minimum_score_spin)
        finance_layout.addRow(
            "Минимальная релевантность",
            score_widget,
        )
        root.addWidget(finance_group)

        source_group = QGroupBox(
            "Площадки и объём выдачи",
            content,
        )
        source_layout = QFormLayout(source_group)
        source_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.provider_ids_edit = QLineEdit(source_group)
        self.provider_ids_edit.setPlaceholderText("eis, rts_tender, roseltorg")
        self.provider_ids_edit.textChanged.connect(self._emit_changed)
        source_layout.addRow(
            "ID провайдеров",
            self.provider_ids_edit,
        )

        self.page_size_spin = QSpinBox(source_group)
        self.page_size_spin.setRange(1, 500)
        self.page_size_spin.valueChanged.connect(self._emit_changed)
        source_layout.addRow(
            "Результатов на страницу",
            self.page_size_spin,
        )

        self.include_disabled_check = QCheckBox(
            "Разрешить запуск отключённых провайдеров",
            source_group,
        )
        self.include_disabled_check.toggled.connect(self._emit_changed)
        source_layout.addRow("", self.include_disabled_check)

        self.enabled_check = QCheckBox(
            "Профиль включён и доступен для запуска",
            source_group,
        )
        self.enabled_check.toggled.connect(self._emit_changed)
        source_layout.addRow("", self.enabled_check)
        root.addWidget(source_group)

        self.validation_label = QLabel("", content)
        self.validation_label.setObjectName("ProfileValidationLabel")
        self.validation_label.setWordWrap(True)
        root.addWidget(self.validation_label)

        root.addStretch(1)

        self.setEnabled(False)
        self.apply_theme(self._theme)

    def _emit_changed(self, *args: object) -> None:
        del args
        self.profile_changed.emit()

    @staticmethod
    def _create_price_spin(parent: QWidget) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(parent)
        spin.setRange(-1.0, 999_999_999_999.0)
        spin.setDecimals(2)
        spin.setSingleStep(10_000.0)
        spin.setSpecialValueText("Без ограничения")
        spin.setSuffix(" ₽")
        spin.setGroupSeparatorShown(True)
        return spin

    @property
    def profile(self) -> TenderSearchProfile | None:
        return self._profile

    def load_profile(
        self,
        profile: TenderSearchProfile,
        *,
        allow_id_edit: bool = False,
    ) -> None:
        """Populate the editor from an existing profile."""

        self._profile = profile
        self._allow_id_edit = bool(allow_id_edit)
        self.setEnabled(True)

        self.profile_id_edit.setText(profile.id)
        self.profile_id_edit.setEnabled(self._allow_id_edit)
        self.name_edit.setText(profile.name)
        self.description_edit.setPlainText(profile.description)
        self.keywords_edit.setPlainText("\n".join(profile.keywords))
        self.excluded_keywords_edit.setPlainText("\n".join(profile.excluded_keywords))
        self.regions_edit.setPlainText("\n".join(profile.regions))

        selected_directions = set(profile.directions)
        for direction, checkbox in self.direction_checkboxes.items():
            checkbox.setChecked(direction in selected_directions)

        self.require_all_directions_check.setChecked(profile.require_all_directions)

        selected_laws = set(profile.laws)
        for law, checkbox in self.law_checkboxes.items():
            checkbox.setChecked(law in selected_laws)
        additional_laws = [law for law in profile.laws if law not in self.law_checkboxes]
        self.additional_laws_edit.setText(", ".join(additional_laws))

        self._set_optional_price(
            self.min_price_spin,
            profile.min_price,
        )
        self._set_optional_price(
            self.max_price_spin,
            profile.max_price,
        )

        self.minimum_score_spin.setValue(profile.minimum_score)
        self.only_open_check.setChecked(profile.only_open)
        self.lookback_days_spin.setValue(
            -1 if profile.lookback_days is None else profile.lookback_days
        )
        self.page_size_spin.setValue(profile.page_size)
        self.provider_ids_edit.setText(", ".join(profile.provider_ids))
        self.include_disabled_check.setChecked(profile.include_disabled_providers)
        self.enabled_check.setChecked(profile.enabled)

        kind = "Встроенный профиль" if profile.is_builtin else "Пользовательский профиль"
        if allow_id_edit:
            kind += " · новый, ещё не сохранён"
        self.kind_label.setText(kind)
        self.clear_validation_message()

    def clear_editor(self) -> None:
        self._profile = None
        self.setEnabled(False)
        self.kind_label.clear()
        self.clear_validation_message()

    def build_profile(self) -> TenderSearchProfile:
        """Validate the form and return an immutable profile model."""

        if self._profile is None:
            raise ValueError("Профиль не выбран")

        keywords = _split_values(self.keywords_edit.toPlainText())
        excluded_keywords = _split_values(self.excluded_keywords_edit.toPlainText())
        directions = tuple(
            direction
            for direction, checkbox in (self.direction_checkboxes.items())
            if checkbox.isChecked()
        )

        laws: list[str] = [
            law for law, checkbox in self.law_checkboxes.items() if checkbox.isChecked()
        ]
        laws.extend(_split_values(self.additional_laws_edit.text()))

        profile = TenderSearchProfile(
            id=self.profile_id_edit.text().strip().casefold(),
            name=self.name_edit.text().strip(),
            description=(self.description_edit.toPlainText().strip()),
            keywords=keywords,
            excluded_keywords=excluded_keywords,
            directions=directions,
            require_all_directions=(self.require_all_directions_check.isChecked()),
            regions=_split_values(self.regions_edit.toPlainText()),
            laws=_ordered_unique(laws),
            min_price=self._optional_price(self.min_price_spin),
            max_price=self._optional_price(self.max_price_spin),
            price_currency=self._profile.price_currency,
            minimum_score=self.minimum_score_spin.value(),
            only_open=self.only_open_check.isChecked(),
            lookback_days=(
                None if self.lookback_days_spin.value() < 0 else self.lookback_days_spin.value()
            ),
            page_size=self.page_size_spin.value(),
            provider_ids=_split_values(self.provider_ids_edit.text()),
            include_disabled_providers=(self.include_disabled_check.isChecked()),
            enabled=self.enabled_check.isChecked(),
            is_builtin=self._profile.is_builtin,
            created_at=self._profile.created_at,
            updated_at=self._profile.updated_at,
        )
        self.clear_validation_message()
        return profile

    def show_validation_error(self, message: str) -> None:
        self.validation_label.setText(message)
        palette = get_palette(self._theme)
        self.validation_label.setStyleSheet(f"color: {palette.danger};")

    def show_validation_success(self, message: str) -> None:
        self.validation_label.setText(message)
        palette = get_palette(self._theme)
        self.validation_label.setStyleSheet(f"color: {palette.success};")

    def clear_validation_message(self) -> None:
        self.validation_label.clear()

    @staticmethod
    def _set_optional_price(
        spin: QDoubleSpinBox,
        value: float | None,
    ) -> None:
        spin.setValue(-1.0 if value is None else float(value))

    @staticmethod
    def _optional_price(
        spin: QDoubleSpinBox,
    ) -> float | None:
        value = spin.value()
        return None if value < 0 else float(value)

    def apply_theme(
        self,
        theme: ThemeName | str,
    ) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)

        self.setStyleSheet(
            f"""
            QWidget#SearchProfileEditorContent {{
                background-color: {palette.panel_background};
                color: {palette.text_primary};
            }}
            QLabel#ProfileEditorTitle {{
                color: {palette.text_primary};
                font-size: 20px;
                font-weight: 700;
            }}
            QLabel#ProfileKindLabel {{
                color: {palette.brand_accent};
                font-size: 12px;
                font-weight: 600;
            }}
            QLabel {{
                color: {palette.text_secondary};
            }}
            QGroupBox {{
                color: {palette.text_primary};
                background-color: {palette.card_background};
                border: 1px solid {palette.border_default};
                border-radius: 9px;
                margin-top: 12px;
                padding: 12px;
                font-weight: 600;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
                color: {palette.text_primary};
            }}
            QLineEdit,
            QPlainTextEdit,
            QSpinBox,
            QDoubleSpinBox {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_default};
                border-radius: 6px;
                padding: 6px 8px;
                selection-background-color:
                    {palette.selected_background};
            }}
            QLineEdit:focus,
            QPlainTextEdit:focus,
            QSpinBox:focus,
            QDoubleSpinBox:focus {{
                border-color: {palette.focus_ring};
            }}
            QLineEdit:disabled {{
                color: {palette.text_muted};
                background-color: {palette.elevated_background};
            }}
            QCheckBox {{
                color: {palette.text_secondary};
                spacing: 7px;
            }}
            QSlider::groove:horizontal {{
                height: 5px;
                background: {palette.border_default};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 15px;
                margin: -5px 0;
                background: {palette.brand_primary};
                border-radius: 7px;
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            """
        )


def _split_values(value: str) -> tuple[str, ...]:
    prepared = value.replace(";", "\n").replace(",", "\n")
    return _ordered_unique(prepared.splitlines())


def _ordered_unique(
    values: Iterable[str],
) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized = str(value).strip()
        if not normalized:
            continue
        identity = normalized.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        result.append(normalized)

    return tuple(result)


__all__ = [
    "DIRECTION_LABELS",
    "TenderSearchProfileEditor",
]
