---
name: setup-python-guardrails
description: Set up deterministic guardrails for Python projects using the pre-commit framework with ruff and mypy. Covers linting, type checking, file size limits, cyclomatic complexity, and unused code. Use when user wants to add Python linting, type checking, pre-commit hooks, or guardrails for agent-generated code.
---

# Setup Python Guardrails

Deterministic guardrails dramatically improve code quality from LLM agents. This skill sets up the Python `pre-commit` framework with `ruff` and `mypy` as the default toolchain, with opt-in deep-coverage hooks for security, duplication, dependency rules, and dead code.

## What This Sets Up

### Default (always installed)

- **pre-commit** framework with `.pre-commit-config.yaml`
- **ruff** — linting, import sorting, unused imports/variables, line length, and cyclomatic complexity (C901) in one tool
- **mypy** — static type checking

### Opt-in deep coverage (documented, user selects)

- **bandit** — security static analysis (referenced by the `security-audit` skill)
- **pip-audit** — dependency vulnerability scanning (referenced by the `security-audit` skill)
- **vulture** — deeper dead code detection (unused methods, classes, properties beyond ruff's F-rules)
- **import-linter** — enforce layer/dependency rules (e.g. "billing must not import from orders")
- **jscpd** — copy-paste/duplication detection across files (language-agnostic)
- **radon** — maintainability index and additional complexity metrics

## Steps

### 1. Detect project environment

Check for `pyproject.toml`, `setup.py`, or `setup.cfg`. If none exist, create a minimal `pyproject.toml`:

```toml
[project]
name = "project-name"
version = "0.0.1"
requires-python = ">=3.11"
```

Check for `uv` (preferred) or `pip` as the package manager.

### 2. Install pre-commit

```bash
uv add --dev pre-commit ruff mypy
# or: pip install --dev pre-commit ruff mypy
```

### 3. Create `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]
        # Remove additional_dependencies if no third-party stubs are needed
```

### 4. Configure ruff in `pyproject.toml`

```toml
[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes (unused imports, variables, undefined names)
    "I",    # isort (import sorting)
    "C901", # mccabe complexity
    "UP",   # pyupgrade
]
mccabe = { max-complexity = 15 }

[tool.ruff.format]
quote-style = "double"
```

Adjust `max-complexity` and `line-length` to project taste. Common ranges:
- Complexity: 10 (strict) to 20 (lenient)
- Line length: 88 (black default) to 120

### 5. Configure mypy in `pyproject.toml`

```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false
```

Start permissive (`disallow_untyped_defs = false`) and tighten over time. Agents generate typed code more reliably when the check is present even if not fully strict.

### 6. Add a `check` script to `pyproject.toml`

```toml
[tool.scripts]
check = "pre-commit run --all-files"
```

Or document the command in the project README:

```bash
uv run pre-commit run --all-files
# or: pre-commit run --all-files
```

### 7. Install git hooks

```bash
pre-commit install
```

### 8. Verify

- [ ] `.pre-commit-config.yaml` exists
- [ ] `[tool.ruff]` section exists in `pyproject.toml`
- [ ] `[tool.mypy]` section exists in `pyproject.toml`
- [ ] `pre-commit install` ran successfully
- [ ] `pre-commit run --all-files` passes (or reports fixable issues)

## Opt-in: Deep Coverage Hooks

Add these to `.pre-commit-config.yaml` when the advisory profile or user requests them.

### Security (bandit + pip-audit)

Referenced by the `security-audit` skill for deterministic security checks.

```yaml
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.9
    hooks:
      - id: bandit
        args: ["-c", "pyproject.toml", "-r", "src"]
        additional_dependencies: ["bandit[toml]"]

  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: 0.2.18
    hooks:
      - id: pip-audit
        args: ["--strict"]
```

### Dead code (vulture)

Catches unused methods, classes, and properties beyond ruff's F-rules.

```yaml
  - repo: https://github.com/jendrikseipp/vulture
    rev: v2.11
    hooks:
      - id: vulture
```

### Duplication (jscpd)

Language-agnostic copy-paste detection. Install jscpd separately (`npm i -g jscpd` or use npx).

```yaml
  - repo: local
    hooks:
      - id: jscpd
        name: jscpd
        entry: npx jscpd
        args: ["src", "--min-lines", "10", "--threshold", "0"]
        language: system
        pass_filenames: false
```

### Layer/dependency rules (import-linter)

Enforce module boundaries (e.g. "billing must not import from orders").

```yaml
  - repo: https://github.com/seddimport/import-linter
    rev: 2.0
    hooks:
      - id: import-linter
```

Configure contracts in `pyproject.toml`:

```toml
[tool.importlinter]
root_packages = ["src"]

[[tool.importlinter.contracts]]
name = "Feature isolation"
type = "forbidden"
source_modules = ["src.billing"]
forbidden_modules = ["src.orders"]
```

### Maintainability metrics (radon)

Optional; provides maintainability index and Halstead complexity beyond mccabe.

```yaml
  - repo: local
    hooks:
      - id: radon
        name: radon mi
        entry: radon mi
        args: ["--min", "B", "src"]
        language: system
        pass_filenames: false
```

## Agent Integration

In the project's `AGENTS.md` or agent rules, mandate:

```
Always run `pre-commit run --all-files` (or `uv run pre-commit run --all-files`) before task completion.
Fix all reported issues before declaring the task done.
```

This ensures the agent runs the full guardrail chain on every change.
