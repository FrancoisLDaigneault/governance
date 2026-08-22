# Optional convenience task runner (https://just.systems).
# Every command below works standalone -- just is never required.

# One-command onboarding: install deps and the pre-commit framework hooks.
# The hook types come from default_install_hook_types in .pre-commit-config.yaml,
# so this plain command installs the merge-commit gate too.
setup:
    uv sync --locked
    git config --unset-all core.hooksPath || true
    uv run pre-commit install --install-hooks

# Run the quality gates (same quality commands as the CI quality job)
check:
    uv run ruff check .
    uv run ruff format --check .
    uv run ty check --error-on-warning src scripts tests
    uv run mypy
    uv run deptry src
    uv run lint-imports
    uv run pytest -q

# Apply the baseline to one repository (dry-run by default; pass --apply)
bootstrap *ARGS:
    uv run python scripts/bootstrap.py {{ARGS}}

# Audit repositories against the baseline (pass --all for the whole fleet)
audit *ARGS:
    uv run python scripts/audit.py {{ARGS}}
