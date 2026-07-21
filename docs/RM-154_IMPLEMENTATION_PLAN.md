# RM-154 Implementation Plan

Status: approved audit-first plan.

## Scope and branch discipline

Implementation is performed in dedicated worktree
`C:\CorterisTenderAI_1_5_1\.worktrees\rm154` on branch
`feat/rm-154-visual-qa`, based on canonical main
`2453304b5a7f7bea74bccf07e2ceccc4b6cf11a4`. The primary checkout contains unrelated
user changes and is not modified.

RM-154 closes UI-141-016 only. RM-155 cannot start until the feature merge SHA passes
the exact gate and canonical closeout is merged.

## Commit sequence

### 1. Audit and plan — docs only

- record audit, state inventory, render decision, visual contract, and this plan;
- include entry-gate and renderer-characterization evidence;
- commit before adding infrastructure, tests, workflow changes, or PNGs.

### 2. Characterization and expected-red tests

- add typed immutable case/environment/policy/result schemas;
- add failing contract tests for missing baseline, environment mismatch, unsafe path,
  privacy leakage, repeatability drift, deliberate token mutation, and layout change;
- prove failures are diagnostic and do not write approved directories.

The expected-red commit is retained in history. The branch is not proposed for merge
until all required tests are green.

### 3. Test-only renderer and synthetic factories

- implement font registration/fingerprint, opaque widget capture, normalization,
  hashes, strict comparator, and bounded artifacts;
- extract/adapt the existing in-memory shell setup into visual fixtures;
- add the initial shell and component-gallery catalog;
- add ready/critical cases only after their public-owner state builders pass privacy
  and three-run repeatability checks;
- add cleanup/resource assertions.

### 4. Candidate workflow and review bundle

- add a dedicated canonical candidate command and sanitized bundle;
- extend the Windows quality gate so policy/unit tests run on 3.12 and 3.13 while
  canonical candidate/compare runs only on 3.12;
- pin any new official artifact action to a full commit SHA and use 14-day retention;
- prove normal application packaging excludes all visual artifacts.

### 5. Canonical baseline import

- run candidate mode on the canonical CI renderer;
- inspect every candidate PNG and manifest;
- import with the explicit authorization workflow and recorded rationale;
- rerun canonical comparison and deliberate mutation tests;
- record case count, hashes, repository size, fingerprint, and review result.

### 6. Acceptance, feature PR, and exact merge gate

Run commands derived from `pyproject.toml` and `.github/workflows/quality-gate.yml`:

```text
python -m pytest -q --basetemp .pytest-basetemp-rm154-full
python -m mypy
python -m ruff check .
python -m ruff format . --check
python -m scripts.check_repository_secrets
python -m pip_audit --skip-editable
python -m scripts.audit_ui_inventory --format summary
python -m scripts.check_design_system
python -m bandit -r scripts/rm154_visual_qa -q
python -m pytest -q tests/test_build_release_contract.py
powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1 -SkipTests -SkipInstaller
python -m pytest -q tests/test_rm153_performance_contract.py tests/test_rm153_theme_epoch.py
python -m scripts.rm154_visual_qa validate baseline tests/visual/baselines/rm154-v1
```

Add the RM-154 visual policy/candidate/compare commands and RM-153 performance command
to the recorded acceptance results. Use a worktree-local pytest `--basetemp` if the
known external `%TEMP%` ACL remains inaccessible, and record that fact exactly.

Open a feature PR, require both Python matrix jobs, merge, and verify the same feature
merge SHA through the exact GitHub Actions run and both successful job IDs.

### 7. Canonical docs closeout

After the exact merge gate only:

- add `docs/RM-154_ACCEPTANCE.md` with exact local and CI evidence;
- update `docs/STATUS.md`, `docs/ROADMAP.md`, and `docs/ROADMAP_HISTORY.md` atomically;
- close UI-141-016 with artifact/fingerprint/baseline references;
- preserve RM-152 native statuses verbatim;
- activate RM-155 as the sole next stage, without implementing it;
- merge a docs-only closeout PR and verify final canonical main CI.

## Rollback and failure handling

All implementation is test-only except the quality-gate wiring. If deterministic
capture cannot be achieved, remove the unaccepted infrastructure commit(s), retain
the audit evidence, and leave RM-154 active with a typed blocker. Never weaken a
tolerance, add a broad mask, omit a required case, or accept a noncanonical candidate
merely to obtain green CI.

If a renderer dependency, font, or runner image changes, comparison blocks before
pixel evaluation. The change is handled through a new fingerprint plus explicit
candidate review, not an automatic baseline rewrite.
