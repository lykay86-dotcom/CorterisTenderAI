"""Non-blocking background monitor for system health snapshots."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from threading import Event, Lock
from time import monotonic

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from app.core.system_health import SystemHealthSnapshot


class SystemHealthLifecycleState(StrEnum):
    """Terminal lifecycle for one monitor-owned health job at a time."""

    OPEN = "open"
    RUNNING = "running"
    CLOSING = "closing"
    CLOSED = "closed"


class _SystemHealthWorkerSignals(QObject):
    snapshot_ready = Signal(object)
    failed = Signal(str)
    finished = Signal()


class _SystemHealthWorker(QRunnable):
    """One retained runnable whose signal source survives owner teardown."""

    _retained: set[_SystemHealthWorker] = set()
    _retained_lock = Lock()

    def __init__(
        self,
        collector: Callable[[], SystemHealthSnapshot],
        *,
        generation: int,
    ) -> None:
        super().__init__()
        self.collector = collector
        self.generation = generation
        self.signals = _SystemHealthWorkerSignals()
        self.completion_event = Event()
        self.setAutoDelete(True)

    def retain(self) -> None:
        with self._retained_lock:
            self._retained.add(self)

    def abandon(self) -> None:
        self.completion_event.set()
        self._release()

    def _release(self) -> None:
        with self._retained_lock:
            self._retained.discard(self)

    @staticmethod
    def _safe_emit(signal, *args: object) -> None:
        try:
            signal.emit(*args)
        except RuntimeError:
            # A defensive last line for abnormal QObject teardown. Normal
            # close retains this worker and its signal source until completion.
            return

    @Slot()
    def run(self) -> None:
        try:
            snapshot = self.collector()
        except Exception as exc:
            self._safe_emit(self.signals.failed, str(exc))
        else:
            self._safe_emit(self.signals.snapshot_ready, snapshot)
        finally:
            self._safe_emit(self.signals.finished)
            self.completion_event.set()
            self._release()


class SystemHealthMonitor(QObject):
    """Run health checks in one owned pool with bounded terminal shutdown."""

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
        self._owns_thread_pool = thread_pool is None
        self.thread_pool = thread_pool or QThreadPool(self)
        self._lifecycle_state = SystemHealthLifecycleState.OPEN
        self._last_snapshot: SystemHealthSnapshot | None = None
        self._worker: _SystemHealthWorker | None = None
        self._generation = 0

    @property
    def lifecycle_state(self) -> SystemHealthLifecycleState:
        return self._lifecycle_state

    @property
    def is_running(self) -> bool:
        return self._lifecycle_state is SystemHealthLifecycleState.RUNNING

    @property
    def last_snapshot(self) -> SystemHealthSnapshot | None:
        return self._last_snapshot

    def request_refresh(self) -> bool:
        """Start one current-generation check only while the monitor is open."""
        if self._lifecycle_state is not SystemHealthLifecycleState.OPEN:
            return False

        self._generation += 1
        worker = _SystemHealthWorker(
            self.collector,
            generation=self._generation,
        )
        self._worker = worker
        self._lifecycle_state = SystemHealthLifecycleState.RUNNING
        self.busy_changed.emit(True)

        worker.signals.snapshot_ready.connect(self._handle_snapshot)
        worker.signals.failed.connect(self._handle_failure)
        worker.signals.finished.connect(self._handle_finished)
        worker.retain()
        self.thread_pool.start(worker)
        return True

    def shutdown(self, timeout_ms: int = 1000) -> bool:
        """Close only monitor-owned work within a fixed caller budget."""
        if timeout_ms < 0:
            raise ValueError("timeout_ms must be non-negative")
        if self._lifecycle_state is SystemHealthLifecycleState.CLOSED:
            return True

        self._lifecycle_state = SystemHealthLifecycleState.CLOSING
        worker = self._worker
        if worker is None:
            self._lifecycle_state = SystemHealthLifecycleState.CLOSED
            return True

        try_take = getattr(self.thread_pool, "tryTake", None)
        if callable(try_take) and bool(try_take(worker)):
            worker.abandon()
            self._finish_close(worker)
            return True

        deadline = monotonic() + (timeout_ms / 1000)
        if not worker.completion_event.wait(timeout=max(0.0, deadline - monotonic())):
            return False

        if self._owns_thread_pool:
            wait_for_done = getattr(self.thread_pool, "waitForDone", None)
            if callable(wait_for_done):
                remaining_ms = max(0, round((deadline - monotonic()) * 1000))
                if not bool(wait_for_done(remaining_ms)):
                    return False

        self._finish_close(worker)
        return True

    def _is_current_sender(self) -> bool:
        worker = self._worker
        return worker is not None and self.sender() is worker.signals

    @Slot(object)
    def _handle_snapshot(self, snapshot: SystemHealthSnapshot) -> None:
        if (
            self._lifecycle_state is not SystemHealthLifecycleState.RUNNING
            or not self._is_current_sender()
        ):
            return
        self._last_snapshot = snapshot
        self.snapshot_ready.emit(snapshot)

    @Slot(str)
    def _handle_failure(self, message: str) -> None:
        if (
            self._lifecycle_state is not SystemHealthLifecycleState.RUNNING
            or not self._is_current_sender()
        ):
            return
        self.check_failed.emit(message)

    @Slot()
    def _handle_finished(self) -> None:
        if not self._is_current_sender():
            return
        worker = self._worker
        if worker is None:
            return
        if self._lifecycle_state is SystemHealthLifecycleState.CLOSING:
            self._finish_close(worker)
            return
        if self._lifecycle_state is not SystemHealthLifecycleState.RUNNING:
            return
        self._worker = None
        self._lifecycle_state = SystemHealthLifecycleState.OPEN
        self.busy_changed.emit(False)

    def _finish_close(self, worker: _SystemHealthWorker) -> None:
        if self._worker is worker:
            self._worker = None
        self._lifecycle_state = SystemHealthLifecycleState.CLOSED


__all__ = ["SystemHealthLifecycleState", "SystemHealthMonitor"]
