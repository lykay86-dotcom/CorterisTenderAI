from __future__ import annotations

from dataclasses import replace

from app.tenders.corteris_filter import (
    CorterisTenderClassifier,
    RelevanceGrade,
    TenderDirection,
)
from app.tenders.matching_catalog import (
    MatchingCatalogEntry,
    MatchingCatalogRepository,
    MatchingEntryKind,
)
from app.tenders.collector.participation_score import (
    CorterisParticipationRanker,
)
from tests.collector_c3_helpers import make_tender


def test_default_catalog_is_seeded_and_versioned(tmp_path) -> None:
    repository = MatchingCatalogRepository(tmp_path / "registry.sqlite3")

    catalog = repository.load()

    assert catalog.revision == 1
    assert catalog.entries
    assert any(item.kind == MatchingEntryKind.ABBREVIATION or item.term == "скуд" for item in catalog.entries)
    assert any(item.kind == MatchingEntryKind.OKPD2 for item in catalog.entries)
    assert any(item.kind == MatchingEntryKind.EXCLUSION for item in catalog.entries)


def test_editable_synonym_transliteration_weight_and_activity_affect_classifier(tmp_path) -> None:
    repository = MatchingCatalogRepository(tmp_path / "registry.sqlite3")
    catalog = repository.load()
    custom = (
        MatchingCatalogEntry(
            entry_id="synonym",
            group_key="video_surveillance",
            term="умный глаз",
            kind=MatchingEntryKind.SYNONYM,
            direction=TenderDirection.VIDEO_SURVEILLANCE,
            canonical_term="видеонаблюдение",
            weight_percent=200,
            category="user vocabulary",
        ),
        MatchingCatalogEntry(
            entry_id="inactive",
            group_key="video_surveillance",
            term="скрытый термин",
            kind=MatchingEntryKind.TRANSLITERATION,
            direction=TenderDirection.VIDEO_SURVEILLANCE,
            active=False,
        ),
    )
    saved = repository.save(custom, catalog.settings, saved_by="tester")
    classifier = CorterisTenderClassifier(saved.to_search_profile())

    matched = classifier.evaluate(make_tender(title="Монтаж системы умный глаз"))
    inactive = classifier.evaluate(make_tender(title="Скрытый термин"))

    assert matched.score >= 36
    assert TenderDirection.VIDEO_SURVEILLANCE in matched.directions
    assert inactive.grade == RelevanceGrade.EXCLUDED
    assert repository.load().revision == 2


def test_okpd2_can_match_without_keyword_and_exclusion_is_separate(tmp_path) -> None:
    repository = MatchingCatalogRepository(tmp_path / "registry.sqlite3")
    initial = repository.load()
    entries = (
        MatchingCatalogEntry(
            "okpd", "video", "26.40.33", MatchingEntryKind.OKPD2,
            TenderDirection.VIDEO_SURVEILLANCE,
        ),
        MatchingCatalogEntry(
            "exclude", "exceptions", "медицинская камера",
            MatchingEntryKind.EXCLUSION,
        ),
    )
    catalog = repository.save(entries, replace(initial.settings, minimum_score=1))
    classifier = CorterisTenderClassifier(catalog.to_search_profile())
    coded = make_tender(title="Поставка оборудования")
    medical = replace(coded, title="Медицинская камера", classification_codes=())

    coded_result = classifier.evaluate(coded)
    medical_result = classifier.evaluate(medical)

    assert coded_result.matched_okpd2 == ("26.40.33.190",)
    assert coded_result.relevant
    assert medical_result.hard_excluded


def test_reset_defaults_creates_revision_instead_of_deleting_history(tmp_path) -> None:
    repository = MatchingCatalogRepository(tmp_path / "registry.sqlite3")
    catalog = repository.load()
    repository.save(catalog.entries[:1], catalog.settings)

    restored = repository.reset_defaults()

    assert restored.revision == 3
    with repository._connect() as connection:
        revisions = connection.execute(
            "SELECT COUNT(*) AS total FROM collector_matching_catalog_revisions"
        ).fetchone()["total"]
    assert revisions == 3


def test_participation_ranker_uses_catalog_exclusions_not_private_list(tmp_path) -> None:
    repository = MatchingCatalogRepository(tmp_path / "registry.sqlite3")
    initial = repository.load()
    catalog = repository.save(
        (
            MatchingCatalogEntry(
                "medical-profile",
                "video",
                "медицинская видеокамера",
                MatchingEntryKind.STRONG_KEYWORD,
                TenderDirection.VIDEO_SURVEILLANCE,
            ),
        ),
        replace(initial.settings, minimum_score=1),
    )
    classifier = CorterisTenderClassifier(catalog.to_search_profile())

    score = CorterisParticipationRanker(classifier=classifier).score(
        make_tender(title="Медицинская видеокамера")
    )

    assert not score.hard_excluded
