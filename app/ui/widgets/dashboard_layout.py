from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QStackedWidget, QVBoxLayout, QWidget

from app.ui.navigation import (
    DEFAULT_ROUTE_REGISTRY,
    NavigationCause,
    NavigationHistory,
    NavigationSnapshot,
    NavigationStatus,
    RouteAvailability,
    RouteContext,
    RouteId,
    RouteKind,
    RouteRegistry,
    RouteRequest,
    RouteResult,
    RouteSpec,
)

from app.ui.widgets.sidebar import _primary_sidebar_key, create_default_sidebar
from app.ui.widgets.topbar import TopBar


RouteHandler = Callable[[RouteContext], bool]
RouteContextProvider = Callable[[], RouteContext]


class DashboardLayout(QWidget):
    """Main workspace layout combining Sidebar, TopBar and content area."""

    navigation_completed = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        registry: RouteRegistry = DEFAULT_ROUTE_REGISTRY,
    ) -> None:
        super().__init__(parent)

        self.route_registry = registry
        self.navigation_history = NavigationHistory()
        self.current_snapshot: NavigationSnapshot | None = None
        self.last_navigation_result = RouteResult(
            status=NavigationStatus.UNKNOWN_ROUTE,
            reason_code="navigation_not_started",
            message="Навигация ещё не выполнялась.",
        )
        self._destination_index: dict[str, int] = {}
        self._route_handlers: dict[RouteId, RouteHandler] = {}
        self._context_providers: dict[str, RouteContextProvider] = {}

        self.sidebar = create_default_sidebar(registry)
        self.topbar = TopBar()
        self.pages = QStackedWidget()

        shell = QHBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        shell.addWidget(self.sidebar)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        right.addWidget(self.topbar)
        right.addWidget(self.pages, 1)

        shell.addLayout(right, 1)

        # Public compatibility view retained for RM-127 consumers. Titles are
        # derived from RouteSpec and activation uses _destination_index only.
        self._page_index: dict[str, tuple[int, str]] = {}

        self.sidebar.item_selected.connect(self._activate)

    def add_page(self, key: str, title: str, widget: QWidget) -> None:
        """Bind a physical page through a legacy key without creating a route map."""
        spec = self.route_registry.resolve(key)
        destination = spec.destination if spec is not None else key
        if destination is None:
            raise ValueError("A planned route cannot own a physical page")
        if destination in self._destination_index:
            raise ValueError(f"Physical destination is already bound: {destination}")
        index = self.pages.addWidget(widget)
        self._destination_index[destination] = index
        resolved_title = spec.title if spec is not None else str(title)
        self._page_index[key] = (index, resolved_title)
        if (
            spec is not None
            and spec.route_id is RouteId.DASHBOARD
            and self.current_snapshot is None
        ):
            self.navigate(
                RouteRequest(
                    RouteId.DASHBOARD,
                    cause=NavigationCause.PROGRAMMATIC,
                    record_history=False,
                )
            )

    def register_route_handler(
        self,
        route_id: RouteId,
        handler: RouteHandler,
    ) -> None:
        """Bind an existing embedded/modal owner without storing it in metadata."""
        if not callable(handler):
            raise TypeError("Route handler must be callable")
        if self.route_registry.resolve(route_id) is None:
            raise ValueError("Cannot bind an unknown route")
        self._route_handlers[route_id] = handler

    def register_context_provider(
        self,
        destination: str,
        provider: RouteContextProvider,
    ) -> None:
        """Register a page-owned presentation-state snapshot provider."""
        normalized = str(destination).strip()
        if not normalized or not callable(provider):
            raise ValueError("A context provider needs a destination and callable")
        self._context_providers[normalized] = provider

    def add_placeholder_page(self, key: str, title: str) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(title)
        label.setStyleSheet("font-size:24px;font-weight:600;")
        layout.addStretch()
        layout.addWidget(label)
        layout.addStretch()
        self.add_page(key, title, page)

    def initialize_defaults(self) -> None:
        """Compatibility demo helper driven only by canonical primary specs."""
        for spec in self.route_registry.primary_routes:
            key = _primary_sidebar_key(spec)
            self.add_placeholder_page(key, spec.title)
        self.navigate(RouteRequest(RouteId.DASHBOARD, record_history=False))

    def navigate(self, request: RouteRequest) -> RouteResult:
        """Resolve and activate one route with a typed, observable result."""
        if not isinstance(request, RouteRequest):
            raise TypeError("navigate() requires RouteRequest")
        spec = self.route_registry.resolve(request.target)
        if spec is None:
            return self._publish(
                RouteResult(
                    status=NavigationStatus.UNKNOWN_ROUTE,
                    reason_code="unknown_route",
                    message="Маршрут недоступен.",
                    snapshot=self.current_snapshot,
                )
            )

        context = self._context_for_spec(spec, request.context)
        context_error = self.route_registry.validate_context(spec, context)
        if context_error is not None:
            return self._publish(
                RouteResult(
                    status=NavigationStatus.INVALID_CONTEXT,
                    resolved_route=spec.route_id,
                    reason_code=context_error,
                    message="Для открытия раздела недостаточно безопасного контекста.",
                    snapshot=self.current_snapshot,
                    recovery_route=spec.parent,
                )
            )
        if spec.availability in {
            RouteAvailability.PLANNED,
            RouteAvailability.DISABLED,
        }:
            return self._publish(
                RouteResult(
                    status=NavigationStatus.UNAVAILABLE,
                    resolved_route=spec.route_id,
                    reason_code=spec.capability or spec.availability.value,
                    message="Раздел пока недоступен.",
                    snapshot=self.current_snapshot,
                    recovery_route=spec.parent,
                )
            )

        origin_snapshot: NavigationSnapshot | None = None
        if (
            request.record_history
            and spec.history_enabled
            and self.current_snapshot is not None
            and spec.kind is not RouteKind.MODAL
        ):
            origin_snapshot = self._capture_current_snapshot()

        handler = self._route_handlers.get(spec.route_id)
        handler_required = spec.kind in {RouteKind.EMBEDDED, RouteKind.MODAL}
        if handler_required and handler is None:
            return self._destination_unavailable(spec)
        if handler is not None:
            try:
                accepted = bool(handler(context))
            except Exception:
                accepted = False
            if not accepted:
                return self._destination_unavailable(spec)

        if spec.kind is RouteKind.MODAL:
            return self._publish(
                RouteResult(
                    status=NavigationStatus.NAVIGATED,
                    resolved_route=spec.route_id,
                    snapshot=self.current_snapshot,
                    history_changed=False,
                )
            )

        destination = spec.destination or ""
        index = self._destination_index.get(destination)
        if index is None:
            return self._destination_unavailable(spec)

        target_snapshot = NavigationSnapshot(
            spec.route_id,
            context,
            context.focus_token,
        )
        if self.current_snapshot == target_snapshot and self.pages.currentIndex() == index:
            return self._publish(
                RouteResult(
                    status=NavigationStatus.NO_CHANGE,
                    resolved_route=spec.route_id,
                    snapshot=self.current_snapshot,
                )
            )

        history_changed = False
        if origin_snapshot is not None:
            origin = replace(
                origin_snapshot,
                focus_token=request.focus_token or origin_snapshot.focus_token,
            )
            history_changed = self.navigation_history.push(origin)

        self.pages.setCurrentIndex(index)
        self.current_snapshot = target_snapshot
        self.topbar.set_page_title(spec.title)
        self.sidebar.set_current(_primary_sidebar_key(self._primary_ancestor(spec)))
        return self._publish(
            RouteResult(
                status=NavigationStatus.NAVIGATED,
                resolved_route=spec.route_id,
                snapshot=target_snapshot,
                history_changed=history_changed,
            )
        )

    def back(self) -> RouteResult:
        """Restore the newest valid in-memory snapshot without recording a loop."""
        while (snapshot := self.navigation_history.pop()) is not None:
            result = self.navigate(
                RouteRequest(
                    snapshot.route_id,
                    cause=NavigationCause.BACK,
                    context=snapshot.context,
                    record_history=False,
                )
            )
            if result.succeeded:
                self.current_snapshot = snapshot
                self._restore_focus(snapshot.focus_token)
                return self._publish(replace(result, snapshot=snapshot, history_changed=False))
        return self._publish(
            RouteResult(
                status=NavigationStatus.NO_CHANGE,
                resolved_route=(self.current_snapshot.route_id if self.current_snapshot else None),
                reason_code="history_empty",
                message="Предыдущий раздел отсутствует.",
                snapshot=self.current_snapshot,
            )
        )

    def return_to_origin(self) -> RouteResult:
        return self.back()

    def _destination_unavailable(self, spec: RouteSpec) -> RouteResult:
        return self._publish(
            RouteResult(
                status=NavigationStatus.UNAVAILABLE,
                resolved_route=spec.route_id,
                reason_code="destination_unavailable",
                message="Раздел временно недоступен.",
                snapshot=self.current_snapshot,
                recovery_route=spec.parent,
            )
        )

    def _publish(self, result: RouteResult) -> RouteResult:
        self.last_navigation_result = result
        self.navigation_completed.emit(result)
        return result

    def _primary_ancestor(self, spec: RouteSpec) -> RouteSpec:
        current = spec
        while current.parent is not None:
            current = self.route_registry.get(current.parent)
        return current

    @staticmethod
    def _context_for_spec(spec: RouteSpec, context: RouteContext) -> RouteContext:
        updates: dict[str, str] = {}
        if context.workflow_kind is None:
            workflow_kind = {
                RouteId.WORKFLOW_PROPOSALS: "proposal",
                RouteId.WORKFLOW_ESTIMATES: "estimate",
                RouteId.WORKFLOW_PROJECTS: "project",
            }.get(spec.route_id)
            if workflow_kind is not None:
                updates["workflow_kind"] = workflow_kind
        if spec.route_id is RouteId.TENDER_AI:
            updates.setdefault("tender_section", "settings")
            updates.setdefault("settings_section", "ai")
        elif spec.route_id is RouteId.TENDER_SETTINGS:
            updates.setdefault("tender_section", "settings")
        return replace(context, **updates) if updates else context

    def _restore_focus(self, token: str | None) -> None:
        if not token:
            current = self.pages.currentWidget()
            if current is not None:
                current.setFocus()
            return
        target = self.findChild(QWidget, token)
        if target is not None:
            target.setFocus()
            return
        current = self.pages.currentWidget()
        if current is not None:
            current.setFocus()

    def _capture_current_snapshot(self) -> NavigationSnapshot:
        current = self.current_snapshot
        if current is None:
            raise RuntimeError("Navigation snapshot is unavailable")
        spec = self.route_registry.get(current.route_id)
        provider = self._context_providers.get(spec.destination or "")
        if provider is None:
            return current
        try:
            context = provider()
        except Exception:
            return current
        if not isinstance(context, RouteContext):
            return current
        if self.route_registry.validate_context(spec, context) is not None:
            return current
        captured = replace(current, context=context)
        self.current_snapshot = captured
        return captured

    def _activate(self, key: str) -> None:
        self.navigate(
            RouteRequest(
                key,
                cause=NavigationCause.SIDEBAR,
            )
        )


__all__ = ["DashboardLayout"]
