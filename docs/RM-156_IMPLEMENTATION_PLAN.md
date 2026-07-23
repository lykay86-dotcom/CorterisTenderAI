# RM-156 — план реализации модели контрагента

Статус: `AUDIT-FIRST PLAN / IMPLEMENTATION NOT STARTED`.

## 1. Package sequence

1. Слить этот docs-only audit/contract/plan package и получить successful exact merge-SHA gate.
2. В отдельном worktree добавить strict expected-red tests без application changes.
3. Сохранить доказательство, что failures относятся только к отсутствующим RM-156 boundaries.
4. После merge/exact tests package создать отдельный feature worktree.
5. Реализовать минимально:
   - contractor-INN value object;
   - existing UTC audit type hardening;
   - `Contractor` ORM/repository/UoW registration;
   - application schema 3→4 migration и guards.
6. Не добавлять UI, search, source adapters или RM-157–RM-168 fields.
7. Провести feature acceptance, PR-head gate, merge и exact merge-SHA gate.
8. Только затем выполнить отдельный docs-only closeout RM-156 и активировать RM-157.

## 2. Expected-red package

Tests фиксируют контракт до кода:

- valid organization/person INN vectors и checksum mutations;
- invalid type, Unicode digits, punctuation, whitespace-inside, 9/11/13 digits;
- direct ORM and repository validation parity;
- unique identity, deleted lookup/restore/conflict behavior;
- UTC create/update/delete/restore after new SQLite session;
- schema 3→4 backup, row preservation, current idempotence, future/corrupt fail-closed;
- schema columns/indexes and diagnostics expected version;
- public imports, UoW exposure and no forbidden imports;
- bootstrap/RM-107 regression guards.

Regular run должен xfail только отсутствующие boundaries; explicit `--runxfail` должен давать
целевые assertion failures без import/setup/network failures.

## 3. Feature commit boundaries

Reviewable commits:

1. identity value object and unit tests green;
2. UTC audit type hardening and round-trip tests green;
3. ORM/repository/UoW integration green;
4. schema 3→4 migration/backup/future-corrupt guards green;
5. acceptance evidence and documentation.

Нельзя объединять этап с opportunistic refactor существующего `Company`, Collector или UI.

## 4. Validation

Команды уточняются по актуальным `pyproject.toml` и `.github/workflows/quality-gate.yml`.
Минимальный контур:

```powershell
python scripts/check_repository_secrets.py
python -m ruff check .
python -m ruff format . --check
python -m mypy
python -m pytest -q <RM-156 focused tests>
python -m pytest -q tests/test_database_core.py tests/test_database_migrations_121.py
python -m pytest -q tests/test_collector_normalizer.py tests/test_tender_registry.py
python -m pytest -q tests/test_bootstrap_tender_search_integration.py
python -m pytest -q tests/test_build_release_contract.py tests/test_frozen_self_test.py
python scripts/check_rm155_compatibility.py
python -m pytest -q
python -m pip_audit --skip-editable
git diff --check
```

Pytest использует `QT_QPA_PLATFORM=offscreen` и короткий command-scoped `TEMP`/`--basetemp`.
PR-head и exact merge-SHA Quality Gate обязаны пройти на Windows Python 3.12/3.13, включая
dependency audit.

## 5. Rollback

- до feature merge: удалить только незлитую ветку/worktree;
- после feature merge: revert feature merge и восстановить verified schema-3 backup при
  фактической необходимости;
- не удалять contractor rows вручную и не выполнять автоматический downgrade;
- Collector data/schema/settings/credentials и RM-107 decisions не откатываются;
- audit docs сохраняются как evidence даже при implementation blocker.
