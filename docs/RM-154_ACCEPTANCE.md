# RM-154 acceptance evidence

## Scope and exact identities

- Canonical production baseline: `2453304b5a7f7bea74bccf07e2ceccc4b6cf11a4`.
- Audit/decision/plan package: `b7c5052`.
- Expected-red contract: `ce3f53c`.
- Strict comparison guardrails: `6e5a9a5`.
- Deterministic renderer/workflow: `fad5f6d`.
- Reviewed canonical baseline: `c66c076`.
- Permanent CI gate: `4871765`.
- Final feature head: `109f084aaf84cd907b849d17635bb7cfad1d97ab`.
- Feature merge: `40f0e327d0d485b93e93f39bab1d838e584b8914`.

RM-154 closes UI-141-016 only. It adds test-only visual capture, comparison, review and CI
governance. Production shell, router, pages, theme adapters, charts, tables, dialogs, business
owners and deterministic decision paths are reused rather than duplicated.

## Audit and visual matrix

The audit-first package records the production owners, dynamic regions, state matrix, renderer
decision, deterministic environment, privacy threats, tolerance/masking policy and implementation
sequence in:

- `RM-154_VISUAL_QA_AUDIT.md`;
- `RM-154_VISUAL_STATE_INVENTORY.md`;
- `RM-154_RENDER_TECHNOLOGY_DECISION.md`;
- `RM-154_VISUAL_QA_CONTRACT.md`;
- `RM-154_EXPECTED_RED.md`;
- `RM-154_IMPLEMENTATION_PLAN.md`.

The accepted catalog contains 14 normalized PNGs: seven dark/light pairs for the component
gallery, Dashboard ready state, critical-stop participation dialog, and shell analytics,
Dashboard, tenders and workflow empty states. Viewport, theme, state, locale, timezone, clock and
settings are fixed. Every fixture is synthetic and in-memory.

## Renderer, environment and baselines

- Capture backend: test-only PySide6 `QWidget.render` into opaque `QImage.Format_RGB32`.
- Normalization/compare backend: Pillow RGB with metadata-free deterministic PNG output.
- Canonical profile: `windows-latest-python312`, Python 3.12.10, PySide6/Qt 6.11.1,
  Pillow 12.3.0 and GitHub image `win25-vs2026:20260714.173.1`.
- Fonts: system Segoe UI regular/semibold/bold and Consolas, registered in place and pinned by
  file hashes; font files are not copied or redistributed.
- Renderer fingerprint:
  `f1cd92373456028fd9360b3a032ef9b8d5784dc90d00abad4080d404db0dba56`.
- Baseline schema: `rm154-visual-baseline-v1`; 14 PNGs total `950716` bytes.
- Policy: `strict-rgb-v1`, zero changed pixels, zero maximum/mean delta and no masks.

Three unchanged captures per case produced identical normalized hashes. A deliberate theme-token
mutation and a deliberate layout mutation both fail strict comparison with visible diagnostics.
Environment drift blocks before pixel comparison with a typed result; it cannot become a pixel
pass or silently rewrite the baseline.

The canonical candidate was created by workflow-dispatch run `29817956646`, Python 3.12 job
`88593614567`, artifact `8490282481`, digest
`sha256:8beebd55a9e108318bd67a840b4bd1419c0d115e124a2fa022f91ca2173f3030`.
All 14 cases and their manifest/hashes passed validation. The dark/light surfaces were reviewed
before import. Import required the exact approval phrase, named reviewer and reason on the
canonical non-CI environment; ordinary CI cannot auto-accept a candidate.

## Privacy, security and retention

- Fixtures read no network, keyring, production database, user settings, live AI or real tender
  data.
- Case IDs and artifact roots are allowlisted and containment-checked; traversal, symlinks,
  malformed manifests, hash substitution, oversized images and repository-size overflow fail
  closed.
- Candidate/baseline privacy scans reject secrets, absolute paths and host/user identifiers.
- Repository secret scan passed. The RM-154 Bandit contour has zero findings; two narrow annotated
  false positives cover the `PASS` outcome label and a fixed `git rev-parse HEAD` argv with shell
  disabled.
- Review/failure upload uses pinned official `actions/upload-artifact` v6 commit
  `b7c566a772e6b6bfb58ed0dc250532a479d7789f` with 14-day retention.
- The PyInstaller spec and release contract prove baselines, candidates and diagnostics are not
  bundled into the application.

## Native and semantic boundary

Offscreen exact pixels are not native Windows/DPI certification. RM-152 remains truthful at
`0 PASS`, `4 BLOCKED` and `29 NOT_EXECUTED`; RM-154 does not promote those cells. Semantic,
accessibility, route, ownership and critical-stop tests remain primary. Score, recommendation,
critical stop-factor priority, Decimal values, identities, exports and confirmed decisions are
unchanged.

## Local validation ledger

- expected red: `6 failed, 3 passed`, all six intended missing boundaries;
- focused RM-154/release contour: `30 passed in 40.44s`;
- full pytest: `2378 passed, 2 warnings in 199.01s`; warnings are the accepted openpyxl fixture
  unknown-extension and conditional-formatting warnings;
- RM-153 performance/resource guards: `9 passed in 13.20s`;
- repeated candidate/baseline validation: 14/14 `PASS`;
- Ruff check: PASS; Ruff format: `788 files already formatted`;
- required mypy: `Success: no issues found in 20 source files`;
- repository secret scan: PASS;
- design-system audit: matrix `47`, styles `44`, violations `0`;
- UI inventory: 97 modules, 153 UI test modules, no literal colors outside theme;
- dependency audit: no known vulnerabilities; editable project skipped by policy;
- build/release contract: `8 passed` in exact merge-SHA CI;
- real one-file build: `82440663` bytes, SHA-256
  `46c199c7b9792e2d4686e709c419135cf475983e7108dc420967897e2565db92`;
- isolated frozen self-test: `success=true`, all nine checks passed.

## GitHub evidence

- Feature PR #116 final head `109f084aaf84cd907b849d17635bb7cfad1d97ab`.
- Final PR-head Quality Gate run `29822184296`: Python 3.12 job `88607135547` and Python 3.13
  job `88607135493`, both successful; Python 3.12 strict visual comparison passed 14/14.
- Feature PR #116 merged as `40f0e327d0d485b93e93f39bab1d838e584b8914`.
- Exact merge-SHA push-run `29823579968` confirmed that exact `headSha`:
  - Python 3.12 job `88611629793`: `2378 passed, 2 warnings in 132.81s`, strict visual
    comparison 14/14 `PASS`, dependency audit successful; job duration 4m28s;
  - Python 3.13 job `88611629760`: `2378 passed, 2 warnings in 168.76s`, dependency audit
    successful; job duration 5m17s.
- Secret scan, Ruff check/format, required mypy, offline/migration/import/composition/build smokes,
  full suite and dependency audit are successful on both versions. The only annotations are
  non-blocking official-actions Node.js 20/24 migration notices.

## Invariants and rollback

No production dependency, database/settings schema, migration, telemetry, persistent screenshot
cache or lifecycle owner was added. RM-107 deterministic score/recommendation/critical stop-factor
priority is unchanged. Rollback is a revert of feature merge
`40f0e327d0d485b93e93f39bab1d838e584b8914`; no data, schema or settings downgrade is required.

RM-154 satisfies its Definition of Done. This separate docs-only closeout marks RM-154 `DONE` and
activates RM-155 as the sole `IN PROGRESS` stage without starting RM-155 implementation.

