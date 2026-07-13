# Инструкция по установке документации

```powershell
git checkout main
git pull origin main
git checkout -b docs/rm-108-roadmap-v2
```

Скопировать файлы из папки `docs/` архива в `CorterisTenderAI/docs/`, заменив ROADMAP.md, STATUS.md, DEFINITION_OF_DONE.md и ROADMAP_HISTORY.md.

Проверить:
```powershell
git diff -- docs
```

Коммит:
```powershell
git add docs
git commit -m "docs(rm-108): adopt roadmap v2 and close rm-107"
git push -u origin docs/rm-108-roadmap-v2
```

PR: `docs(rm-108): adopt roadmap v2 and close RM-107`.

После merge:
```powershell
git checkout main
git pull origin main
git checkout -b feat/rm-108-ai-tender-summary
```

Начать только RM-108.1 — аудит.
