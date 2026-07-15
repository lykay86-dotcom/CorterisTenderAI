# RM-126 — план аудита раздела «Тендеры»

Дата: 16 июля 2026 года.
Baseline: `7d51159a0fcbe21a457276ab29cc80fd1a2eb985`.
Ветка: `docs/rm-126-tenders-audit`.
Worktree: отдельный, без изменений пользователя из основного checkout.

## Цель и границы

Провести docs-only аудит текущего UI, двух поисковых контуров, provider/settings/credentials,
persistence, lifecycle и downstream decision boundary. Результат — проверяемый source-of-truth и
handoff для RM-127–RM-140. Production behavior, схема БД, зависимости и live network не меняются.

## Порядок выполнения

1. Проверить entry gate: RM-125 `DONE`, feature/closeout PR merged, post-merge Windows Quality Gate
   успешен на Python 3.12/3.13, RM-126 — единственный `IN PROGRESS`, baseline чист относительно
   известных пользовательских файлов.
2. Создать отдельный worktree/ветку от baseline и зафиксировать OS, timezone, Python, SHA, PR и run.
3. Выполнить предварительный target contour и полный workflow-equivalent Quality Gate.
4. Проследить composition root и реальные call sites от bootstrap до dialogs, search/Collector,
   persistence и participation decision.
5. Составить inventory provider/source, profiles, settings/credentials, storage и C1–C20.
6. Сравнить sync profile search и async Collector; выбрать target boundary и transition plan.
7. Оформить findings с evidence, owner, severity, target RM и acceptance condition.
8. Принять решения D-01–D-10 и заполнить readiness matrix RM-127–RM-140.
9. Создать `docs/RM-126_AUDIT.md` и `docs/RM-126_REQUIREMENTS.md`; обновить acceptance section
   roadmap, не переводя RM-126 в `DONE`.
10. Запустить target contour, полный Quality Gate и `git diff --check`; записать точные результаты.
11. Коммит `docs(rm-126): audit tenders section`, push и PR
    `docs(rm-126): audit tenders section`.
12. После merge проверить Windows Quality Gate на merge SHA.
13. В свежей ветке `docs/rm-126-completion` изменить только `STATUS`, `ROADMAP`,
    `ROADMAP_HISTORY`, назначить RM-127 единственным `IN PROGRESS`; коммит
    `docs(rm-126): complete tenders audit stage`.
14. После merge closeout снова проверить Windows Quality Gate. Только затем считать RM-126 `DONE`.

## Валидация

Команды берутся из `.github/workflows/quality-gate.yml` и `pyproject.toml`. На локальной машине
используется `C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe`; для pytest задаётся
репозиторный `--basetemp=.tmp/...`, поскольку чужой каталог Windows Temp недоступен текущему
процессу.

- secret scan: `python scripts/ci/check_secrets.py`;
- Ruff: `python -m ruff check .` и `python -m ruff format --check .`;
- mypy: `python -m mypy` для утверждённого 20-file contour из workflow;
- offline/migration/import/composition/build smoke — точные команды workflow;
- target: tender/collector tests и bootstrap tender integration;
- full: `python -m pytest -q`;
- dependency audit: `python -m pip_audit`;
- repository integrity: `git diff --check`, `git status --short`.

## Коммиты и closeout

Основной audit PR не меняет статус RM-126 на `DONE`. Второй docs-only closeout допускается только
после merge основного PR и зелёного post-merge gate. Планируемые коммиты:

1. `docs(rm-126): audit tenders section`;
2. `docs(rm-126): record tenders audit acceptance` — только если acceptance нужно дополнить после
   review без изменения выводов;
3. `docs(rm-126): complete tenders audit stage` — отдельная closeout ветка после merge/gate.
