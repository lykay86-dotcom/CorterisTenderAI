"""C18 evidence-backed commercial estimator without invented prices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Mapping
from uuid import uuid4


class CommercialEstimateStatus(StrEnum):
    COMPLETE = "complete"
    DATA_INSUFFICIENT = "data_insufficient"


class CommercialCostCategory(StrEnum):
    EQUIPMENT = "equipment"
    INSTALLATION = "installation"
    LOGISTICS = "logistics"
    TRAVEL = "travel"
    WARRANTY = "warranty"
    SUBCONTRACT = "subcontract"
    WORKING_CAPITAL = "working_capital"
    BANK_GUARANTEE = "bank_guarantee"


REQUIRED_COST_CATEGORIES = tuple(CommercialCostCategory)


@dataclass(frozen=True, slots=True)
class CommercialEvidence:
    source: str
    document: str = ""
    page: str = ""
    quote: str = ""
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("evidence source must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    def to_payload(self) -> dict[str, object]:
        return {
            "source": self.source,
            "document": self.document,
            "page": self.page,
            "quote": self.quote,
            "confidence": self.confidence,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "CommercialEvidence":
        return cls(
            source=str(payload.get("source", "")),
            document=str(payload.get("document", "")),
            page=str(payload.get("page", "")),
            quote=str(payload.get("quote", "")),
            confidence=float(payload.get("confidence", 0.0)),
        )


@dataclass(frozen=True, slots=True)
class CommercialCostLine:
    line_id: str
    category: CommercialCostCategory
    description: str
    quantity: Decimal
    unit_cost: Decimal | None
    evidence: CommercialEvidence | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "quantity", _decimal(self.quantity, "quantity"))
        object.__setattr__(self, "unit_cost", _optional_decimal(self.unit_cost, "unit_cost"))
        if not self.line_id.strip() or not self.description.strip():
            raise ValueError("line_id and description must not be empty")
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        if self.unit_cost is not None and self.evidence is None:
            raise ValueError("priced cost line requires evidence")

    @property
    def total(self) -> Decimal | None:
        if self.unit_cost is None:
            return None
        return (self.quantity * self.unit_cost).quantize(Decimal("0.01"))

    def to_payload(self) -> dict[str, object]:
        return {
            "line_id": self.line_id,
            "category": self.category.value,
            "description": self.description,
            "quantity": str(self.quantity),
            "unit_cost": str(self.unit_cost) if self.unit_cost is not None else None,
            "evidence": self.evidence.to_payload() if self.evidence else None,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "CommercialCostLine":
        raw_evidence = payload.get("evidence")
        return cls(
            line_id=str(payload.get("line_id", "")),
            category=CommercialCostCategory(str(payload.get("category", ""))),
            description=str(payload.get("description", "")),
            quantity=Decimal(str(payload.get("quantity", "0"))),
            unit_cost=(
                Decimal(str(payload["unit_cost"])) if payload.get("unit_cost") is not None else None
            ),
            evidence=(
                CommercialEvidence.from_payload(raw_evidence)
                if isinstance(raw_evidence, Mapping)
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class CommercialEstimateDraft:
    registry_key: str
    currency: str = "RUB"
    lines: tuple[CommercialCostLine, ...] = ()
    confirmed_zero_categories: tuple[CommercialCostCategory, ...] = ()
    confirmed_zero_evidence: tuple[tuple[CommercialCostCategory, CommercialEvidence], ...] = ()
    proposed_revenue: Decimal | None = None
    revenue_evidence: CommercialEvidence | None = None
    advance_percent: Decimal | None = None
    payment_delay_days: int | None = None
    payment_evidence: CommercialEvidence | None = None
    target_margin_percent: Decimal | None = None
    note: str = ""

    def __post_init__(self) -> None:
        normalized_currency = self.currency.strip().upper()
        if normalized_currency != "RUB":
            raise ValueError("C18 currently accepts only explicitly entered RUB costs")
        object.__setattr__(self, "currency", normalized_currency)
        object.__setattr__(self, "lines", tuple(self.lines))
        object.__setattr__(
            self,
            "confirmed_zero_categories",
            tuple(dict.fromkeys(self.confirmed_zero_categories)),
        )
        object.__setattr__(self, "confirmed_zero_evidence", tuple(self.confirmed_zero_evidence))
        evidenced_zeroes = {category for category, _evidence in self.confirmed_zero_evidence}
        if any(category not in evidenced_zeroes for category in self.confirmed_zero_categories):
            raise ValueError("every confirmed zero category requires evidence")
        object.__setattr__(
            self, "proposed_revenue", _optional_decimal(self.proposed_revenue, "proposed_revenue")
        )
        object.__setattr__(
            self, "advance_percent", _optional_percent(self.advance_percent, "advance_percent")
        )
        object.__setattr__(
            self,
            "target_margin_percent",
            _optional_percent(self.target_margin_percent, "target_margin_percent"),
        )
        if not self.registry_key.strip():
            raise ValueError("registry_key must not be empty")
        if self.proposed_revenue is not None and self.revenue_evidence is None:
            raise ValueError("proposed revenue requires evidence")
        if (
            self.advance_percent is not None or self.payment_delay_days is not None
        ) and self.payment_evidence is None:
            raise ValueError("payment terms require evidence")
        if self.payment_delay_days is not None and self.payment_delay_days < 0:
            raise ValueError("payment_delay_days must be non-negative")

    def to_payload(self) -> dict[str, object]:
        return {
            "registry_key": self.registry_key,
            "currency": self.currency,
            "lines": [item.to_payload() for item in self.lines],
            "confirmed_zero_categories": [item.value for item in self.confirmed_zero_categories],
            "confirmed_zero_evidence": [
                [category.value, evidence.to_payload()]
                for category, evidence in self.confirmed_zero_evidence
            ],
            "proposed_revenue": str(self.proposed_revenue)
            if self.proposed_revenue is not None
            else None,
            "revenue_evidence": self.revenue_evidence.to_payload()
            if self.revenue_evidence
            else None,
            "advance_percent": str(self.advance_percent)
            if self.advance_percent is not None
            else None,
            "payment_delay_days": self.payment_delay_days,
            "payment_evidence": self.payment_evidence.to_payload()
            if self.payment_evidence
            else None,
            "target_margin_percent": str(self.target_margin_percent)
            if self.target_margin_percent is not None
            else None,
            "note": self.note,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "CommercialEstimateDraft":
        raw_lines = payload.get("lines", ())
        return cls(
            registry_key=str(payload.get("registry_key", "")),
            currency=str(payload.get("currency", "RUB")),
            lines=tuple(
                CommercialCostLine.from_payload(item)
                for item in raw_lines
                if isinstance(item, Mapping)
            )
            if isinstance(raw_lines, (list, tuple))
            else (),
            confirmed_zero_categories=tuple(
                CommercialCostCategory(str(item))
                for item in payload.get("confirmed_zero_categories", ())
            ),
            confirmed_zero_evidence=tuple(
                (
                    CommercialCostCategory(str(item[0])),
                    CommercialEvidence.from_payload(item[1]),
                )
                for item in payload.get("confirmed_zero_evidence", ())
                if isinstance(item, (list, tuple))
                and len(item) == 2
                and isinstance(item[1], Mapping)
            ),
            proposed_revenue=_payload_decimal(payload.get("proposed_revenue")),
            revenue_evidence=_payload_evidence(payload.get("revenue_evidence")),
            advance_percent=_payload_decimal(payload.get("advance_percent")),
            payment_delay_days=(
                int(payload["payment_delay_days"])
                if payload.get("payment_delay_days") is not None
                else None
            ),
            payment_evidence=_payload_evidence(payload.get("payment_evidence")),
            target_margin_percent=_payload_decimal(payload.get("target_margin_percent")),
            note=str(payload.get("note", "")),
        )


@dataclass(frozen=True, slots=True)
class CommercialEstimateResult:
    estimate_id: str
    registry_key: str
    status: CommercialEstimateStatus
    currency: str
    known_cost: Decimal
    total_cost: Decimal | None
    proposed_revenue: Decimal | None
    profit: Decimal | None
    margin_percent: Decimal | None
    advance_amount: Decimal | None
    financing_exposure: Decimal | None
    category_totals: tuple[tuple[CommercialCostCategory, Decimal], ...]
    missing_data: tuple[str, ...]
    warnings: tuple[str, ...]
    calculated_at: str
    input_fingerprint: str


class CommercialEstimator:
    def calculate(self, draft: CommercialEstimateDraft) -> CommercialEstimateResult:
        totals = {category: Decimal("0") for category in REQUIRED_COST_CATEGORIES}
        missing: list[str] = []
        categories_with_lines: set[CommercialCostCategory] = set()
        for line in draft.lines:
            categories_with_lines.add(line.category)
            if line.total is None:
                missing.append(f"Цена: {line.description}")
            else:
                totals[line.category] += line.total
        accounted = categories_with_lines | set(draft.confirmed_zero_categories)
        for category in REQUIRED_COST_CATEGORIES:
            if category not in accounted:
                missing.append(f"Категория: {_category_label(category)}")
        if draft.proposed_revenue is None:
            missing.append("Предложенная цена/выручка")
        if draft.advance_percent is None:
            missing.append("Размер аванса")
        if draft.payment_delay_days is None:
            missing.append("Срок оплаты")

        known_cost = sum(totals.values(), Decimal("0")).quantize(Decimal("0.01"))
        complete = not missing
        total_cost = known_cost if complete else None
        profit = None
        margin = None
        advance_amount = None
        exposure = None
        warnings: list[str] = []
        if draft.proposed_revenue is not None and draft.advance_percent is not None:
            advance_amount = (
                draft.proposed_revenue * draft.advance_percent / Decimal("100")
            ).quantize(Decimal("0.01"))
            exposure = max(Decimal("0"), known_cost - advance_amount).quantize(Decimal("0.01"))
        if complete and draft.proposed_revenue is not None:
            profit = (draft.proposed_revenue - known_cost).quantize(Decimal("0.01"))
            if draft.proposed_revenue > 0:
                margin = (profit / draft.proposed_revenue * Decimal("100")).quantize(
                    Decimal("0.01")
                )
            if (
                draft.target_margin_percent is not None
                and margin is not None
                and margin < draft.target_margin_percent
            ):
                warnings.append(f"Маржа {margin}% ниже целевой {draft.target_margin_percent}%.")
            if profit < 0:
                warnings.append("Расчёт показывает отрицательную прибыль.")

        payload = draft.to_payload()
        fingerprint_payload = dict(payload)
        fingerprint_payload["lines"] = sorted(
            (
                {key: value for key, value in line.items() if key != "line_id"}
                for line in payload["lines"]
            ),
            key=lambda item: (str(item["category"]), str(item["description"])),
        )
        fingerprint = hashlib.sha256(
            json.dumps(
                fingerprint_payload,
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return CommercialEstimateResult(
            estimate_id=uuid4().hex,
            registry_key=draft.registry_key,
            status=(
                CommercialEstimateStatus.COMPLETE
                if complete
                else CommercialEstimateStatus.DATA_INSUFFICIENT
            ),
            currency=draft.currency,
            known_cost=known_cost,
            total_cost=total_cost,
            proposed_revenue=draft.proposed_revenue,
            profit=profit,
            margin_percent=margin,
            advance_amount=advance_amount,
            financing_exposure=exposure,
            category_totals=tuple(
                (category, totals[category]) for category in REQUIRED_COST_CATEGORIES
            ),
            missing_data=tuple(dict.fromkeys(missing)),
            warnings=tuple(warnings),
            calculated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            input_fingerprint=fingerprint,
        )


class CommercialEstimateRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._lock = RLock()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS collector_commercial_estimates (
                    estimate_id TEXT PRIMARY KEY,
                    registry_key TEXT NOT NULL,
                    status TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    known_cost TEXT NOT NULL,
                    total_cost TEXT,
                    proposed_revenue TEXT,
                    profit TEXT,
                    margin_percent TEXT,
                    calculated_at TEXT NOT NULL,
                    input_fingerprint TEXT NOT NULL,
                    draft_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    UNIQUE(registry_key, input_fingerprint),
                    FOREIGN KEY(registry_key) REFERENCES tender_records(registry_key) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_commercial_estimates_registry
                    ON collector_commercial_estimates(registry_key, calculated_at DESC);
                CREATE TABLE IF NOT EXISTS collector_commercial_cost_lines (
                    estimate_id TEXT NOT NULL,
                    line_id TEXT NOT NULL,
                    registry_key TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    unit_cost TEXT,
                    total TEXT,
                    evidence_json TEXT,
                    PRIMARY KEY(estimate_id, line_id),
                    FOREIGN KEY(estimate_id) REFERENCES collector_commercial_estimates(estimate_id) ON DELETE CASCADE
                );
            """)

    def save(
        self, draft: CommercialEstimateDraft, result: CommercialEstimateResult
    ) -> CommercialEstimateResult:
        if draft.registry_key != result.registry_key:
            raise ValueError("draft and result registry keys differ")
        self.initialize()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                existing = connection.execute(
                    "SELECT estimate_id FROM collector_commercial_estimates WHERE registry_key=? AND input_fingerprint=?",
                    (result.registry_key, result.input_fingerprint),
                ).fetchone()
                estimate_id = str(existing["estimate_id"]) if existing else result.estimate_id
                stored_result = (
                    result
                    if estimate_id == result.estimate_id
                    else _replace_estimate_id(result, estimate_id)
                )
                connection.execute(
                    """INSERT INTO collector_commercial_estimates(
                        estimate_id, registry_key, status, currency, known_cost,
                        total_cost, proposed_revenue, profit, margin_percent,
                        calculated_at, input_fingerprint, draft_json, result_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(registry_key, input_fingerprint) DO UPDATE SET
                        status=excluded.status, known_cost=excluded.known_cost,
                        total_cost=excluded.total_cost, proposed_revenue=excluded.proposed_revenue,
                        profit=excluded.profit, margin_percent=excluded.margin_percent,
                        calculated_at=excluded.calculated_at, draft_json=excluded.draft_json,
                        result_json=excluded.result_json""",
                    (
                        estimate_id,
                        result.registry_key,
                        result.status.value,
                        result.currency,
                        str(result.known_cost),
                        _string_decimal(result.total_cost),
                        _string_decimal(result.proposed_revenue),
                        _string_decimal(result.profit),
                        _string_decimal(result.margin_percent),
                        result.calculated_at,
                        result.input_fingerprint,
                        json.dumps(draft.to_payload(), ensure_ascii=False, sort_keys=True),
                        json.dumps(
                            _result_payload(stored_result), ensure_ascii=False, sort_keys=True
                        ),
                    ),
                )
                connection.execute(
                    "DELETE FROM collector_commercial_cost_lines WHERE estimate_id=?",
                    (estimate_id,),
                )
                for line in draft.lines:
                    connection.execute(
                        "INSERT INTO collector_commercial_cost_lines VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            estimate_id,
                            line.line_id,
                            result.registry_key,
                            line.category.value,
                            line.description,
                            str(line.quantity),
                            _string_decimal(line.unit_cost),
                            _string_decimal(line.total),
                            json.dumps(line.evidence.to_payload(), ensure_ascii=False)
                            if line.evidence
                            else None,
                        ),
                    )
                connection.execute("COMMIT")
                return stored_result
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def latest(
        self, registry_key: str
    ) -> tuple[CommercialEstimateDraft, CommercialEstimateResult] | None:
        self.initialize()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT draft_json, result_json FROM collector_commercial_estimates WHERE registry_key=? ORDER BY calculated_at DESC, rowid DESC LIMIT 1",
                (registry_key.strip(),),
            ).fetchone()
        if row is None:
            return None
        return (
            CommercialEstimateDraft.from_payload(json.loads(str(row["draft_json"]))),
            _result_from_payload(json.loads(str(row["result_json"]))),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _decimal(value: object, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value).replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(f"{field} must be decimal") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"{field} must be finite and non-negative")
    return parsed


def _optional_decimal(value: object, field: str) -> Decimal | None:
    return None if value in (None, "") else _decimal(value, field)


def _optional_percent(value: object, field: str) -> Decimal | None:
    parsed = _optional_decimal(value, field)
    if parsed is not None and parsed > 100:
        raise ValueError(f"{field} cannot exceed 100")
    return parsed


def _payload_decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _payload_evidence(value: object) -> CommercialEvidence | None:
    return CommercialEvidence.from_payload(value) if isinstance(value, Mapping) else None


def _string_decimal(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _category_label(category: CommercialCostCategory) -> str:
    return {
        CommercialCostCategory.EQUIPMENT: "оборудование",
        CommercialCostCategory.INSTALLATION: "монтаж",
        CommercialCostCategory.LOGISTICS: "логистика",
        CommercialCostCategory.TRAVEL: "командировки",
        CommercialCostCategory.WARRANTY: "гарантия",
        CommercialCostCategory.SUBCONTRACT: "субподряд",
        CommercialCostCategory.WORKING_CAPITAL: "оборотный капитал",
        CommercialCostCategory.BANK_GUARANTEE: "банковская гарантия",
    }[category]


def _result_payload(result: CommercialEstimateResult) -> dict[str, object]:
    return {
        "estimate_id": result.estimate_id,
        "registry_key": result.registry_key,
        "status": result.status.value,
        "currency": result.currency,
        "known_cost": str(result.known_cost),
        "total_cost": _string_decimal(result.total_cost),
        "proposed_revenue": _string_decimal(result.proposed_revenue),
        "profit": _string_decimal(result.profit),
        "margin_percent": _string_decimal(result.margin_percent),
        "advance_amount": _string_decimal(result.advance_amount),
        "financing_exposure": _string_decimal(result.financing_exposure),
        "category_totals": [[key.value, str(value)] for key, value in result.category_totals],
        "missing_data": list(result.missing_data),
        "warnings": list(result.warnings),
        "calculated_at": result.calculated_at,
        "input_fingerprint": result.input_fingerprint,
    }


def _result_from_payload(payload: Mapping[str, object]) -> CommercialEstimateResult:
    return CommercialEstimateResult(
        estimate_id=str(payload["estimate_id"]),
        registry_key=str(payload["registry_key"]),
        status=CommercialEstimateStatus(str(payload["status"])),
        currency=str(payload["currency"]),
        known_cost=Decimal(str(payload["known_cost"])),
        total_cost=_payload_decimal(payload.get("total_cost")),
        proposed_revenue=_payload_decimal(payload.get("proposed_revenue")),
        profit=_payload_decimal(payload.get("profit")),
        margin_percent=_payload_decimal(payload.get("margin_percent")),
        advance_amount=_payload_decimal(payload.get("advance_amount")),
        financing_exposure=_payload_decimal(payload.get("financing_exposure")),
        category_totals=tuple(
            (CommercialCostCategory(str(key)), Decimal(str(value)))
            for key, value in payload["category_totals"]
        ),
        missing_data=tuple(str(item) for item in payload.get("missing_data", ())),
        warnings=tuple(str(item) for item in payload.get("warnings", ())),
        calculated_at=str(payload["calculated_at"]),
        input_fingerprint=str(payload["input_fingerprint"]),
    )


def _replace_estimate_id(
    result: CommercialEstimateResult, estimate_id: str
) -> CommercialEstimateResult:
    return CommercialEstimateResult(
        estimate_id=estimate_id,
        registry_key=result.registry_key,
        status=result.status,
        currency=result.currency,
        known_cost=result.known_cost,
        total_cost=result.total_cost,
        proposed_revenue=result.proposed_revenue,
        profit=result.profit,
        margin_percent=result.margin_percent,
        advance_amount=result.advance_amount,
        financing_exposure=result.financing_exposure,
        category_totals=result.category_totals,
        missing_data=result.missing_data,
        warnings=result.warnings,
        calculated_at=result.calculated_at,
        input_fingerprint=result.input_fingerprint,
    )


__all__ = [
    "CommercialCostCategory",
    "CommercialCostLine",
    "CommercialEstimateDraft",
    "CommercialEstimateRepository",
    "CommercialEstimateResult",
    "CommercialEstimateStatus",
    "CommercialEstimator",
    "CommercialEvidence",
    "REQUIRED_COST_CATEGORIES",
]
