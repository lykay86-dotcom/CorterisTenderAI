from __future__ import annotations
import shutil, zipfile
from pathlib import Path
from app.config.settings import get_settings
from app.parsers.documents import parse_document,classify_document,SUPPORTED
from app.repositories.tenders import TenderRepository

class ImportService:
    def __init__(self): self.repo=TenderRepository()
    def create_tender(self,title:str,number:str="",url:str="",nmck:float=0)->int:
        return self.repo.create(title=title,number=number,source_url=url,nmck=nmck).id
    def import_path(self,tender_id:int,source:Path)->list[str]:
        base=get_settings().data_dir/"projects"/str(tender_id); base.mkdir(parents=True,exist_ok=True)
        if source.suffix.lower()==".zip":
            with zipfile.ZipFile(source) as z: z.extractall(base)
        elif source.is_dir(): shutil.copytree(source,base,dirs_exist_ok=True)
        else: shutil.copy2(source,base/source.name)
        imported=[]
        for p in base.rglob("*"):
            if p.is_file() and p.suffix.lower() in SUPPORTED:
                text,pages=parse_document(p); kind=classify_document(p.name,text)
                self.repo.add_document(tender_id,name=p.name,path=str(p),kind=kind,text=text,page_count=pages); imported.append(p.name)
        return imported
