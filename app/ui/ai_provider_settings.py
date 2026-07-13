"""Presentation-only controls for canonical AI provider selection."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

from app.core.ai.provider_selection import (
    AiProviderId,
    AiProviderResolution,
    AiProviderSelectionService,
    AiProviderSettings,
    OLLAMA_DEFAULT_BASE_URL,
    OPENAI_DEFAULT_BASE_URL,
)

AI_PROVIDER_OPTIONS: tuple[tuple[str, str], ...] = (
    (AiProviderId.DISABLED.value, "Отключено"),
    (AiProviderId.OPENAI.value, "OpenAI API"),
    (AiProviderId.OPENAI_COMPATIBLE.value, "OpenAI-совместимый сервер"),
    (AiProviderId.OLLAMA.value, "Ollama — локально"),
)
RESTART_NOTICE = "Новый AI-провайдер будет применён после перезапуска приложения"
OLLAMA_HINT = "Ollama должен быть запущен локально, а указанная модель — установлена заранее."


class AiProviderSettingsWidget(QWidget):
    """Render stable provider IDs and delegate all behavior to the service."""

    def __init__(
        self,
        service: AiProviderSelectionService | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.last_resolution: AiProviderResolution | None = None

        form = QFormLayout(self)
        self.provider_combo = QComboBox(self)
        for provider_id, label in AI_PROVIDER_OPTIONS:
            self.provider_combo.addItem(label, provider_id)
        self.credential_edit = QLineEdit(self)
        self.credential_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.credential_edit.setPlaceholderText("API-ключ")
        self.model_edit = QLineEdit(self)
        self.base_url_edit = QLineEdit(self)
        self.ollama_hint = QLabel(OLLAMA_HINT, self)
        self.ollama_hint.setWordWrap(True)
        self.save_button = QPushButton("Сохранить", self)

        form.addRow("Провайдер", self.provider_combo)
        form.addRow("API-ключ", self.credential_edit)
        form.addRow("Модель", self.model_edit)
        form.addRow("Base URL", self.base_url_edit)
        form.addRow(self.ollama_hint)
        form.addRow(self.save_button)

        self.provider_combo.currentIndexChanged.connect(self._sync_fields)
        self.save_button.clicked.connect(self.save)
        self.load()

    def selected_provider_id(self) -> AiProviderId:
        try:
            return AiProviderId(str(self.provider_combo.currentData()))
        except ValueError:
            return AiProviderId.DISABLED

    def load(self) -> None:
        settings = (
            self.service.load_settings()
            if self.service is not None
            else AiProviderSettings(AiProviderId.DISABLED)
        )
        index = self.provider_combo.findData(settings.provider_id.value)
        self.provider_combo.setCurrentIndex(max(index, 0))
        self.model_edit.setText(settings.model)
        self.base_url_edit.setText(settings.base_url)
        self.credential_edit.clear()
        self._sync_fields()
        self._sync_credential_placeholder(settings.provider_id)

    def save(self) -> AiProviderResolution | None:
        provider_id = self.selected_provider_id()
        if self.service is None:
            self.credential_edit.clear()
            QMessageBox.warning(
                self,
                "AI-провайдер",
                "Настройки AI-провайдера недоступны.",
            )
            return None

        settings = AiProviderSettings(
            provider_id=provider_id,
            model=self.model_edit.text().strip(),
            base_url=self.base_url_edit.text().strip(),
        )
        credential = self.credential_edit.text().strip() or None
        try:
            resolution = self.service.save_selection(settings, credential=credential)
        finally:
            self.credential_edit.clear()
        self.last_resolution = resolution
        self._sync_credential_placeholder(provider_id)

        if resolution.available and resolution.effective_provider_id is provider_id:
            QMessageBox.information(self, "AI-провайдер", RESTART_NOTICE)
        else:
            message = (
                resolution.warnings[0]
                if resolution.warnings
                else ("AI-провайдер остался отключён.")
            )
            QMessageBox.warning(self, "AI-провайдер", message)
        return resolution

    def _sync_fields(self) -> None:
        provider_id = self.selected_provider_id()
        enabled = provider_id is not AiProviderId.DISABLED
        compatible = provider_id is AiProviderId.OPENAI_COMPATIBLE
        ollama = provider_id is AiProviderId.OLLAMA
        self.model_edit.setEnabled(enabled)
        self.credential_edit.setEnabled(enabled and not ollama)
        self.base_url_edit.setEnabled(compatible or ollama)
        self.ollama_hint.setVisible(ollama)
        if provider_id is AiProviderId.OPENAI:
            self.base_url_edit.setText(OPENAI_DEFAULT_BASE_URL)
        elif ollama and self.base_url_edit.text().strip() in {"", OPENAI_DEFAULT_BASE_URL}:
            self.base_url_edit.setText(OLLAMA_DEFAULT_BASE_URL)
        self._sync_credential_placeholder(provider_id)

    def _sync_credential_placeholder(self, provider_id: AiProviderId) -> None:
        if provider_id is AiProviderId.OLLAMA:
            self.credential_edit.setPlaceholderText("Не требуется")
            return
        saved = (
            self.service is not None
            and provider_id is not AiProviderId.DISABLED
            and self.service.credential_available(provider_id)
        )
        self.credential_edit.setPlaceholderText("Сохранён" if saved else "API-ключ")


__all__ = [
    "AI_PROVIDER_OPTIONS",
    "AiProviderSettingsWidget",
    "OLLAMA_HINT",
    "RESTART_NOTICE",
]
