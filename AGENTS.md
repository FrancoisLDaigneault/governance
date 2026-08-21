# AGENTS.md - operating manual for coding agents

This repository is the governance baseline as code: it applies and audits
GitHub **repository and organization settings** for the `fld-forge` organization.
Repositories outside that organization are not part of its fleet.

Layout: `src/governance_tools/` (`baseline` loads and validates
`baseline.json`, `identifiers` validates targets, `gh` is the only network IO,
`compare` is pure comparison plus the stricter-than-baseline guard, `controls`
does per-control read/apply, `check` classifies one control, `repository` shares
repository checks, `bootstrap`, `org` and `audit` orchestrate, `matrix` and
`report` render, `readme` renders the generated README controls
block, `scheduled_audit` wraps the audit
for the scheduled task and writes only its own log files), `scripts/` (thin
wrappers), `tests/` (unit / integration); local gates run through the
pre-commit framework (`.pre-commit-config.yaml`).

A control is keyed by a repository or, with `"scope": "org"`, by an
organization. Loading validates that a control's endpoints carry the
placeholder its scope requires, so the two can never aim at each other. A
control carrying `manual_reason` has no corrective call: it audits, reports
drift, and renders `MANUAL` under `--apply` rather than claiming a write the
API would silently discard.

## Blast radius - read this first

The tool holds credentials that change settings on every repository it is
pointed at. A bug here does not fail a build, it silently weakens a fleet.
These invariants exist to bound that, and each is a named test:

- **Dry-run is the default.** Only `--apply` may mutate; tests assert that no
  mutating call is issued otherwise.
- **The stricter-than-baseline guard.** A live ruleset stricter than the
  baseline is reported and skipped, never lowered; `--force-normalize` is the
  only bypass, and a guard that cannot run renders `ERR` instead of normalizing.
- **A failed read is an error, never drift** - and never falls through to a
  corrective write. An unparseable response costs one cell, not the whole run.
- **Repository names are shape-checked** before reaching an API path template.

Never weaken one of these to make a test pass. If you change the behaviour,
change the test that describes it, in the same commit, and say so.

## Hard rules

- Keep every `subprocess` call inside `gh.py`. Everything else takes a
  `GhClient`; that is what makes the tool testable without the network.
- `baseline.json` lives inside the package (`src/governance_tools/`) so it
  ships in the wheel. Do not move it back to the repository root.
- The baseline is desired state, not a minimum floor. Never add a control whose
  desired value is looser than GitHub's default; where the API demands a field
  the baseline does not govern, preserve the live value (`apply_preserve`).
- English only, everywhere you write. An accent-heuristic gate
  (`tests/unit/test_language.py`) fails the suite on accented characters.
- `main` is protected: direct pushes are rejected by a repository ruleset.
  Every change lands through a branch and a pull request.

## Gates and commands

Setup: `uv sync --locked` then `uv run pre-commit install --install-hooks`
(or `just setup`, which also clears any legacy `core.hooksPath`). Python 3.12+.

The seven quality commands (also available as `just check`; the pre-commit
hooks and the CI quality job run exactly these):

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check --error-on-warning src scripts tests
uv run mypy
uv run deptry src
uv run lint-imports
uv run pytest -q
```

The full pytest run enforces a 90% branch-coverage floor; subset runs
(e.g. `uv run pytest tests/unit`) need `--no-cov`. Size and complexity caps:
McCabe <= 8, <= 30 statements and <= 5 arguments per function, lines <= 100
(ruff); modules <= 200 lines, scripts <= 20 lines (`test_standards.py`).
A documentation drift gate (`tests/unit/test_docs.py`) fails the suite when
doc claims (test counts, gate commands, caps, floors) diverge from reality.

## Release semantics (empirically verified)

Conventional Commits drive release-please (config under
`.github/release-please/`): `feat:` bumps the minor version, `fix:` and
`docs:` bump the patch (`docs:` produces a visible Documentation changelog
section), a breaking change bumps the major; `ci:`, `chore:`, `refactor:` and
`test:` do not release by themselves. Releases are created as drafts, get
their assets attached, and are published last - so an immutable release always
carries its assets.

## Known quirks

- `uv run` may rewrite `uv.lock` when `pyproject.toml` is ahead of it
  (post-release window). Restore with `git checkout -- uv.lock` unless the
  change is intended.
- release-please PRs carry CI checks only while the `RELEASE_PLEASE_TOKEN`
  secret exists: the workflow falls back to `github.token`, whose pushes
  trigger no CI (GitHub anti-recursion). If a release PR shows no checks,
  inspect the diff and rely on post-merge CI on `main`.
- CRLF warnings on Windows are checkout-side only; committed blobs are LF
  (`.gitattributes` enforces `eol=lf`).
- Repo-local SSH commit signing is configured (`commit.gpgsign true`);
  commits sign automatically - do not disable or bypass it.
- A fleet audit costs roughly a dozen API calls per repository; `--all`
  enumerates every non-archived repository in `fld-forge`, and no other owner.
