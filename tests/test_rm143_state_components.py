"""Expected shared status, data-state and form presentation primitives."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLineEdit

from app.ui.dashboard.data_state import DataState, DataStateKind, DataStatePanel
from app.ui.theme.colors import SemanticColor
from app.ui.widgets.feedback import InlineMessage, StatusBadge
from app.ui.widgets.form import FormField, FormSection


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_data_state_adds_disabled_unavailable_without_second_taxonomy() -> None:
    _app()
    state = DataState.disabled("Нет доступа")
    panel = DataStatePanel()
    panel.set_state(state)

    assert state.kind is DataStateKind.DISABLED
    assert state.blocking
    assert "Нет доступа" in panel.accessibleDescription()
    assert panel.title_label.text()


def test_status_primitives_expose_text_and_semantic_tone() -> None:
    _app()
    badge = StatusBadge("Готово", tone=SemanticColor.SUCCESS)
    message = InlineMessage(
        "Требуется проверка",
        details="Откройте документы.",
        tone=SemanticColor.WARNING,
    )

    assert badge.text() == "Готово"
    assert badge.accessibleName() == "Готово"
    assert message.title_label.text() == "Требуется проверка"
    assert "Откройте документы" in message.accessibleDescription()


def test_form_field_and_section_own_presentation_not_validation() -> None:
    _app()
    edit = QLineEdit()
    field = FormField("Название", edit, help_text="До 120 символов", required=True)
    section = FormSection("Параметры")
    section.add_field(field)
    field.set_error("Поле обязательно")

    assert field.control is edit
    assert field.label.text().startswith("Название")
    assert field.error_label.text() == "Поле обязательно"
    assert section.fields == (field,)
