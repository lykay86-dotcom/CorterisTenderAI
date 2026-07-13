# Repository instructions for coding agents

Before planning or changing the repository, read the canonical project documents:

- `docs/STATUS.md` defines the only active roadmap stage.
- `docs/ROADMAP.md` defines roadmap scope and ordering.
- `docs/DEFINITION_OF_DONE.md` defines completion requirements.
- `docs/ROADMAP_HISTORY.md` records accepted history.

Do not hard-code the active RM in agent instructions. Do not start the next RM until the
current stage satisfies the Definition of Done and its status is updated in the canonical
documents.

Preserve deterministic decision logic: AI output must not override the approved score,
recommendation, or critical stop-factor priority. Reuse existing adapters, analyzers,
orchestrators, repositories, and dependency-injection paths unless an audited protocol or
schema difference proves that a new component is required.

Before editing, inspect the worktree and protect unrelated user changes. Use a dedicated
branch or worktree for each RM package. Derive validation commands from `pyproject.toml` and
the active GitHub Actions workflow, and record exact results in the relevant roadmap
documents.
