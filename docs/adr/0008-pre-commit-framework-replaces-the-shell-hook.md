# ADR-0008: pre-commit framework replaces the versioned shell hook

- Status: accepted (hook set amended by ADR-0010: deptry joined the local hooks)
- Date: 2026-08-19

## Context

Local gates ran through a hand-written shell hook (`hooks/pre-commit`)
activated with `git config core.hooksPath hooks`. It worked, but it re-ran
the whole suite on every commit with no autofix, offered none of the common
hygiene checks (broken TOML/YAML, merge-conflict markers, lockfile drift),
and required a dedicated CI shellcheck job just to lint the hook itself.
pi-config made the same migration first (its ADR-0010); converging on it
also aligns the CI check names across the fleet's mature repositories,
a prerequisite for required status checks in the repository rulesets.

## Decision

Adopt the pre-commit framework (`.pre-commit-config.yaml`): hygiene hooks,
ruff autofix + format, and the official `uv-lock` hook, with the type checker
and pytest as `repo: local` / `language: system` hooks so they run in the
project venv - isolated mirrors cannot see project dependencies and can drift
from CI. `hooks/pre-commit` and the `core.hooksPath` setting are
removed (`just setup` unsets it and installs the framework hooks); the CI
shellcheck job is retired with the shell script it existed to lint. CI
remains the authority: it runs the same gate commands directly, not through
pre-commit.

## Consequences

Commits get faster feedback (changed-files scope, autofix) and lockfile
drift is caught at commit time. Tool versions appear in two places -
`uv.lock` for the local hooks and `rev:` tags for the mirrors - so bumping
ruff or uv means keeping the matching `rev:` in sync; the config comments
flag this. Existing clones must run `just setup` (or
`uv run pre-commit install --install-hooks`) once to switch over. The CI
check-name set becomes {quality, secrets-scan, pip-audit, zizmor}, identical
to pi-config.
