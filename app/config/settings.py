from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from platformdirs import user_data_dir, user_log_dir
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="CORTERIS_", env_file=".env", extra="ignore")
    env:str="production"
    database_url:str=""
    ai_provider:str="none"
    openai_base_url:str="https://api.openai.com/v1"
    openai_model:str="gpt-4.1-mini"
    log_level:str="INFO"

    @property
    def data_dir(self)->Path:
        p=Path(user_data_dir("CorterisTenderAI","Corteris")); p.mkdir(parents=True,exist_ok=True); return p
    @property
    def log_dir(self)->Path:
        p=Path(user_log_dir("CorterisTenderAI","Corteris")); p.mkdir(parents=True,exist_ok=True); return p
    @property
    def resolved_database_url(self)->str:
        return self.database_url or f"sqlite:///{(self.data_dir/'corteris_tender_ai.db').as_posix()}"

@lru_cache
def get_settings()->Settings:
    s=Settings(); s.database_url=s.resolved_database_url; return s
