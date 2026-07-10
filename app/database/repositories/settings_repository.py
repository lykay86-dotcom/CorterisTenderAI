from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AppSetting
from ..repository import Repository


class SettingsRepository(Repository[AppSetting]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, AppSetting)

    def get_value(self, key: str, default: object = None, *, scope: str = "global") -> object:
        stmt = select(AppSetting).where(
            AppSetting.scope == scope,
            AppSetting.key == key,
            AppSetting.is_deleted.is_(False),
        )
        setting = self.session.scalar(stmt)
        return default if setting is None else setting.value

    def set_value(
        self,
        key: str,
        value: object,
        *,
        scope: str = "global",
        description: str = "",
    ) -> AppSetting:
        stmt = select(AppSetting).where(AppSetting.scope == scope, AppSetting.key == key)
        setting = self.session.scalar(stmt)
        if setting is None:
            setting = AppSetting(scope=scope, key=key, value=value, description=description)
            self.add(setting)
        else:
            setting.value = value
            setting.description = description or setting.description
            setting.restore() if setting.is_deleted else setting.touch()
            self.session.flush()
        return setting
