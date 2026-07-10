from __future__ import annotations

from sqlalchemy import JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, UUIDAuditMixin


class AppSetting(UUIDAuditMixin, Base):
    __tablename__ = "app_settings"
    __table_args__ = (UniqueConstraint("scope", "key", name="uq_setting_scope_key"),)

    scope: Mapped[str] = mapped_column(String(100), default="global", nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    value: Mapped[object] = mapped_column(JSON, nullable=True)
    description: Mapped[str] = mapped_column(String(500), default="")
