"""C17 editable, versioned matching catalog stored in SQLite."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Iterable
from uuid import uuid4

from app.tenders.collector_database import initialize_collector_database
from app.tenders.corteris_filter import (
    CorterisSearchProfile,
    DEFAULT_CORTERIS_PROFILE,
    DirectionRule,
    TenderDirection,
)


class MatchingEntryKind(StrEnum):
    STRONG_KEYWORD = "strong_keyword"
    WEAK_KEYWORD = "weak_keyword"
    ACTION = "action"
    ABBREVIATION = "abbreviation"
    SYNONYM = "synonym"
    TRANSLITERATION = "transliteration"
    OKPD2 = "okpd2"
    EXCLUSION = "exclusion"


@dataclass(frozen=True, slots=True)
class MatchingCatalogEntry:
    entry_id: str
    group_key: str
    term: str
    kind: MatchingEntryKind
    direction: TenderDirection | None = None
    canonical_term: str = ""
    weight_percent: int = 100
    category: str = ""
    source: str = "user"
    active: bool = True

    def __post_init__(self) -> None:
        if not self.entry_id.strip() or not self.group_key.strip() or not self.term.strip():
            raise ValueError("entry_id, group_key and term must not be empty")
        if not 0 <= self.weight_percent <= 500:
            raise ValueError("weight_percent must be between 0 and 500")
        direction_required = self.kind not in {
            MatchingEntryKind.ACTION,
            MatchingEntryKind.EXCLUSION,
        }
        if direction_required and self.direction is None:
            raise ValueError(f"direction is required for {self.kind.value}")


@dataclass(frozen=True, slots=True)
class MatchingCatalogSettings:
    minimum_score: int = 24
    medium_score: int = 40
    high_score: int = 65
    title_strong_weight: int = 18
    title_weak_weight: int = 7
    body_strong_weight: int = 8
    body_weak_weight: int = 3
    tag_strong_weight: int = 12
    tag_weak_weight: int = 5
    action_bonus: int = 6
    multi_direction_bonus: int = 8
    okpd2_weight: int = 10

    def __post_init__(self) -> None:
        if not 0 <= self.minimum_score <= self.medium_score <= self.high_score <= 100:
            raise ValueError("invalid score thresholds")
        for name in (
            "title_strong_weight",
            "title_weak_weight",
            "body_strong_weight",
            "body_weak_weight",
            "tag_strong_weight",
            "tag_weak_weight",
            "action_bonus",
            "multi_direction_bonus",
            "okpd2_weight",
        ):
            if not 0 <= getattr(self, name) <= 100:
                raise ValueError(f"{name} must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class MatchingCatalog:
    entries: tuple[MatchingCatalogEntry, ...]
    settings: MatchingCatalogSettings
    revision: int
    updated_at: str

    def to_search_profile(self) -> CorterisSearchProfile:
        active = tuple(item for item in self.entries if item.active)
        rules: list[DirectionRule] = []
        for direction in TenderDirection:
            items = tuple(item for item in active if item.direction == direction)
            strong_kinds = {
                MatchingEntryKind.STRONG_KEYWORD,
                MatchingEntryKind.ABBREVIATION,
                MatchingEntryKind.SYNONYM,
                MatchingEntryKind.TRANSLITERATION,
            }
            rules.append(
                DirectionRule(
                    direction=direction,
                    strong_terms=_unique(item.term for item in items if item.kind in strong_kinds),
                    weak_terms=_unique(
                        item.term for item in items if item.kind == MatchingEntryKind.WEAK_KEYWORD
                    ),
                    okpd2_codes=_unique(
                        item.term for item in items if item.kind == MatchingEntryKind.OKPD2
                    ),
                )
            )
        settings = self.settings
        return CorterisSearchProfile(
            rules=tuple(rules),
            action_terms=_unique(
                item.term for item in active if item.kind == MatchingEntryKind.ACTION
            ),
            hard_exclusion_terms=_unique(
                item.term for item in active if item.kind == MatchingEntryKind.EXCLUSION
            ),
            minimum_score=settings.minimum_score,
            medium_score=settings.medium_score,
            high_score=settings.high_score,
            title_strong_weight=settings.title_strong_weight,
            title_weak_weight=settings.title_weak_weight,
            body_strong_weight=settings.body_strong_weight,
            body_weak_weight=settings.body_weak_weight,
            tag_strong_weight=settings.tag_strong_weight,
            tag_weak_weight=settings.tag_weak_weight,
            action_bonus=settings.action_bonus,
            multi_direction_bonus=settings.multi_direction_bonus,
            okpd2_weight=settings.okpd2_weight,
            term_weight_percent=tuple((item.term, item.weight_percent) for item in active),
        )


class MatchingCatalogRepository:
    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._lock = RLock()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            initialize_collector_database(self.path)
        with self._lock, self._connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) AS total FROM collector_matching_catalog_entries"
            ).fetchone()["total"]
            if int(count) == 0:
                self._replace(
                    connection, _default_entries(), MatchingCatalogSettings(), "system-default"
                )

    def load(self) -> MatchingCatalog:
        self.initialize()
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM collector_matching_catalog_entries ORDER BY group_key, kind, term"
            ).fetchall()
            settings_row = connection.execute(
                "SELECT * FROM collector_matching_catalog_settings WHERE singleton_id = 1"
            ).fetchone()
        settings_payload = json.loads(str(settings_row["payload_json"]))
        return MatchingCatalog(
            entries=tuple(_row_to_entry(row) for row in rows),
            settings=MatchingCatalogSettings(**settings_payload),
            revision=int(settings_row["revision"]),
            updated_at=str(settings_row["updated_at"]),
        )

    def load_profile(self) -> CorterisSearchProfile:
        return self.load().to_search_profile()

    def save(
        self,
        entries: Iterable[MatchingCatalogEntry],
        settings: MatchingCatalogSettings,
        *,
        saved_by: str = "user",
    ) -> MatchingCatalog:
        values = tuple(entries)
        identities = {
            (item.group_key.casefold(), item.term.casefold(), item.kind, item.direction)
            for item in values
        }
        if len(identities) != len(values):
            raise ValueError("matching catalog contains duplicate entries")
        self.initialize()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._replace(connection, values, settings, saved_by.strip() or "user")
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return self.load()

    def reset_defaults(self, *, saved_by: str = "user") -> MatchingCatalog:
        return self.save(_default_entries(), MatchingCatalogSettings(), saved_by=saved_by)

    @staticmethod
    def _replace(
        connection: sqlite3.Connection,
        entries: tuple[MatchingCatalogEntry, ...],
        settings: MatchingCatalogSettings,
        saved_by: str,
    ) -> None:
        previous = connection.execute(
            "SELECT revision FROM collector_matching_catalog_settings WHERE singleton_id = 1"
        ).fetchone()
        revision = int(previous["revision"]) + 1 if previous is not None else 1
        moment = datetime.now(timezone.utc).isoformat(timespec="seconds")
        connection.execute("DELETE FROM collector_matching_catalog_entries")
        connection.executemany(
            """INSERT INTO collector_matching_catalog_entries(
                entry_id, group_key, term, kind, direction, canonical_term,
                weight_percent, category, source, active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    item.entry_id,
                    item.group_key,
                    item.term,
                    item.kind.value,
                    item.direction.value if item.direction else "",
                    item.canonical_term,
                    item.weight_percent,
                    item.category,
                    item.source,
                    int(item.active),
                    moment,
                )
                for item in entries
            ],
        )
        settings_payload = _settings_payload(settings)
        connection.execute(
            """INSERT INTO collector_matching_catalog_settings(
                singleton_id, payload_json, revision, updated_at
            ) VALUES (1, ?, ?, ?)
            ON CONFLICT(singleton_id) DO UPDATE SET
                payload_json=excluded.payload_json,
                revision=excluded.revision,
                updated_at=excluded.updated_at""",
            (json.dumps(settings_payload, ensure_ascii=False, sort_keys=True), revision, moment),
        )
        snapshot = {
            "settings": settings_payload,
            "entries": [_entry_payload(item) for item in entries],
        }
        connection.execute(
            "INSERT INTO collector_matching_catalog_revisions VALUES (?, ?, ?, ?, ?)",
            (
                uuid4().hex,
                revision,
                moment,
                saved_by,
                json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
            ),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _default_entries() -> tuple[MatchingCatalogEntry, ...]:
    result: list[MatchingCatalogEntry] = []
    for rule in DEFAULT_CORTERIS_PROFILE.rules:
        for kind, terms in (
            (MatchingEntryKind.STRONG_KEYWORD, rule.strong_terms),
            (MatchingEntryKind.WEAK_KEYWORD, rule.weak_terms),
        ):
            for term in terms:
                result.append(_default_entry(rule.direction.value, term, kind, rule.direction))
    okpd2_defaults = {
        TenderDirection.VIDEO_SURVEILLANCE: ("26.30", "26.40.33"),
        TenderDirection.OPS: ("27.90.70",),
        TenderDirection.MAINTENANCE: ("33.13", "80.20"),
        TenderDirection.INTEGRATED_SECURITY: ("43.21", "71.12"),
    }
    for direction, codes in okpd2_defaults.items():
        for code in codes:
            result.append(_default_entry(direction.value, code, MatchingEntryKind.OKPD2, direction))
    for term in DEFAULT_CORTERIS_PROFILE.action_terms:
        result.append(_default_entry("actions", term, MatchingEntryKind.ACTION, None))
    for term in DEFAULT_CORTERIS_PROFILE.hard_exclusion_terms:
        result.append(_default_entry("exclusions", term, MatchingEntryKind.EXCLUSION, None))
    return tuple(result)


def _default_entry(
    group: str, term: str, kind: MatchingEntryKind, direction: TenderDirection | None
) -> MatchingCatalogEntry:
    identity = hashlib.sha256(f"{group}|{kind.value}|{term}".encode("utf-8")).hexdigest()[:24]
    return MatchingCatalogEntry(
        identity, group, term, kind, direction, category="default", source="built-in"
    )


def _row_to_entry(row: sqlite3.Row) -> MatchingCatalogEntry:
    direction = str(row["direction"])
    return MatchingCatalogEntry(
        entry_id=str(row["entry_id"]),
        group_key=str(row["group_key"]),
        term=str(row["term"]),
        kind=MatchingEntryKind(str(row["kind"])),
        direction=TenderDirection(direction) if direction else None,
        canonical_term=str(row["canonical_term"]),
        weight_percent=int(row["weight_percent"]),
        category=str(row["category"]),
        source=str(row["source"]),
        active=bool(row["active"]),
    )


def _settings_payload(settings: MatchingCatalogSettings) -> dict[str, int]:
    return {name: int(getattr(settings, name)) for name in settings.__dataclass_fields__}


def _entry_payload(item: MatchingCatalogEntry) -> dict[str, object]:
    return {
        "entry_id": item.entry_id,
        "group_key": item.group_key,
        "term": item.term,
        "kind": item.kind.value,
        "direction": item.direction.value if item.direction else "",
        "canonical_term": item.canonical_term,
        "weight_percent": item.weight_percent,
        "category": item.category,
        "source": item.source,
        "active": item.active,
    }


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        rendered = str(value).strip()
        identity = rendered.casefold()
        if rendered and identity not in seen:
            seen.add(identity)
            result.append(rendered)
    return tuple(result)


__all__ = [
    "MatchingCatalog",
    "MatchingCatalogEntry",
    "MatchingCatalogRepository",
    "MatchingCatalogSettings",
    "MatchingEntryKind",
]
