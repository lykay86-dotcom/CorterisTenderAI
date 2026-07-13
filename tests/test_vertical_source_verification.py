from __future__ import annotations

import asyncio

from app.tenders.collector.provider_control import (
    CollectorProviderManager,
    ProviderUiState,
)
from app.tenders.collector.vertical_source_verification import (
    REQUIRED_VERTICAL_STAGES,
    VerifiedVerticalSourceSmokeService,
    VerticalSmokeStage,
    VerticalSourceStatus,
    VerticalSourceVerificationRepository,
)
from app.tenders.provider_base import ProviderHealth, ProviderHealthStatus


def _callbacks():
    return {
        stage: (lambda current=stage: (f"{current.value} выполнен", 1))
        for stage in REQUIRED_VERTICAL_STAGES
    }


def test_only_live_pass_of_every_stage_can_be_working(tmp_path) -> None:
    repository = VerticalSourceVerificationRepository(tmp_path / "registry.sqlite3")
    service = VerifiedVerticalSourceSmokeService(repository)

    verification = service.run(
        "eis",
        "public_html_async",
        _callbacks(),
        live=True,
    )

    assert verification.status == VerticalSourceStatus.WORKING
    assert verification.qualifies_as_working
    assert repository.is_working("eis")
    assert len(verification.steps) == len(REQUIRED_VERTICAL_STAGES)


def test_fixture_pass_is_unverified_and_cannot_promote_source(tmp_path) -> None:
    repository = VerticalSourceVerificationRepository(tmp_path / "registry.sqlite3")
    verification = VerifiedVerticalSourceSmokeService(repository).run(
        "eis",
        "fixture",
        _callbacks(),
        live=False,
    )

    assert verification.status == VerticalSourceStatus.UNVERIFIED
    assert not verification.qualifies_as_working
    assert not repository.is_working("eis")


def test_missing_or_failed_stage_records_failure_and_stops_pipeline(tmp_path) -> None:
    repository = VerticalSourceVerificationRepository(tmp_path / "registry.sqlite3")
    callbacks = _callbacks()
    callbacks.pop(VerticalSmokeStage.DOCUMENTS)

    verification = VerifiedVerticalSourceSmokeService(repository).run(
        "eis",
        "public_html_async",
        callbacks,
        live=True,
    )

    assert verification.status == VerticalSourceStatus.FAILED
    assert verification.steps[-1].stage == VerticalSmokeStage.DOCUMENTS
    assert not verification.steps[-1].passed
    assert "documents" in verification.error_message


def test_health_available_is_unverified_until_vertical_smoke_passes(tmp_path) -> None:
    async def checker(provider_ids):
        return {
            provider_id: ProviderHealth(
                provider_id=provider_id,
                status=ProviderHealthStatus.AVAILABLE,
                checked_at="2026-07-12T12:00:00+00:00",
                message="Health-check успешен",
            )
            for provider_id in provider_ids
        }

    repository = VerticalSourceVerificationRepository(tmp_path / "tender_registry.sqlite3")
    manager = CollectorProviderManager(
        tmp_path,
        environment={},
        health_checker=checker,
        vertical_verification_repository=repository,
    )
    before = asyncio.run(manager.check_provider("eis"))
    VerifiedVerticalSourceSmokeService(repository).run(
        "eis", "public_html_async", _callbacks(), live=True
    )
    after = manager.states()[0]

    assert before.ui_state == ProviderUiState.UNVERIFIED
    assert after.provider_id == "eis"
    assert after.ui_state == ProviderUiState.WORKING
