"""RM-129 shared projection, runtime ownership, and UI status contract."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path

import httpx

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMainWindow

from app.tenders.business_profile import BusinessCapabilityProjection
from app.tenders.collector.async_provider_factory import create_default_collector_service
from app.tenders.collector.company_capability import (
    CompanyCapabilityLoadStatus,
    CompanyCapabilityProfile,
    CompanyCapabilityProfileRepository,
)
from app.tenders.collector.network_runtime import create_collector_network_runtime
from app.tenders.collector.participation_score import CorterisCompanyProfile
from app.tenders.collector.participation_score_service import (
    CorterisParticipationScoreService,
)
from app.tenders.search_profile_repository import TenderSearchProfileRepository
from app.tenders.search_runtime import TenderSearchRuntime, create_tender_search_runtime
from app.ui.company_capability_dialog import CompanyCapabilityDialog
from app.ui.tender_search_ui_controller import TenderSearchUiController
from tests.collector_c3_helpers import make_tender


NOW = datetime(2026, 7, 12, tzinfo=timezone.utc)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _confirmed() -> CompanyCapabilityProfile:
    return CompanyCapabilityProfile(
        company_name="ООО КОРТЕРИС",
        business_directions=("видеонаблюдение",),
        self_install_regions=("Москва",),
        licenses=("МЧС",),
        installation_crew_count=2,
        confirmed_experience=("Контракт №1",),
        max_project_amount=Decimal("30000000"),
        working_capital=Decimal("5000000"),
        equipment=("IP-камера",),
        suppliers=("Поставщик",),
        base_currency="RUB",
    ).confirm(confirmed_by="Директор", confirmed_at=NOW)


def test_manual_score_builds_one_projection_for_ranker_and_stop(
    monkeypatch,
) -> None:
    profile = _confirmed()
    captured: dict[str, object] = {}

    class TenderRepository:
        @staticmethod
        def get_tender(_registry_key: str):
            return make_tender()

    class CapabilityRepository:
        @staticmethod
        def load() -> CompanyCapabilityProfile:
            return profile

    class FakeScoringProfile:
        @classmethod
        def from_business_profile(cls, projection: BusinessCapabilityProjection):
            captured["score_projection"] = projection
            return object()

    class FakeRanker:
        def __init__(self, _profile, *, classifier=None) -> None:
            captured["ranker_classifier"] = classifier

        @staticmethod
        def score(_tender, context):
            captured["stop_assessment"] = context.stop_factor_assessment
            return object()

    class FakeStopEngine:
        def __init__(self, projection: BusinessCapabilityProjection) -> None:
            captured["stop_projection"] = projection

        @staticmethod
        def evaluate(_registry_key, _tender, *, analysis=None):
            return ("stop", analysis)

    import app.tenders.collector.participation_score_service as module

    monkeypatch.setattr(module, "CorterisCompanyProfile", FakeScoringProfile)
    monkeypatch.setattr(module, "CorterisParticipationRanker", FakeRanker)
    monkeypatch.setattr(module, "StopFactorEngine", FakeStopEngine)
    service = CorterisParticipationScoreService(
        TenderRepository(),
        object(),
        capability_repository=CapabilityRepository(),
    )

    service.evaluate("tender:1", persist=False)

    assert captured["score_projection"] is captured["stop_projection"]
    assert captured["stop_assessment"] == ("stop", None)


def test_runtime_exposes_same_capability_repository_used_by_manual_score(tmp_path: Path) -> None:
    runtime = create_tender_search_runtime(tmp_path)

    assert runtime.capability_repository is not None
    assert runtime.participation_score_service is not None
    assert runtime.participation_score_service.capability_repository is (
        runtime.capability_repository
    )
    assert runtime.capability_repository.path == tmp_path / "company_capability_profile.json"


def test_automatic_collector_uses_the_same_projection_without_network(tmp_path: Path) -> None:
    async def scenario() -> None:
        requests: list[httpx.Request] = []

        def handle(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, request=request)

        raw = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        network_runtime = create_collector_network_runtime(client=raw)
        CompanyCapabilityProfileRepository(tmp_path / "company_capability_profile.json").save(
            _confirmed()
        )

        service = create_default_collector_service(tmp_path, network_runtime)

        assert service.stop_factor_engine is not None
        projection = service.stop_factor_engine.profile
        assert isinstance(projection, BusinessCapabilityProjection)
        assert service.ranker.profile == CorterisCompanyProfile.from_business_profile(projection)
        assert requests == []
        await raw.aclose()

    asyncio.run(scenario())


def test_dialog_shows_corrupt_status_without_touching_file(tmp_path: Path) -> None:
    app = _app()
    path = tmp_path / "company_capability_profile.json"
    original = b'{"schema_version": 2, "profile": '
    path.write_bytes(original)
    dialog = CompanyCapabilityDialog(CompanyCapabilityProfileRepository(path))

    assert dialog.load_result.status is CompanyCapabilityLoadStatus.CORRUPT
    assert "повреж" in dialog.status.text().casefold()
    assert path.read_bytes() == original
    app.processEvents()


def test_dialog_shows_migrated_v1_without_automatic_rewrite(tmp_path: Path) -> None:
    app = _app()
    path = tmp_path / "company_capability_profile.json"
    legacy = _confirmed().to_dict()
    for key in (
        "base_currency",
        "confirmation_version",
        "confirmation_fingerprint",
        "confirmation_source",
    ):
        legacy.pop(key)
    original = json.dumps(
        {"schema_version": 1, "profile": legacy},
        ensure_ascii=False,
    ).encode("utf-8")
    path.write_bytes(original)

    dialog = CompanyCapabilityDialog(CompanyCapabilityProfileRepository(path))

    assert dialog.load_result.status is CompanyCapabilityLoadStatus.MIGRATED_V1
    assert "schema v1" in dialog.status.text()
    assert dialog.confirmation.isChecked()
    assert path.read_bytes() == original
    dialog.close()
    app.processEvents()


def test_dialog_shows_future_schema_without_automatic_rewrite(tmp_path: Path) -> None:
    app = _app()
    path = tmp_path / "company_capability_profile.json"
    original = b'{"schema_version":999,"profile":{}}'
    path.write_bytes(original)

    dialog = CompanyCapabilityDialog(CompanyCapabilityProfileRepository(path))

    assert dialog.load_result.status is CompanyCapabilityLoadStatus.UNSUPPORTED_FUTURE
    assert "новее поддерживаемой" in dialog.status.text()
    assert path.read_bytes() == original
    dialog.close()
    app.processEvents()


def test_editing_loaded_facts_requires_new_explicit_confirmation(tmp_path: Path) -> None:
    app = _app()
    repository = CompanyCapabilityProfileRepository(tmp_path / "company_capability_profile.json")
    repository.save(_confirmed())
    dialog = CompanyCapabilityDialog(repository)

    assert dialog.confirmation.isChecked()
    dialog.company_name.setText("ООО КОРТЕРИС — новое имя")
    assert not dialog.confirmation.isChecked()

    dialog.confirmation.setChecked(True)
    dialog.save_profile()
    restored = repository.load_result().profile
    assert restored.company_name == "ООО КОРТЕРИС — новое имя"
    assert restored.is_confirmed
    app.processEvents()


def test_controller_reuses_runtime_repository_and_one_dialog(tmp_path: Path) -> None:
    app = _app()
    search_repository = TenderSearchProfileRepository(tmp_path / "search_profiles.json")
    search_repository.initialize()
    capability_repository = CompanyCapabilityProfileRepository(
        tmp_path / "company_capability_profile.json"
    )
    runtime = TenderSearchRuntime(
        data_directory=tmp_path,
        repository=search_repository,
        registry=object(),
        engine=object(),
        search_service=object(),
        runner=object(),
        capability_repository=capability_repository,
    )
    window = QMainWindow()
    controller = TenderSearchUiController(tmp_path, runtime=runtime, parent=window)

    controller.open_company_capability_dialog()
    first = controller._company_capability_dialog
    controller.open_company_capability_dialog()

    assert first is not None
    assert controller._company_capability_dialog is first
    assert first.repository is capability_repository
    assert controller.company_capability_action.objectName() == "actionCompanyCapabilityProfile"
    first.close()
    app.processEvents()
