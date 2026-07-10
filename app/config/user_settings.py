from __future__ import annotations
from dataclasses import dataclass, asdict, field
from pathlib import Path
import json, shutil
from app.config.settings import get_settings

@dataclass(slots=True)
class PlatformConnection:
    name: str
    protocol: str = "API"
    endpoint: str = ""
    username: str = ""
    enabled: bool = True
    notes: str = ""

@dataclass(slots=True)
class UserPreferences:
    ai_provider: str = "OpenAI API"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4.1-mini"
    profit_mode: str = "markup"
    profit_percent: float = 30.0
    vat_percent: float = 22.0
    risk_percent: float = 5.0
    licenses: list[str] = field(default_factory=list)
    sro_memberships: list[str] = field(default_factory=list)
    template_dir: str = ""
    platforms: list[PlatformConnection] = field(default_factory=list)
    company_name: str = "ООО «КОРТЕРИС»"
    inn: str = "9701327346"
    kpp: str = "770101001"
    ogrn: str = "1267700130092"
    legal_address: str = "105066, г. Москва, ул. Доброслободская, д. 7/1, стр. 3, помещ. 3/2"
    director: str = "Лукин Юрий Юрьевич"
    phone: str = "+7 (495) 150-04-03"
    email: str = "info@corteris.ru"
    website: str = "www.corteris.ru"
    taxation_system: str = "ОСНО"
    logo_path: str = ""
    signature_path: str = ""
    stamp_path: str = ""
    projects_dir: str = ""
    backups_dir: str = ""

class UserSettingsStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (get_settings().data_dir / "user_settings.json")

    def load(self) -> UserPreferences:
        defaults=UserPreferences(
            template_dir=str(Path(__file__).resolve().parents[2]/"templates"/"company"),
            logo_path=str(Path(__file__).resolve().parents[2]/"assets"/"corteris_logo.png"),
            projects_dir=str(get_settings().data_dir/"projects"),
            backups_dir=str(get_settings().data_dir/"backups"),
        )
        if not self.path.exists(): return defaults
        raw=json.loads(self.path.read_text(encoding="utf-8"))
        raw["platforms"]=[PlatformConnection(**x) for x in raw.get("platforms",[])]
        for k,v in asdict(defaults).items(): raw.setdefault(k,v)
        return UserPreferences(**raw)

    def save(self,prefs:UserPreferences)->None:
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.path.write_text(json.dumps(asdict(prefs),ensure_ascii=False,indent=2),encoding="utf-8")

    def import_template(self,source:Path,target_name:str|None=None)->Path:
        prefs=self.load(); target_dir=Path(prefs.template_dir or get_settings().data_dir/"templates")
        target_dir.mkdir(parents=True,exist_ok=True); target=target_dir/(target_name or source.name)
        shutil.copy2(source,target); return target

    def import_company_asset(self, source:Path, kind:str)->Path:
        target_dir=get_settings().data_dir/"company_assets"; target_dir.mkdir(parents=True,exist_ok=True)
        target=target_dir/f"{kind}{source.suffix.lower()}"; shutil.copy2(source,target); return target
