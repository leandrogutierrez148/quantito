---
trigger: always_on
---

# Git Workflow & Branch Management Standards

This rule defines mandatory Git and worktree procedures for all AI agents and developers working on the **Quantito** repository.

---

## 1. Mandatory Branching Policy

Before starting work on any user requirement, feature, bug fix, or refactoring task, you **MUST** ensure you are working on a dedicated Git branch or worktree.

> [!IMPORTANT]
> **Never commit or push directly to `main` or `master`.** All changes must originate from a dedicated task branch.

---

## 2. Branch Naming Convention

All branch names must strictly follow the format:

```text
<type>/<short-kebab-case-description>
```

### Allowed Types:
- `fix/`: Bug fixes and error resolutions (e.g., `fix/dockerfile-with-pyproject`, `fix/delayed-pipeline-error`).
- `feat/`: New features, strategies, sinks, or capabilities (e.g., `feat/rsi-strategy`, `feat/bigquery-sink-batching`).
- `chore/`: Maintenance, dependency updates, and configuration tasks (e.g., `chore/cleanup-logs`, `chore/ruff-settings`).
- `refactor/`: Code refactoring without behavioral changes (e.g., `refactor/pipeline-data-extraction`).
- `test/`: Adding or updating test suites (e.g., `test/engine-failure-cases`).
- `docs/`: Documentation updates (e.g., `docs/architecture-guide`).

### Rules for the Descriptor:
1. Must use **lowercase** and **kebab-case** (hyphen-separated words).
2. Must be concise, self-explanatory, and directly related to the task.
3. Example: `fix/dockerfile-with-pyproject`

---

## 3. Standard Git Workflow

1. **Verify Current State**:
   ```bash
   git status
   git branch
   ```

2. **Create and Switch to the New Branch**:
   ```bash
   # From updated main branch:
   git checkout -b <type>/<short-description>
   ```

3. **Or Using Worktrees (if applicable)**:
   ```bash
   git worktree add ../quantito-<short-description> -b <type>/<short-description>
   ```

4. **Verify Quality Before Committing**:
   - Run Ruff linter and formatting checks:
     ```bash
     .venv/bin/ruff check . && .venv/bin/ruff format --check .
     ```
   - Run test suite:
     ```bash
     PYTHONPATH=. .venv/bin/python -m unittest discover tests
     ```

5. **Commit with Plain Message**:
   - Use a clear, concise, plain description.
   - Example:
     ```bash
     git add <modified-files>
     git commit -m "Fix dependency issue"
     ```

