"""Rule-based analysis of extracted tender documentation.

This module does not make legal conclusions and does not call an external AI.
It extracts verifiable requirements and evidence from locally stored text so
that later scoring and AI layers can work with a structured, auditable input.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from threading import RLock
from typing import Iterable, Sequence
from uuid import uuid4

from app.core.document_classification import DocumentKind, classify_document_kind
from app.tenders.document_text_extractor import (
    StoredDocumentText,
    TenderDocumentTextService,
)


class RequirementCategory(StrEnum):
    DOCUMENT = "document"
    LICENSE = "license"
    EXPERIENCE = "experience"
    SECURITY = "security"
    DEADLINE = "deadline"
    PAYMENT = "payment"
    WARRANTY = "warranty"
    PENALTY = "penalty"
    CONTRACT = "contract"
    TECHNICAL = "technical"
    STOP_FACTOR = "stop_factor"


class FindingSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AnalysisRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class TenderAnalysisSource:
    document_key: str
    source_name: str
    text: str
    checksum_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.document_key.strip():
            raise ValueError("document_key must not be empty")
        if not self.source_name.strip():
            raise ValueError("source_name must not be empty")


@dataclass(frozen=True, slots=True)
class AnalyzedDocument:
    document_key: str
    source_name: str
    kind: DocumentKind
    character_count: int
    checksum_sha256: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RequirementFinding:
    finding_id: str
    category: RequirementCategory
    title: str
    value: str
    severity: FindingSeverity
    confidence: float
    source_name: str
    snippet: str
    pattern_key: str

    def __post_init__(self) -> None:
        if not self.finding_id.strip():
            raise ValueError("finding_id must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class TenderRequirementAnalysis:
    analysis_id: str
    registry_key: str
    analyzed_at: str
    source_fingerprint: str
    documents: tuple[AnalyzedDocument, ...]
    findings: tuple[RequirementFinding, ...]
    missing_documents: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    @property
    def critical_count(self) -> int:
        return sum(finding.severity == FindingSeverity.CRITICAL for finding in self.findings)

    @property
    def warning_count(self) -> int:
        return sum(finding.severity == FindingSeverity.WARNING for finding in self.findings)

    @property
    def risk_level(self) -> AnalysisRiskLevel:
        if self.critical_count >= 2:
            return AnalysisRiskLevel.CRITICAL
        if self.critical_count == 1:
            return AnalysisRiskLevel.HIGH
        if self.warning_count >= 4:
            return AnalysisRiskLevel.HIGH
        if self.warning_count >= 1:
            return AnalysisRiskLevel.MEDIUM
        return AnalysisRiskLevel.LOW

    def findings_for(
        self,
        category: RequirementCategory,
    ) -> tuple[RequirementFinding, ...]:
        return tuple(finding for finding in self.findings if finding.category == category)

    @property
    def license_requirements(self) -> tuple[RequirementFinding, ...]:
        return self.findings_for(RequirementCategory.LICENSE)

    @property
    def experience_requirements(self) -> tuple[RequirementFinding, ...]:
        return self.findings_for(RequirementCategory.EXPERIENCE)

    @property
    def security_requirements(self) -> tuple[RequirementFinding, ...]:
        return self.findings_for(RequirementCategory.SECURITY)

    @property
    def deadlines(self) -> tuple[RequirementFinding, ...]:
        return self.findings_for(RequirementCategory.DEADLINE)

    @property
    def stop_factors(self) -> tuple[RequirementFinding, ...]:
        return self.findings_for(RequirementCategory.STOP_FACTOR)

    @property
    def contract_risks(self) -> tuple[RequirementFinding, ...]:
        categories = {
            RequirementCategory.PAYMENT,
            RequirementCategory.WARRANTY,
            RequirementCategory.PENALTY,
            RequirementCategory.CONTRACT,
        }
        return tuple(finding for finding in self.findings if finding.category in categories)


@dataclass(frozen=True, slots=True)
class _Rule:
    key: str
    category: RequirementCategory
    title: str
    pattern: re.Pattern[str]
    severity: FindingSeverity
    confidence: float


_RULES: tuple[_Rule, ...] = (
    _Rule(
        "license_mchs",
        RequirementCategory.LICENSE,
        "Лицензия МЧС",
        re.compile(
            r"(?:лицензи\w{0,12}\s+(?:мчс|на\s+"
            r"(?:осуществление\s+)?деятельност\w{0,8}\s+по\s+"
            r"монтаж\w{0,8}.*?пожарн\w{0,10})|"
            r"лицензи\w{0,12}.*?мчс)",
            re.IGNORECASE | re.DOTALL,
        ),
        FindingSeverity.WARNING,
        0.94,
    ),
    _Rule(
        "license_fsb",
        RequirementCategory.LICENSE,
        "Лицензия ФСБ",
        re.compile(
            r"лицензи\w{0,12}.*?фсб",
            re.IGNORECASE | re.DOTALL,
        ),
        FindingSeverity.CRITICAL,
        0.98,
    ),
    _Rule(
        "sro_membership",
        RequirementCategory.LICENSE,
        "Членство или допуск СРО",
        re.compile(
            r"(?:членств\w{0,8}\s+в\s+сро|"
            r"допуск\w{0,8}\s+сро|"
            r"выписк\w{0,8}\s+из\s+реестр\w{0,8}\s+сро)",
            re.IGNORECASE,
        ),
        FindingSeverity.WARNING,
        0.96,
    ),
    _Rule(
        "general_license",
        RequirementCategory.LICENSE,
        "Обязательная лицензия или разрешение",
        re.compile(
            r"(?:обязательн\w{0,8}|требу\w{0,8})"
            r".{0,90}(?:лицензи\w{0,12}|разрешени\w{0,10}|"
            r"допуск\w{0,8})",
            re.IGNORECASE | re.DOTALL,
        ),
        FindingSeverity.WARNING,
        0.88,
    ),
    _Rule(
        "experience_contracts",
        RequirementCategory.EXPERIENCE,
        "Требование к количеству исполненных контрактов",
        re.compile(
            r"(?:не\s+менее\s+)?\d{1,3}\s+"
            r"(?:исполненн\w{0,10}\s+)?"
            r"(?:контракт\w{0,8}|договор\w{0,8})",
            re.IGNORECASE,
        ),
        FindingSeverity.WARNING,
        0.88,
    ),
    _Rule(
        "experience_period",
        RequirementCategory.EXPERIENCE,
        "Подтверждение опыта за установленный период",
        re.compile(
            r"(?:опыт\w{0,10}.{0,120})?"
            r"за\s+последни\w{0,8}\s+\d{1,2}\s+"
            r"(?:год\w{0,6}|лет)",
            re.IGNORECASE | re.DOTALL,
        ),
        FindingSeverity.WARNING,
        0.86,
    ),
    _Rule(
        "experience_value",
        RequirementCategory.EXPERIENCE,
        "Минимальная стоимость подтверждённого опыта",
        re.compile(
            r"(?:стоимост\w{0,8}|цен\w{0,6})"
            r".{0,140}(?:не\s+менее|составля\w{0,10})"
            r".{0,40}(?:\d{1,3}(?:[.,]\d+)?\s*%|"
            r"\d[\d\s]*(?:[.,]\d+)?\s*(?:руб|₽))",
            re.IGNORECASE | re.DOTALL,
        ),
        FindingSeverity.WARNING,
        0.84,
    ),
    _Rule(
        "application_security",
        RequirementCategory.SECURITY,
        "Обеспечение заявки",
        re.compile(
            r"обеспечени\w{0,8}\s+(?:исполнения\s+)?заявк\w{0,8}"
            r".{0,120}",
            re.IGNORECASE | re.DOTALL,
        ),
        FindingSeverity.WARNING,
        0.95,
    ),
    _Rule(
        "contract_security",
        RequirementCategory.SECURITY,
        "Обеспечение исполнения контракта",
        re.compile(
            r"обеспечени\w{0,8}\s+исполнени\w{0,8}\s+"
            r"(?:контракт\w{0,8}|договор\w{0,8}).{0,140}",
            re.IGNORECASE | re.DOTALL,
        ),
        FindingSeverity.WARNING,
        0.97,
    ),
    _Rule(
        "warranty_security",
        RequirementCategory.SECURITY,
        "Обеспечение гарантийных обязательств",
        re.compile(
            r"обеспечени\w{0,8}\s+гарантийн\w{0,8}\s+"
            r"обязательств\w{0,8}.{0,120}",
            re.IGNORECASE | re.DOTALL,
        ),
        FindingSeverity.WARNING,
        0.96,
    ),
    _Rule(
        "execution_deadline",
        RequirementCategory.DEADLINE,
        "Срок выполнения работ или поставки",
        re.compile(
            r"срок\w{0,8}\s+"
            r"(?:выполнени\w{0,8}|поставк\w{0,8}|"
            r"оказани\w{0,8}|монтаж\w{0,8})"
            r".{0,160}?(?:\d{1,4}\s+"
            r"(?:календарн\w{0,8}|рабоч\w{0,8})?\s*"
            r"(?:дн\w{0,4}|месяц\w{0,8})|"
            r"\d{1,2}[./]\d{1,2}[./]\d{2,4})",
            re.IGNORECASE | re.DOTALL,
        ),
        FindingSeverity.INFO,
        0.90,
    ),
    _Rule(
        "payment_term",
        RequirementCategory.PAYMENT,
        "Срок оплаты",
        re.compile(
            r"оплат\w{0,8}.{0,160}?"
            r"(?:в\s+течени\w{0,8}\s+)?\d{1,3}\s+"
            r"(?:рабоч\w{0,8}|календарн\w{0,8})?\s*дн\w{0,4}",
            re.IGNORECASE | re.DOTALL,
        ),
        FindingSeverity.INFO,
        0.90,
    ),
    _Rule(
        "warranty_term",
        RequirementCategory.WARRANTY,
        "Гарантийный срок",
        re.compile(
            r"гарантийн\w{0,8}\s+срок.{0,120}?"
            r"\d{1,4}\s+(?:дн\w{0,4}|месяц\w{0,8}|год\w{0,6})",
            re.IGNORECASE | re.DOTALL,
        ),
        FindingSeverity.INFO,
        0.92,
    ),
    _Rule(
        "penalty",
        RequirementCategory.PENALTY,
        "Штрафы, пени или неустойка",
        re.compile(
            r"(?:штраф\w{0,8}|пен\w{0,6}|неустойк\w{0,8})"
            r".{0,120}",
            re.IGNORECASE | re.DOTALL,
        ),
        FindingSeverity.WARNING,
        0.82,
    ),
    _Rule(
        "unilateral_refusal",
        RequirementCategory.CONTRACT,
        "Односторонний отказ от исполнения",
        re.compile(
            r"односторонн\w{0,10}\s+отказ\w{0,8}"
            r".{0,120}",
            re.IGNORECASE | re.DOTALL,
        ),
        FindingSeverity.WARNING,
        0.90,
    ),
    _Rule(
        "state_secret",
        RequirementCategory.STOP_FACTOR,
        "Работы связаны с государственной тайной",
        re.compile(
            r"(?:государственн\w{0,10}\s+тайн\w{0,8}|"
            r"сведени\w{0,10},?\s+составля\w{0,10}\s+"
            r"государственн\w{0,10}\s+тайн\w{0,8})",
            re.IGNORECASE,
        ),
        FindingSeverity.CRITICAL,
        0.99,
    ),
    _Rule(
        "dangerous_facility",
        RequirementCategory.STOP_FACTOR,
        "Особо опасный или технически сложный объект",
        re.compile(
            r"(?:особо\s+опасн\w{0,10}|"
            r"технически\s+сложн\w{0,10}|"
            r"уникальн\w{0,8})\s+объект\w{0,8}",
            re.IGNORECASE,
        ),
        FindingSeverity.CRITICAL,
        0.93,
    ),
    _Rule(
        "mandatory_mchs",
        RequirementCategory.STOP_FACTOR,
        "Обязательное наличие лицензии МЧС",
        re.compile(
            r"(?:обязательн\w{0,8}|должен|требу\w{0,8})"
            r".{0,100}лицензи\w{0,12}.{0,60}мчс",
            re.IGNORECASE | re.DOTALL,
        ),
        FindingSeverity.CRITICAL,
        0.96,
    ),
    _Rule(
        "mandatory_sro",
        RequirementCategory.STOP_FACTOR,
        "Обязательное членство в СРО",
        re.compile(
            r"(?:обязательн\w{0,8}|должен|требу\w{0,8})"
            r".{0,100}(?:членств\w{0,8}\s+в\s+сро|"
            r"допуск\w{0,8}\s+сро)",
            re.IGNORECASE | re.DOTALL,
        ),
        FindingSeverity.CRITICAL,
        0.95,
    ),
)


class TenderRequirementsAnalyzer:
    """Extract structured requirements with evidence and source snippets."""

    def __init__(
        self,
        *,
        snippet_radius: int = 180,
        max_findings_per_rule: int = 20,
    ) -> None:
        if snippet_radius < 40:
            raise ValueError("snippet_radius must be at least 40")
        if max_findings_per_rule < 1:
            raise ValueError("max_findings_per_rule must be positive")
        self.snippet_radius = int(snippet_radius)
        self.max_findings_per_rule = int(max_findings_per_rule)

    def analyze(
        self,
        registry_key: str,
        sources: Iterable[TenderAnalysisSource],
    ) -> TenderRequirementAnalysis:
        normalized_registry_key = registry_key.strip()
        if not normalized_registry_key:
            raise ValueError("registry_key must not be empty")

        source_items = tuple(sources)
        analyzed_documents: list[AnalyzedDocument] = []
        findings: list[RequirementFinding] = []
        warnings: list[str] = []

        for source in source_items:
            normalized_text = _normalize_text(source.text)
            kind = self.classify_document(
                source.source_name,
                normalized_text,
            )
            analyzed_documents.append(
                AnalyzedDocument(
                    document_key=source.document_key,
                    source_name=source.source_name,
                    kind=kind,
                    character_count=len(normalized_text),
                    checksum_sha256=(
                        source.checksum_sha256
                        or hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
                    ),
                )
            )

            if not normalized_text:
                warnings.append(f"{source.source_name}: извлечённый текст пуст.")
                continue

            findings.extend(
                self._analyze_source(
                    source.source_name,
                    normalized_text,
                )
            )

        deduplicated = _deduplicate_findings(findings)
        kinds = {document.kind for document in analyzed_documents}
        missing_documents = _missing_document_labels(kinds)

        if not analyzed_documents:
            warnings.append("Нет извлечённых документов для анализа.")
        elif all(document.character_count == 0 for document in analyzed_documents):
            warnings.append("Во всех документах отсутствует извлечённый текст.")

        fingerprint = _analysis_fingerprint(
            normalized_registry_key,
            analyzed_documents,
        )
        return TenderRequirementAnalysis(
            analysis_id=uuid4().hex,
            registry_key=normalized_registry_key,
            analyzed_at=_utc_now(),
            source_fingerprint=fingerprint,
            documents=tuple(analyzed_documents),
            findings=tuple(deduplicated),
            missing_documents=missing_documents,
            warnings=tuple(_ordered_unique(warnings)),
        )

    def classify_document(
        self,
        source_name: str,
        text: str,
    ) -> DocumentKind:
        return classify_document_kind(source_name, text)

    def _analyze_source(
        self,
        source_name: str,
        text: str,
    ) -> list[RequirementFinding]:
        findings: list[RequirementFinding] = []

        for rule in _RULES:
            matches = list(rule.pattern.finditer(text))[: self.max_findings_per_rule]
            for match in matches:
                snippet = _snippet(
                    text,
                    match.start(),
                    match.end(),
                    radius=self.snippet_radius,
                )
                value = _finding_value(
                    match.group(0),
                    category=rule.category,
                )
                finding_id = hashlib.sha256(
                    (
                        f"{rule.key}|{source_name}|"
                        f"{_normalize_text(value)}|"
                        f"{_normalize_text(snippet)}"
                    ).encode("utf-8")
                ).hexdigest()[:24]
                findings.append(
                    RequirementFinding(
                        finding_id=finding_id,
                        category=rule.category,
                        title=rule.title,
                        value=value,
                        severity=rule.severity,
                        confidence=rule.confidence,
                        source_name=source_name,
                        snippet=snippet,
                        pattern_key=rule.key,
                    )
                )

        return findings


class TenderAnalysisRepository:
    """Persist versioned analysis results in SQLite."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tender_analysis_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tender_analysis_records (
                    analysis_id TEXT PRIMARY KEY,
                    registry_key TEXT NOT NULL,
                    source_fingerprint TEXT NOT NULL,
                    analyzed_at TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    critical_count INTEGER NOT NULL,
                    warning_count INTEGER NOT NULL,
                    document_count INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(registry_key, source_fingerprint)
                );

                CREATE INDEX IF NOT EXISTS idx_tender_analysis_registry
                    ON tender_analysis_records(
                        registry_key,
                        analyzed_at DESC
                    );
                """
            )
            connection.execute(
                """
                INSERT INTO tender_analysis_meta(key, value)
                VALUES('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (str(self.SCHEMA_VERSION),),
            )

    def save(
        self,
        analysis: TenderRequirementAnalysis,
    ) -> TenderRequirementAnalysis:
        self.initialize()
        payload = json.dumps(
            _analysis_to_payload(analysis),
            ensure_ascii=False,
            separators=(",", ":"),
        )

        with self._lock, self._connect() as connection:
            existing = connection.execute(
                """
                SELECT payload_json
                FROM tender_analysis_records
                WHERE registry_key = ?
                  AND source_fingerprint = ?
                LIMIT 1
                """,
                (
                    analysis.registry_key,
                    analysis.source_fingerprint,
                ),
            ).fetchone()
            if existing is not None:
                return _analysis_from_payload(json.loads(str(existing["payload_json"])))

            connection.execute(
                """
                INSERT INTO tender_analysis_records(
                    analysis_id,
                    registry_key,
                    source_fingerprint,
                    analyzed_at,
                    risk_level,
                    critical_count,
                    warning_count,
                    document_count,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis.analysis_id,
                    analysis.registry_key,
                    analysis.source_fingerprint,
                    analysis.analyzed_at,
                    analysis.risk_level.value,
                    analysis.critical_count,
                    analysis.warning_count,
                    len(analysis.documents),
                    payload,
                ),
            )
        return analysis

    def get_latest(
        self,
        registry_key: str,
    ) -> TenderRequirementAnalysis | None:
        self.initialize()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM tender_analysis_records
                WHERE registry_key = ?
                ORDER BY analyzed_at DESC
                LIMIT 1
                """,
                (registry_key.strip(),),
            ).fetchone()
        if row is None:
            return None
        return _analysis_from_payload(json.loads(str(row["payload_json"])))

    def list_history(
        self,
        registry_key: str,
        *,
        limit: int = 20,
    ) -> tuple[TenderRequirementAnalysis, ...]:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        self.initialize()
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json
                FROM tender_analysis_records
                WHERE registry_key = ?
                ORDER BY analyzed_at DESC
                LIMIT ?
                """,
                (registry_key.strip(), int(limit)),
            ).fetchall()
        return tuple(_analysis_from_payload(json.loads(str(row["payload_json"]))) for row in rows)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=10.0,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection


class TenderRequirementAnalysisService:
    """Analyze the latest locally extracted text for one tender."""

    def __init__(
        self,
        text_service: TenderDocumentTextService,
        repository: TenderAnalysisRepository,
        *,
        analyzer: TenderRequirementsAnalyzer | None = None,
    ) -> None:
        self.text_service = text_service
        self.repository = repository
        self.analyzer = analyzer or TenderRequirementsAnalyzer()

    def analyze(
        self,
        registry_key: str,
        *,
        force_extraction: bool = False,
        persist: bool = True,
    ) -> TenderRequirementAnalysis:
        normalized_key = registry_key.strip()
        if not normalized_key:
            raise ValueError("registry_key must not be empty")

        results = self.text_service.list_results(normalized_key)
        if force_extraction or not results:
            self.text_service.extract_tender(
                normalized_key,
                force=force_extraction,
            )
            results = self.text_service.list_results(normalized_key)

        latest_by_document: dict[str, StoredDocumentText] = {}
        for result in results:
            if result.document_key not in latest_by_document:
                latest_by_document[result.document_key] = result

        sources: list[TenderAnalysisSource] = []
        for result in latest_by_document.values():
            if not result.available_locally:
                continue
            text = self.text_service.read_text(result)
            source_name = (
                result.source_path.name
                if result.source_path is not None
                else (
                    result.text_path.name if result.text_path is not None else result.document_key
                )
            )
            sources.append(
                TenderAnalysisSource(
                    document_key=result.document_key,
                    source_name=source_name,
                    text=text,
                    checksum_sha256=result.checksum_sha256,
                )
            )

        analysis = self.analyzer.analyze(
            normalized_key,
            sources,
        )
        if persist:
            return self.repository.save(analysis)
        return analysis

    def latest(
        self,
        registry_key: str,
    ) -> TenderRequirementAnalysis | None:
        return self.repository.get_latest(registry_key)


def _normalize_text(value: str) -> str:
    value = value.casefold().replace("ё", "е")
    value = value.replace("\u00a0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    return f" {phrase} " in f" {text} "


def _snippet(
    text: str,
    start: int,
    end: int,
    *,
    radius: int,
) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    snippet = text[left:right].replace("\n", " ")
    snippet = re.sub(r"\s+", " ", snippet).strip()
    if left > 0:
        snippet = "… " + snippet
    if right < len(text):
        snippet = snippet + " …"
    return snippet


def _finding_value(
    matched_text: str,
    *,
    category: RequirementCategory,
) -> str:
    normalized = re.sub(r"\s+", " ", matched_text).strip()
    values: list[str] = []

    percent_values = re.findall(
        r"\d{1,3}(?:[.,]\d+)?\s*%",
        normalized,
    )
    money_values = re.findall(
        r"\d[\d\s]*(?:[.,]\d+)?\s*(?:руб(?:лей|ля|ль)?|₽)",
        normalized,
        flags=re.IGNORECASE,
    )
    duration_values = re.findall(
        r"\d{1,4}\s+"
        r"(?:календарн\w*|рабоч\w*)?\s*"
        r"(?:дн\w*|месяц\w*|год\w*|лет)",
        normalized,
        flags=re.IGNORECASE,
    )
    date_values = re.findall(
        r"\d{1,2}[./]\d{1,2}[./]\d{2,4}",
        normalized,
    )

    if category in {
        RequirementCategory.SECURITY,
        RequirementCategory.EXPERIENCE,
    }:
        values.extend(percent_values)
        values.extend(money_values)
    if category in {
        RequirementCategory.DEADLINE,
        RequirementCategory.PAYMENT,
        RequirementCategory.WARRANTY,
        RequirementCategory.EXPERIENCE,
    }:
        values.extend(duration_values)
        values.extend(date_values)

    unique = _ordered_unique(values)
    if unique:
        return "; ".join(unique)
    return normalized[:260]


def _deduplicate_findings(
    findings: Iterable[RequirementFinding],
) -> list[RequirementFinding]:
    result: list[RequirementFinding] = []
    seen: set[tuple[str, str, str]] = set()

    for finding in sorted(
        findings,
        key=lambda item: (
            -_severity_rank(item.severity),
            item.category.value,
            item.source_name.casefold(),
            item.finding_id,
        ),
    ):
        identity = (
            finding.pattern_key,
            _normalize_text(finding.value),
            finding.source_name.casefold(),
        )
        if identity in seen:
            continue
        seen.add(identity)
        result.append(finding)
    return result


def _severity_rank(severity: FindingSeverity) -> int:
    return {
        FindingSeverity.INFO: 1,
        FindingSeverity.WARNING: 2,
        FindingSeverity.CRITICAL: 3,
    }[severity]


def _missing_document_labels(
    kinds: set[DocumentKind],
) -> tuple[str, ...]:
    missing: list[str] = []
    if DocumentKind.TECHNICAL_SPECIFICATION not in kinds:
        missing.append("Техническое задание / описание объекта закупки")
    if DocumentKind.DRAFT_CONTRACT not in kinds:
        missing.append("Проект контракта / договора")
    return tuple(missing)


def _analysis_fingerprint(
    registry_key: str,
    documents: Sequence[AnalyzedDocument],
) -> str:
    rendered = "|".join(
        (
            registry_key,
            *(
                f"{document.document_key}:{document.checksum_sha256}:{document.character_count}"
                for document in sorted(
                    documents,
                    key=lambda item: item.document_key,
                )
            ),
        )
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _analysis_to_payload(
    analysis: TenderRequirementAnalysis,
) -> dict[str, object]:
    return {
        "analysis_id": analysis.analysis_id,
        "registry_key": analysis.registry_key,
        "analyzed_at": analysis.analyzed_at,
        "source_fingerprint": analysis.source_fingerprint,
        "documents": [
            {
                "document_key": item.document_key,
                "source_name": item.source_name,
                "kind": item.kind.value,
                "character_count": item.character_count,
                "checksum_sha256": item.checksum_sha256,
                "warnings": list(item.warnings),
            }
            for item in analysis.documents
        ],
        "findings": [
            {
                "finding_id": item.finding_id,
                "category": item.category.value,
                "title": item.title,
                "value": item.value,
                "severity": item.severity.value,
                "confidence": item.confidence,
                "source_name": item.source_name,
                "snippet": item.snippet,
                "pattern_key": item.pattern_key,
            }
            for item in analysis.findings
        ],
        "missing_documents": list(analysis.missing_documents),
        "warnings": list(analysis.warnings),
    }


def _analysis_from_payload(
    payload: dict[str, object],
) -> TenderRequirementAnalysis:
    return TenderRequirementAnalysis(
        analysis_id=str(payload.get("analysis_id", "")),
        registry_key=str(payload.get("registry_key", "")),
        analyzed_at=str(payload.get("analyzed_at", "")),
        source_fingerprint=str(payload.get("source_fingerprint", "")),
        documents=tuple(
            AnalyzedDocument(
                document_key=str(item.get("document_key", "")),
                source_name=str(item.get("source_name", "")),
                kind=DocumentKind(str(item.get("kind", "other"))),
                character_count=int(item.get("character_count", 0)),
                checksum_sha256=str(item.get("checksum_sha256", "")),
                warnings=tuple(str(value) for value in item.get("warnings", [])),
            )
            for item in payload.get("documents", [])
            if isinstance(item, dict)
        ),
        findings=tuple(
            RequirementFinding(
                finding_id=str(item.get("finding_id", "")),
                category=RequirementCategory(str(item.get("category", "technical"))),
                title=str(item.get("title", "")),
                value=str(item.get("value", "")),
                severity=FindingSeverity(str(item.get("severity", "info"))),
                confidence=float(item.get("confidence", 0.0)),
                source_name=str(item.get("source_name", "")),
                snippet=str(item.get("snippet", "")),
                pattern_key=str(item.get("pattern_key", "")),
            )
            for item in payload.get("findings", [])
            if isinstance(item, dict)
        ),
        missing_documents=tuple(str(value) for value in payload.get("missing_documents", [])),
        warnings=tuple(str(value) for value in payload.get("warnings", [])),
    )


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        identity = normalized.casefold()
        if not normalized or identity in seen:
            continue
        seen.add(identity)
        result.append(normalized)
    return tuple(result)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "AnalysisRiskLevel",
    "AnalyzedDocument",
    "DocumentKind",
    "classify_document_kind",
    "FindingSeverity",
    "RequirementCategory",
    "RequirementFinding",
    "TenderAnalysisRepository",
    "TenderAnalysisSource",
    "TenderRequirementAnalysis",
    "TenderRequirementAnalysisService",
    "TenderRequirementsAnalyzer",
]
