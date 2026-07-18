"""RM-140 application-owned search lifecycle regressions."""

from __future__ import annotations

from app.ui.tender_search_ui_controller import (
    TenderSearchLifecycleState,
    TenderSearchUiController,
)
from tests.test_tender_collector_ui_controller import (
    FakeCollectorSession,
    FakeProviderManager,
    _app,
    _runtime,
)


class QueuedThreadPool:
    def __init__(self) -> None:
        self.runnables: list[object] = []
        self.wait_calls: list[int] = []

    def start(self, runnable) -> None:
        self.runnables.append(runnable)

    def tryTake(self, runnable) -> bool:
        if runnable not in self.runnables:
            return False
        self.runnables.remove(runnable)
        return True


class ImmediateThreadPool:
    def start(self, runnable) -> None:
        runnable.run()

    def waitForDone(self, timeout_ms: int) -> bool:
        self.wait_calls.append(timeout_ms)
        return True


def _controller(tmp_path, pool: QueuedThreadPool) -> TenderSearchUiController:
    _app()
    return TenderSearchUiController(
        tmp_path,
        runtime=_runtime(tmp_path),
        provider_manager=FakeProviderManager(),
        collector_session=FakeCollectorSession(),
        thread_pool=pool,
    )


def test_queued_run_has_one_admission_and_one_terminal_boundary(tmp_path) -> None:
    pool = QueuedThreadPool()
    controller = _controller(tmp_path, pool)

    assert controller.try_start_collector("all-corteris", ("eis",))
    queued = controller.lifecycle_snapshot
    assert queued.state is TenderSearchLifecycleState.QUEUED
    assert not controller.try_start_collector("all-corteris", ("eis",))
    assert len(pool.runnables) == 1

    assert controller.shutdown(timeout_ms=50)
    terminal = controller.lifecycle_snapshot
    assert terminal.state is TenderSearchLifecycleState.CLOSED
    assert terminal.revision > queued.revision
    assert controller.shutdown(timeout_ms=50)
    assert controller.lifecycle_snapshot == terminal
    assert not controller.scheduler_ui_controller.timer.isActive()


def test_late_worker_result_cannot_mutate_shutdown_terminal_state(tmp_path) -> None:
    pool = QueuedThreadPool()
    controller = _controller(tmp_path, pool)
    assert controller.try_start_collector("all-corteris", ("eis",))
    worker = pool.runnables[0]

    assert controller.shutdown(timeout_ms=50)
    terminal = controller.lifecycle_snapshot

    # Simulate a queued callback escaping an external pool after the app owner
    # has already published its terminal boundary.
    worker.run()

    assert controller.lifecycle_snapshot == terminal
    assert controller._collector_worker is None


def test_scheduler_and_manual_entry_points_share_admission_generation(tmp_path) -> None:
    pool = QueuedThreadPool()
    controller = _controller(tmp_path, pool)

    assert controller.try_start_collector("all-corteris", ("eis",))
    generation = controller.lifecycle_snapshot.generation
    controller.scheduler_ui_controller.run_now("all-corteris", ("eis",))

    assert controller.lifecycle_snapshot.generation == generation
    assert len(pool.runnables) == 1


def test_completed_run_allows_exactly_one_new_generation(tmp_path) -> None:
    pool = ImmediateThreadPool()
    controller = _controller(tmp_path, pool)  # type: ignore[arg-type]

    assert controller.try_start_collector("all-corteris", ("eis",))
    first = controller.lifecycle_snapshot
    assert first.state is TenderSearchLifecycleState.COMPLETED

    assert controller.try_start_collector("all-corteris", ("eis",))
    second = controller.lifecycle_snapshot
    assert second.state is TenderSearchLifecycleState.COMPLETED
    assert second.generation == first.generation + 1
