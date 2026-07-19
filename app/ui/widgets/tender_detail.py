"""Reusable native Qt views for RM-149 tender detail/card projections."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QStackedWidget, QVBoxLayout, QWidget

from app.tenders.detail import (
    TenderActionRole,
    TenderActionState,
    TenderCardProjection,
    TenderDetailSnapshot,
    TenderIdentity,
)
from app.ui.theme.colors import ThemeName
from app.ui.widgets.button import PrimaryButton, SecondaryButton
from app.ui.widgets.card import Card, CardTone


def _label(parent: QWidget, object_name: str) -> QLabel:
    result = QLabel(parent)
    result.setObjectName(object_name)
    result.setWordWrap(True)
    result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return result


class _Section(QFrame):
    def __init__(
        self,
        object_name: str,
        title: str,
        *,
        tone: CardTone = CardTone.DEFAULT,
        theme: ThemeName = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.card = Card(title, tone=tone, theme=theme, shadow=False, parent=self)
        layout.addWidget(self.card)

    def set_theme(self, theme: ThemeName | str) -> None:
        self.card.set_theme(theme)


class TenderDetailPanel(QWidget):
    """Render one immutable snapshot without further reads or computation."""

    action_requested = Signal(str)

    def __init__(
        self,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("TenderDetailPanel")
        self._theme = ThemeName(theme)
        self._snapshot: TenderDetailSnapshot | None = None
        self._plain_text = "No tender selected"
        self._primary_action_id = ""
        self._secondary_buttons: dict[str, SecondaryButton] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.critical_section = _Section(
            "TenderDetailCriticalSection",
            "Critical warning",
            tone=CardTone.DANGER,
            theme=self._theme,
            parent=self,
        )
        self.critical_label = _label(self.critical_section.card, "TenderDetailCriticalText")
        self.critical_section.card.add_widget(self.critical_label)
        self.critical_section.setVisible(False)
        root.addWidget(self.critical_section)

        self.identity_section, self.identity_label = self._add_section(
            root, "TenderDetailIdentitySection", "Tender identity"
        )
        self.decision_section, self.decision_label = self._add_section(
            root, "TenderDetailDecisionSection", "Participation decision"
        )
        self.primary_button = PrimaryButton(
            "Open tender details",
            theme=self._theme,
            parent=self.decision_section.card,
        )
        self.primary_button.setObjectName("TenderDetailPrimaryAction")
        self.primary_button.clicked.connect(self._emit_primary_action)
        self.decision_section.card.add_footer_widget(self.primary_button)
        self.status_section, self.status_label = self._add_section(
            root, "TenderDetailStatusSection", "Status and trust"
        )
        self.facts_section, self.facts_label = self._add_section(
            root, "TenderDetailFactsSection", "Tender facts"
        )
        self.evidence_section, self.evidence_label = self._add_section(
            root, "TenderDetailEvidenceSection", "Decision evidence"
        )
        self.provenance_section, self.provenance_label = self._add_section(
            root, "TenderDetailProvenanceSection", "Provenance and history"
        )
        self.actions_section = _Section(
            "TenderDetailActionsSection",
            "Other actions",
            theme=self._theme,
            parent=self,
        )
        self.actions_container = QWidget(self.actions_section.card)
        self.actions_container.setObjectName("TenderDetailSecondaryActions")
        self.actions_layout = QVBoxLayout(self.actions_container)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(6)
        self.actions_section.card.add_widget(self.actions_container)
        root.addWidget(self.actions_section)
        root.addStretch(1)

        self.setAccessibleName("Tender details")
        self.setAccessibleDescription(self._plain_text)

    def _add_section(
        self,
        layout: QVBoxLayout,
        object_name: str,
        title: str,
    ) -> tuple[_Section, QLabel]:
        section = _Section(object_name, title, theme=self._theme, parent=self)
        label = _label(section.card, object_name + "Text")
        section.card.add_widget(label)
        layout.addWidget(section)
        return section, label

    @property
    def snapshot(self) -> TenderDetailSnapshot | None:
        return self._snapshot

    def clear(self, message: str = "No tender selected") -> None:
        self._snapshot = None
        self._primary_action_id = ""
        self._plain_text = message
        self.critical_section.setVisible(False)
        self.identity_label.setText(message)
        for label in (
            self.decision_label,
            self.status_label,
            self.facts_label,
            self.evidence_label,
            self.provenance_label,
        ):
            label.clear()
        self.primary_button.setEnabled(False)
        for button in self._secondary_buttons.values():
            button.setVisible(False)
        self.setAccessibleDescription(message)

    def set_snapshot(self, snapshot: TenderDetailSnapshot) -> None:
        if not isinstance(snapshot, TenderDetailSnapshot):
            raise TypeError("snapshot must be TenderDetailSnapshot")
        self._snapshot = snapshot
        self._plain_text = self._render_plain_text(snapshot)
        self.setAccessibleName(f"Tender details: {snapshot.title}")
        self.setAccessibleDescription(snapshot.accessible_summary)

        critical_text = "\n".join(
            f"Warning: {item.title}. {item.detail}" for item in snapshot.critical_warnings
        )
        self.critical_label.setText(critical_text)
        self.critical_label.setAccessibleName("Critical tender warning")
        self.critical_label.setAccessibleDescription(critical_text)
        self.critical_section.setVisible(bool(snapshot.critical_warnings))

        facts = {item.stable_id: item for item in snapshot.facts}
        number = facts.get("procurement_number")
        self.identity_label.setText(
            "\n".join(
                (
                    snapshot.title,
                    f"Identity: {snapshot.identity.public_id}",
                    f"Procurement number: {number.value if number else 'not loaded'}",
                    f"Source: {snapshot.source}",
                )
            )
        )
        if snapshot.decision is None:
            self.decision_label.setText("Decision: not loaded")
        else:
            score = (
                "not loaded" if snapshot.decision.score is None else str(snapshot.decision.score)
            )
            self.decision_label.setText(
                "\n".join(
                    (
                        f"Recommendation: {snapshot.decision.recommendation}",
                        f"Score: {score}",
                        snapshot.decision.summary,
                        f"Policy: {snapshot.decision.policy_version or 'not loaded'}",
                    )
                )
            )
        self.status_label.setText(
            "\n".join(
                f"{item.label}: {item.value}. {item.explanation}" for item in snapshot.statuses
            )
        )
        self.facts_label.setText(
            "\n".join(f"{item.label}: {item.value}" for item in snapshot.facts)
        )
        evidence = snapshot.decision.evidence if snapshot.decision else ()
        self.evidence_label.setText(
            "\n".join(evidence) if evidence else "Decision evidence: not loaded"
        )
        history = "\n".join(
            f"{item.occurred_at}: {item.title}; {item.detail}" for item in snapshot.history
        )
        self.provenance_label.setText(
            "\n".join(
                part
                for part in (
                    f"Source revision: {snapshot.source_revision}",
                    f"Snapshot fingerprint: {snapshot.fingerprint}",
                    history,
                )
                if part
            )
        )
        self._publish_actions(snapshot)

    def _publish_actions(self, snapshot: TenderDetailSnapshot) -> None:
        primary = snapshot.primary_action
        self._primary_action_id = primary.action_id
        self.primary_button.setText(primary.label)
        self.primary_button.setEnabled(primary.state is TenderActionState.AVAILABLE)
        self.primary_button.setAccessibleName(primary.label)
        self.primary_button.setAccessibleDescription(primary.accessible_description)

        active_ids = set()
        for action in snapshot.actions:
            if action.role is TenderActionRole.PRIMARY:
                continue
            active_ids.add(action.action_id)
            button = self._secondary_buttons.get(action.action_id)
            if button is None:
                button = SecondaryButton(
                    action.label, theme=self._theme, parent=self.actions_container
                )
                button.setObjectName(f"TenderDetailAction_{action.action_id}")
                button.clicked.connect(
                    lambda _checked=False, action_id=action.action_id: self.action_requested.emit(
                        action_id
                    )
                )
                self.actions_layout.addWidget(button)
                self._secondary_buttons[action.action_id] = button
            button.setText(action.label)
            button.setEnabled(action.state is TenderActionState.AVAILABLE)
            button.setAccessibleName(action.label)
            button.setAccessibleDescription(action.accessible_description)
            button.setVisible(True)
        for action_id, button in self._secondary_buttons.items():
            if action_id not in active_ids:
                button.setVisible(False)

    def _emit_primary_action(self) -> None:
        if self._primary_action_id:
            self.action_requested.emit(self._primary_action_id)

    def toPlainText(self) -> str:  # noqa: N802 - QTextBrowser compatibility seam
        return self._plain_text

    @staticmethod
    def _render_plain_text(snapshot: TenderDetailSnapshot) -> str:
        sections = [snapshot.accessible_summary]
        sections.extend(
            f"{item.label}: {item.value}. {item.explanation}" for item in snapshot.statuses
        )
        sections.extend(f"{item.label}: {item.value}" for item in snapshot.facts)
        sections.extend(
            f"Warning: {item.title}. {item.detail}" for item in snapshot.critical_warnings
        )
        sections.extend(item.detail for item in snapshot.history)
        return "\n".join(sections)

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        for section in (
            self.critical_section,
            self.identity_section,
            self.decision_section,
            self.status_section,
            self.facts_section,
            self.evidence_section,
            self.provenance_section,
            self.actions_section,
        ):
            section.set_theme(self._theme)
        self.primary_button.set_theme(self._theme)
        for button in self._secondary_buttons.values():
            button.set_theme(self._theme)


class TenderCard(Card):
    """Compact card that consumes only a repository-free card projection."""

    action_requested = Signal(str)

    def __init__(
        self,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            "Tender",
            subtitle="No tender selected",
            theme=theme,
            shadow=False,
            parent=parent,
        )
        self.setObjectName("TenderCard")
        self.identity: TenderIdentity | None = None
        self.snapshot_fingerprint = ""
        self._projection: TenderCardProjection | None = None
        self._plain_text = "No tender selected"
        self.summary_label = _label(self, "TenderCardSummary")
        self.add_widget(self.summary_label)
        self.primary_button = PrimaryButton("Open details", theme=theme, parent=self)
        self.primary_button.setObjectName("TenderCardPrimaryAction")
        self.primary_button.clicked.connect(self._emit_action)
        self.add_footer_widget(self.primary_button)

    def set_projection(self, projection: TenderCardProjection) -> None:
        if not isinstance(projection, TenderCardProjection):
            raise TypeError("projection must be TenderCardProjection")
        self._projection = projection
        self.identity = projection.identity
        self.snapshot_fingerprint = projection.snapshot_fingerprint
        self.title = projection.title
        self.subtitle = f"{projection.source} · {projection.identity.public_id}"
        warning = f"Warning: {projection.critical_warning}\n" if projection.critical_warning else ""
        self._plain_text = (
            f"{projection.title}\n{warning}Decision: {projection.decision}\n"
            f"Price: {projection.price}\nDeadline: {projection.deadline}\n"
            f"Verification: {projection.verification}; freshness: {projection.freshness}; "
            f"conflicts: {projection.conflicts}\n{projection.primary_action.label}"
        )
        self.summary_label.setText(self._plain_text)
        self.primary_button.setText(projection.primary_action.label)
        self.primary_button.setEnabled(
            projection.primary_action.state is TenderActionState.AVAILABLE
        )
        self.primary_button.setAccessibleDescription(
            projection.primary_action.accessible_description
        )
        self.setAccessibleName(f"Tender card: {projection.title}")
        self.setAccessibleDescription(projection.accessible_summary)

    def _emit_action(self) -> None:
        if self._projection is not None:
            self.action_requested.emit(self._projection.primary_action.action_id)

    def toPlainText(self) -> str:  # noqa: N802 - card/detail test seam
        return self._plain_text


class TenderDetailHost(QWidget):
    """Switch between canonical detail and an explicitly transient preview."""

    action_requested = Signal(str)

    def __init__(
        self,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("TenderDetailHost")
        self._theme = ThemeName(theme)
        self._preview_text = "No tender selected"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.context_label = _label(self, "TenderDetailEntryContext")
        self.context_label.setVisible(False)
        layout.addWidget(self.context_label)
        self.stack = QStackedWidget(self)
        self.detail = TenderDetailPanel(theme=self._theme, parent=self.stack)
        self.detail.action_requested.connect(self.action_requested.emit)
        self.preview = _label(self.stack, "TenderTransientPreview")
        self.preview.setText(self._preview_text)
        self.preview.setAccessibleName("Transient tender preview")
        self.stack.addWidget(self.detail)
        self.stack.addWidget(self.preview)
        self.stack.setCurrentWidget(self.preview)
        layout.addWidget(self.stack)

    @property
    def snapshot(self) -> TenderDetailSnapshot | None:
        return self.detail.snapshot if self.stack.currentWidget() is self.detail else None

    def set_snapshot(self, snapshot: TenderDetailSnapshot) -> None:
        self.detail.set_snapshot(snapshot)
        self.stack.setCurrentWidget(self.detail)
        self.setAccessibleDescription(snapshot.accessible_summary)

    def set_entry_context(self, text: str) -> None:
        self.context_label.setText(text)
        self.context_label.setVisible(bool(text))

    def set_transient_preview(self, text: str) -> None:
        self._preview_text = text
        self.preview.setText(text)
        self.preview.setAccessibleDescription(text)
        self.stack.setCurrentWidget(self.preview)
        self.setAccessibleDescription(text)

    def clear(self, message: str = "No tender selected") -> None:
        self.set_transient_preview(message)

    def toPlainText(self) -> str:  # noqa: N802 - QTextBrowser compatibility seam
        if self.stack.currentWidget() is self.detail:
            content = self.detail.toPlainText()
        else:
            content = self._preview_text
        context = self.context_label.text()
        return "\n".join(item for item in (context, content) if item)

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        self.detail.apply_theme(self._theme)


__all__ = ["TenderCard", "TenderDetailHost", "TenderDetailPanel"]
