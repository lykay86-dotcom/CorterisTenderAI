from app.tenders.collector.store import CollectorStateRepository


def test_missing_database_read_methods_do_not_create_it(tmp_path) -> None:
    path = tmp_path / "missing.sqlite3"
    repository = CollectorStateRepository(path)

    assert repository.list_provider_outcomes(limit=10) == ()
    assert repository.list_checkpoints() == ()
    assert not path.exists()


def test_provider_outcomes_and_checkpoints_are_ordered_read_models(tmp_path) -> None:
    from app.tenders.collector.async_engine import (
        AsyncProviderSearchOutcome,
        AsyncProviderSearchStatus,
    )
    from app.tenders.collector.checkpoint import CollectorCheckpoint
    from app.tenders.collector.models import CollectionRunStatus
    from app.tenders.provider_base import TenderSearchQuery

    repository = CollectorStateRepository(tmp_path / "registry.sqlite3")
    run_id = repository.start_run(
        TenderSearchQuery(keywords=("test",)),
        provider_ids=("eis",),
        started_at="2026-07-18T10:00:00+00:00",
    )
    repository.complete_run(
        run_id,
        status=CollectionRunStatus.COMPLETED,
        completed_at="2026-07-18T10:01:00+00:00",
        provider_outcomes=(
            AsyncProviderSearchOutcome(
                provider_id="eis",
                display_name="ЕИС",
                status=AsyncProviderSearchStatus.SUCCESS,
                elapsed_ms=100,
            ),
        ),
    )
    repository.save_checkpoint(
        CollectorCheckpoint("eis", scope_key="z", updated_at="2026-07-18T10:00:00+00:00")
    )
    repository.save_checkpoint(
        CollectorCheckpoint("eis", scope_key="a", updated_at="2026-07-18T11:00:00+00:00")
    )

    outcomes = repository.list_provider_outcomes(provider_id="eis", limit=10)
    checkpoints = repository.list_checkpoints(provider_id="eis")
    assert [(item.run_id, item.status) for item in outcomes] == [(run_id, "success")]
    assert [(item.provider_id, item.scope_key) for item in checkpoints] == [
        ("eis", "a"),
        ("eis", "z"),
    ]
