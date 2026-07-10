from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import AuditLog
from ..repository import Repository


class AuditRepository(Repository[AuditLog]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, AuditLog)

    def record(
        self,
        action: str,
        *,
        actor: str = "system",
        entity_type: str = "",
        entity_id: str = "",
        summary: str = "",
        before_data: dict | None = None,
        after_data: dict | None = None,
        metadata: dict | None = None,
    ) -> AuditLog:
        return self.add(
            AuditLog(
                actor=actor,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                summary=summary,
                before_data=before_data,
                after_data=after_data,
                metadata_json=metadata or {},
            )
        )
