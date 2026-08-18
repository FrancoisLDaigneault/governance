# Optional convenience task runner (https://just.systems).
# Every command below works standalone -- just is never required.

# One-command onboarding: install deps and enable the versioned pre-commit hook
setup:
    uv sync
    git config core.hooksPath hooks

# Run the quality gates (same quality commands as the pre-commit hook and the CI quality job)
check:
    uv run ruff check .
    uv run ruff format --check .
    uv run mypy
    uv run pytest -q

# Apply the baseline to one repository (dry-run by default; pass --apply)
bootstrap *ARGS:
    uv run python scripts/bootstrap.py {{ARGS}}

# Audit repositories against the baseline (pass --all for the whole fleet)
audit *ARGS:
    uv run python scripts/audit.py {{ARGS}}
