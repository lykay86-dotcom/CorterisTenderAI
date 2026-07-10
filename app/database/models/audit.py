from __future__ import annotations

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, UUIDAuditMixin


class AuditLog(UUIDAuditMixin, Base):
    __tablename__ = "audit_logs"

    actor: Mapped[str] = mapped_column(String(250), default="system", index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), default="", index=True)
    entity_id: Mapped[str] = mapped_column(String(36), default="", index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    before_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
