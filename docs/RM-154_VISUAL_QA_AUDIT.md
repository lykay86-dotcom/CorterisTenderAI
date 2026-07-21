# RM-154 Visual QA Audit

Status: audit complete; implementation not started at the time of this document.

Audit base: `2453304b5a7f7bea74bccf07e2ceccc4b6cf11a4`
(`docs(rm-153): close stage and activate rm-154 (#115)`).

## Purpose

RM-154 closes UI-141-016: the application has deterministic semantic and
interaction coverage, but no governed screenshot/golden-image regression workflow.
This audit identifies the existing owners and test seams before any visual test
infrastructure or baseline PNG is added.

RM-154 does not change product decision logic, source adapters, scoring,
recommendations, critical stop-factor priority, native RM-152 evidence, or frozen
installer ownership.

## Entry gate

The canonical roadmap documents were read before planning. `docs/STATUS.md` names
RM-154 as the sole active stage, RM-153 is closed, and RM-155 remains planned.

The first baseline command exposed an external pytest temporary-directory ACL
failure:

```text
C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe -m pytest -q
```

All errors originated while pytest tried to inspect
`%LOCALAPPDATA%\Temp\pytest-of-сooocorteris`; even `Get-Acl` returned access denied.
An unchanged focused test passed with a worktree-local `--basetemp`, proving that
the repository fixture itself was not broken. The unchanged full suite then passed:

```text
C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe -m pytest -q --basetemp=C:\CorterisTenderAI_1_5_1\.worktrees\rm154\.pytest-basetemp-entry
2354 passed, 2 warnings in 172.54s (0:02:52)
```

The two warnings are the accepted openpyxl extension/conditional-formatting
warnings. The temporary directory was removed after the run. No source change was
used to obtain the green entry gate.

## Sources inspected

- `docs/STATUS.md`, `docs/ROADMAP.md`, `docs/DEFINITION_OF_DONE.md`, and
  `docs/ROADMAP_HISTORY.md`;
- the RM-154 task specification and the canonical RM-143..RM-155 design rebuild
  specification;
- RM-141 UI audit, inventory, owner map, user journeys, and redesign handoff;
- RM-143 through RM-153 acceptance evidence relevant to themes, states, charts,
  responsive layout, native evidence, and performance;
- RM-152 responsive matrix and named owner exceptions;
- RM-153 performance contract and post-implementation measurements;
- `pyproject.toml`, `.github/workflows/quality-gate.yml`, and the PyInstaller spec;
- the shell, dashboard, tender workspace, analytics, workflow, chart, dialog,
  theme, component-gallery, and navigation owners;
- existing UI tests and `scripts/benchmark_rm153_ui.py` test seams.

## Existing coverage and the remaining gap

The UI inventory audit at the entry SHA reports:

| Metric | Value |
|---|---:|
| UI modules | 97 |
| UI source lines | 37,549 |
| UI test modules | 152 |
| stylesheet calls | 47 |
| accessible names / descriptions | 90 / 53 |
| fixed / minimum / maximum size calls | 15 / 35 / 6 |
| `QTableView` / `QTableWidget` uses | 4 / 32 |
| timers / threads | 6 / 1 |
| literal colors outside theme owner | 0 |

`python -m scripts.audit_design_system` is green with 47 matrix entries,
44 stylesheet owners, and zero violations. Existing tests cover state semantics,
navigation, accessibility, themes, responsive contracts, charts, dialogs, and
performance. A repository search found no governed screenshot baseline, golden
manifest, pixel comparator, baseline-update authorization, or review bundle.

That absence is precisely UI-141-016. RM-154 must add visual evidence without
replacing the existing semantic assertions.

## Reusable production owners and test seams

The following owners already expose deterministic state setters and must be reused:

| Surface | Existing owner or seam | Relevant public state controls |
|---|---|---|
| shell and routing | `ModernMainWindow`, navigation registry/workspace | route requests, `apply_theme` |
| dashboard | dashboard page/controller/view model | data, refreshing, partial, warning, error, recent tenders, KPI |
| tender workspace | `TenderWorkspacePage` | dashboard filter, tender open, compatibility search, demo load |
| workflow | `BusinessWorkflowPage` | navigation state, dashboard filter, theme, shutdown |
| analytics | analytics page | snapshot, financial snapshot, filters, loading, error, theme |
| charts | RM-146 `ChartCanvas` and state model | loading, ready, empty, partial, stale, error, too-large, unavailable |
| participation decision | participation-score dialog | score, deterministic decision, busy, error, status, theme |
| full analysis | full-analysis dialog | progress, deterministic result, AI recheck display/error, error, theme |
| recovery | database-recovery dialog | theme and deterministic recovery state |
| component coverage | `ComponentGallery` | theme and representative component states |

`scripts/benchmark_rm153_ui._window()` already proves a bounded, in-memory shell
factory: it replaces repositories, settings, controller startup, health refresh,
and business-metrics persistence without changing production owners. RM-154 may
extract the pattern into test-only fixtures, but must not make the benchmark script
the permanent owner of visual cases.

## Dynamic and unsafe regions

The following inputs can make pixels nondeterministic or leak local state:

- wall-clock timestamps, relative-age labels, and locale-dependent formatting;
- generated UUIDs, repository rows, usernames, absolute paths, and recent files;
- asynchronous controller refresh, system-health monitoring, timers, animation,
  cursor/caret blink, focus rings, selection, and scroll position;
- platform/native window chrome, shadows, screen compositing, display scaling, and
  GPU/raster backend differences;
- font discovery and fallback order;
- network, database, keyring, AI provider, or user `QSettings` contents.

The visual fixture must replace every such input with fixed synthetic data or a
bounded in-memory adapter. Dynamic content is not solved by broad masking. No mask
is approved by the audit.

## Assets and typography

The repository contains product logos and local SVG icons with a manifest, but no
font file. The theme owner specifies `Segoe UI` and `Consolas`.

In the Windows offscreen plugin used for characterization, `QFontDatabase` initially
reported neither family. Captures were byte-stable but rendered text as missing-glyph
boxes, so those pixels are invalid as product baselines. Explicitly registering the
installed Windows font files fixed the rendering without copying them into the
repository:

| Local characterization file | SHA-256 |
|---|---|
| `segoeui.ttf` | `ba32a222b23d727267cf1aba4e5296fe84ce99b9d910915103fc085d7931bc88` |
| `seguisb.ttf` | `9853283466bd43993b9813215281fb9c7090cbd8e9b5453f6d0d040622e117e2` |
| `segoeuib.ttf` | `1b242874a2f57529060e770ba313e027a99d40b3c36e1c7e8b2dece16ad6ed88` |
| `consola.ttf` | `c6e6ce8119fdd47ec6a5449a08e2d2ad7f41ea03143aae193068ed9fa58eaebc` |

These hashes describe the local characterization machine only. The canonical CI
profile will record and enforce its own font hashes. A font mismatch is a typed
environment block, never a pixel comparison and never an implicit baseline update.
System fonts are used in place and are not redistributed or added to the executable.

## Renderer characterization

The following candidates were exercised on Windows 10, Python 3.12.7, PySide6
6.11.1 / Qt 6.11.1, Pillow 12.3.0, `QT_QPA_PLATFORM=offscreen`, Fusion style,
96 logical DPI, DPR 1, and a 1540x940 shell viewport.

- `QImage.Format_ARGB32_Premultiplied` was rejected: the image could retain zero
  alpha while differing RGB values, making a visible theme comparison ambiguous.
- `QImage.Format_RGB32` produced opaque RGB PNGs. Three repeated captures per case
  were byte-identical.
- `QWidget.render(QImage, QPoint())` is the supported PySide6 6.11 overload. A
  painter-only call is not portable across the supported binding signatures.
- `QScreen.grabWindow`, native chrome, and desktop screenshots were rejected for
  the strict offscreen contract because they introduce compositor and display state.

After explicit font registration, all eight route/theme characterization cases had
one unique hash across three independently constructed windows. Their combined PNG
size was 482,695 bytes. Dark/light pairs differed across the full canvas. These are
audit measurements, not accepted goldens.

## RM-152 native boundary

RM-152 records 29 `NOT_EXECUTED` and 4 `BLOCKED` native matrix cells. RM-154 strict
offscreen images cannot promote or rewrite any of those statuses. Native-only facts
such as real monitor DPI transitions, Windows chrome, OS dialogs, screen-reader
runtime behavior, and desktop compositing remain RM-152 evidence owned by the
corresponding matrix cells.

Every visual case declares whether native evidence is also required. The offscreen
result is still only `PASS`, `FAIL`, or typed `BLOCKED/SKIPPED` for the strict visual
profile; it is never native acceptance.

## CI, packaging, and repository impact

The quality gate is Windows `windows-latest` on Python 3.12 and 3.13 with the Qt
offscreen platform. Pillow is already a pinned runtime dependency, so RM-154 needs no
new runtime package. The PyInstaller spec already gathers Qt resources and must not
be broadened to include test goldens, diff images, review artifacts, or fonts.

Canonical pixel comparison will run only on the governed Python 3.12 renderer
profile. Schema, policy, privacy, case-catalog, hash, and comparator unit tests run
on both Python versions. Diagnostic artifacts are uploaded only on candidate or
failure paths and are not shipped.

## Audit decision

Proceed with a test-only visual harness based on opaque `QImage.Format_RGB32`,
`QWidget.render`, Pillow normalization/comparison, synthetic in-memory fixtures, an
explicit renderer fingerprint, exact initial comparison policy, and a review-first
baseline update command. Produce canonical candidate images in CI before committing
any golden. Do not accept local exploratory captures as baselines.

