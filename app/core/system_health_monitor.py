"""Non-blocking background monitor for system health snapshots."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    QObject,
    QRunnable,
    QThreadPool,
    Signal,
    Slot,
)

from app.core.system_health import SystemHealthSnapshot


class _SystemHealthWorkerSignals(QObject):
    snapshot_ready = Signal(object)
    failed = Signal(str)
    finished = Signal()


class _SystemHealthWorker(QRunnable):
    def __init__(
        self,
        collector: Callable[[], SystemHealthSnapshot],
    ) -> None:
        super().__init__()
        self.collector = collector
        self.signals = _SystemHealthWorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            snapshot = self.collector()
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        else:
            self.signals.snapshot_ready.emit(snapshot)
        finally:
            self.signals.finished.emit()


class SystemHealthMonitor(QObject):
    """Run health checks in QThreadPool and suppress duplicate refreshes."""

    snapshot_ready = Signal(object)
    check_failed = Signal(str)
    busy_changed = Signal(bool)

    def __init__(
        self,
        collector: Callable[[], SystemHealthSnapshot],
        *,
        thread_pool: QThreadPool | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.collector = collector
        self.thread_pool = thread_pool or QThreadPool.globalInstance()
        self._running = False
        self._last_snapshot: SystemHealthSnapshot | None = None
        self._worker: _SystemHealthWorker | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def last_snapshot(self) -> SystemHealthSnapshot | None:
        return self._last_snapshot

    def request_refresh(self) -> bool:
        """Start a check and return False when one is already running."""
        if self._running:
            return False

        self._running = True
        self.busy_changed.emit(True)

        worker = _SystemHealthWorker(self.collector)
        self._worker = worker
        worker.signals.snapshot_ready.connect(self._handle_snapshot)
        worker.signals.failed.connect(self._handle_failure)
        worker.signals.finished.connect(self._handle_finished)
        self.thread_pool.start(worker)
        return True

    @Slot(object)
    def _handle_snapshot(
        self,
        snapshot: SystemHealthSnapshot,
    ) -> None:
        self._last_snapshot = snapshot
        self.snapshot_ready.emit(snapshot)

    @Slot(str)
    def _handle_failure(self, message: str) -> None:
        self.check_failed.emit(message)

    @Slot()
    def _handle_finished(self) -> None:
        self._running = False
        self._worker = None
        self.busy_changed.emit(False)


__all__ = ["SystemHealthMonitor"]
