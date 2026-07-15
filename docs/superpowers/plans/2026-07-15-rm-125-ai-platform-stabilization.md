# RM-125 — implementation plan

Baseline: `a54ca0b039af95beedd81c1736be6151a3a58616`.

Branch: `fix/rm-125-stabilize-ai-platform`.

## 1. Audit-only commit

- Зафиксировать `docs/RM-125_AUDIT.md`, `docs/RM-125_REQUIREMENTS.md` и этот plan.
- Не изменять application/tests в audit commit.
- Commit: `docs(rm-125): audit AI platform stability`.

## 2. RED contract

- Добавить `tests/test_ai_execution_contract.py`.
- Расширить repository/service/analyzer/orchestrator/recheck/provider/runtime/full-analysis/
  Decision Service/UI/export tests всеми 45 acceptance-сценариями.
- Запустить target с worktree-local `--basetemp`, сохранить точную RED-причину в requirements.
- Commit: `test(rm-125): define AI platform stability contract`.

## 3. Execution и repository contract

- Добавить один pure immutable execution contract и exact helpers.
- Передавать current contract через prepared invocation; не дублировать equality в recheck.
- Ввести immutable cache lookup result, удалить `last_warning`.
- Выполнять newest-first exact-contract lookup ниже corrupt/incompatible rows.
- Сохранить append-only table, payload v10 и physical SQLite schema.

## 4. Analyzer/service semantics

- Создавать valid empty-source provenance для `no_documents` без provider call.
- Ввести единый current cacheability predicate до save.
- Отображать allowlisted provider codes на fixed warnings без raw message и retry.
- Повысить analyzer version `11 -> 12`; остальные версии не менять.
- Recheck захватывает exact baseline до current save и выполняет один analyzer call.

## 5. Orchestrator concurrency

- Добавить per-key coordinator в existing orchestrator.
- Сериализовать normal/recheck одного key и сохранить parallelism разных keys.
- Гарантировать release при exception и cleanup registry entries.
- Не переносить coordinator в UI и не добавлять polling/sleep/global execution lock.

## 6. Explicit RM-107 boundary

- Удалить `_USE_LATEST_AI_ANALYSIS`, implicit repository `latest(...)` и repository dependency из
  Participation Decision/runtime.
- Сохранить explicit current result из full analysis и deterministic-only standalone evaluation.
- Не изменять participation policy/score и critical stop-factor ordering.

## 7. Acceptance и feature publication

- Запустить 13-file target, full pytest, Ruff check/format, mypy, secret scan, pip-audit и
  `git diff --check` с worktree-local temp/cache.
- Выполнить обязательные static architecture/security/version checks.
- Implementation commit: `fix(rm-125): stabilize AI execution contracts`.
- Записать exact результаты в requirements/roadmap acceptance section.
- Acceptance commit: `docs(rm-125): record feature acceptance`.
- Push и PR title: `fix(rm-125): stabilize AI execution contracts`.

## 8. Post-merge closeout

- После feature merge и успешного Windows Quality Gate создать `docs/rm-125-completion` от fresh
  main.
- Изменить только `docs/ROADMAP.md`, `docs/STATUS.md`, `docs/ROADMAP_HISTORY.md`.
- Зафиксировать merge SHA, run ID и exact Python 3.12/3.13 results.
- Commit: `docs(rm-125): complete AI platform stabilization`.
- Только после merged docs closeout отметить RM-125 `DONE`, RM-126 — единственным `IN PROGRESS`.
