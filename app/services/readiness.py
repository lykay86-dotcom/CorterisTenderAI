from __future__ import annotations
from pathlib import Path

def check_application(document_paths:list[Path], required_names:list[str]|None=None)->dict:
    required_names=required_names or ['Коммерческое предложение','Смета','Таблица соответствия']
    names=' '.join(p.name.lower() for p in document_paths)
    checks=[]
    for req in required_names:
        ok=all(token in names for token in req.lower().split())
        checks.append({'name':f'Приложен документ: {req}','ok':ok,'severity':'critical' if not ok else 'info'})
    for p in document_paths:
        checks.append({'name':f'Файл не пустой: {p.name}','ok':p.exists() and p.stat().st_size>0,'severity':'critical'})
        checks.append({'name':f'Допустимый формат: {p.name}','ok':p.suffix.lower() in {'.pdf','.docx','.xlsx','.xls','.zip'},'severity':'warning'})
    ready=all(x['ok'] for x in checks if x['severity']=='critical')
    return {'ready':ready,'status':'Заявка готова к подаче' if ready else 'Заявка не готова','checks':checks}
