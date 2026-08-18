# Governance baseline as code

[![CI](https://github.com/fld-forge/governance/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/fld-forge/governance/actions/workflows/ci.yml)
[![CodeQL](https://github.com/fld-forge/governance/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/fld-forge/governance/security/code-scanning)
[![Release](https://img.shields.io/github/v/release/fld-forge/governance)](https://github.com/fld-forge/governance/releases)
[![License](https://img.shields.io/github/license/fld-forge/governance)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](pyproject.toml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![mypy](https://img.shields.io/badge/mypy-strict-blue)](pyproject.toml)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Coverage](https://img.shields.io/badge/coverage-%E2%89%A590%25%20(branch)-brightgreen)](pyproject.toml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/fld-forge/governance/badge)](https://scorecard.dev/viewer/?uri=github.com/fld-forge/governance)

This repository governs GitHub **repository settings** across the fleet: it
applies and audits them from a single machine-readable baseline.

It turns a hand-maintained platform-settings inventory into an executable
desired-state baseline for every repository owned by the account.

| File | Role |
| --- | --- |
| `src/governance_tools/baseline.json` | Machine-readable desired state: 10 controls, each with its read endpoint, a jq projection, the desired value and the corrective API call. Every desired value was frozen from a live, verified reference state rather than written from memory. It ships inside the package so an installed wheel can find it. |
| `scripts/bootstrap.py` | Applies the baseline to one repository. Dry-run by default; `--apply` executes. Idempotent: re-running on a compliant repo changes nothing and exits 0. |
| `scripts/audit.py` | Compliance matrix across repositories (`--all` = every non-archived repo you own). Exit 1 on any drift, error or skip. |
| `src/governance_tools/` | The package: `baseline` (load and validate), `gh` (the only IO), `compare` (pure comparison and the stricter guard), `controls` (per-control read/apply), `bootstrap` and `audit` (orchestration), `report` (results and rendering). |

## Setup

```bash
uv sync
git config core.hooksPath hooks   # enable the versioned pre-commit gate
```

Or `just setup`. Requirements: `gh` authenticated with the `repo` scope,
[uv](https://docs.astral.sh/uv/) and Python 3.12+ (uv downloads it
automatically via `.python-version`). A fleet audit costs roughly 3 seconds
per repository (a dozen API calls each).

## Usage

```bash
# See what a repo would need (no changes made):
uv run python scripts/bootstrap.py OWNER/REPO

# Apply the baseline to a repo:
uv run python scripts/bootstrap.py OWNER/REPO --apply

# Overwrite a ruleset the guard flagged as stricter than the baseline:
uv run python scripts/bootstrap.py OWNER/REPO --apply --force-normalize

# Audit the whole fleet (or specific repos):
uv run python scripts/audit.py --all
uv run python scripts/audit.py OWNER/REPO1 OWNER/REPO2
```

## Quality gates

`uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` and
`uv run pytest -q` (90% branch-coverage floor). All four run in the
versioned pre-commit hook, in the CI quality job and via `just check`. The
suite never touches the network: every test drives the real code through a
fake `gh` layer, so mutations are recorded and "no write without `--apply`"
is provable.

CI adds a locked install (`uv sync --locked`), gitleaks over the full git
history, pip-audit, zizmor, shellcheck and a weekly scheduled run; CodeQL and
OpenSSF Scorecard analyse the repository on their own cadence.

## Project documents

| Document | Purpose |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | Operating manual for coding agents: blast radius, invariants, hard rules |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Setup, contribution flow, gates, commit conventions |
| [`GOVERNANCE.md`](GOVERNANCE.md) | Who decides, and what changing the baseline requires |
| [`SECURITY.md`](SECURITY.md) | Threat model, reporting, release-asset verification |
| [`NORTHSTAR.md`](NORTHSTAR.md) | Measured steering KPIs, one per axis |
| [`docs/adr/`](docs/adr/README.md) | Architecture decision records |

## Controls

`ruleset-main-protection`, `ruleset-release-tags`, `immutable-releases`,
`codeql-default-setup`, `dependabot-alerts`, `dependabot-security-updates`,
`secret-scanning`, `secret-scanning-push-protection`,
`private-vulnerability-reporting`, `actions-workflow-permissions`.

Public-only controls (rulesets, CodeQL, secret scanning, push protection,
private vulnerability reporting) are skipped with `NA` on private repos:
a free personal plan only gets them on public repositories. Machine-local
commit-signing configuration is out of scope: it lives in a clone's
`.git/config`, not in the platform API this baseline governs.

Comparison is projection-based: only the fields the baseline governs are
compared (canonical JSON), so server-added defaults never produce false
drift.

### Desired state, not a minimum floor

The baseline describes the state a repository should be in, in both
directions: a setting that is *stricter* than the baseline is still drift,
and applying the baseline would lower it. Three things bound that blast
radius:

- **Rulesets are guarded.** Before overwriting an existing ruleset,
  `bootstrap.py` compares it to the baseline; extra rule types, a higher
  `required_approving_review_count`, extra review requirements, or a wider
  ref scope (protecting refs the baseline does not, or excluding fewer)
  are reported as `STRICTER-THAN-BASELINE` and the control is **skipped**
  (in dry-run *and* in `--apply`). Overwriting it is opt-in, via
  `--force-normalize`. If the check itself cannot run, the control renders
  `ERR` and is never normalized. The guard covers rulesets only: the other
  controls are boolean or enum enable flags whose baseline value is already
  the strict one.
- **Nothing is written without `--apply`.** Dry-run issues GET requests
  only; this is enforced by tests that assert no mutating call was made.
- **Ungoverned fields are preserved, never forced.** Where the API demands
  a field in the request body that the baseline deliberately does not
  govern, `apply_preserve` reads the live value and echoes it back
  unchanged. That is how `actions-workflow-permissions` governs only
  `default_workflow_permissions: read` (strictly security-positive) while
  leaving `can_approve_pull_request_reviews` exactly as it was: forcing it
  true would loosen GitHub's stricter default on every repo. Repositories
  running release-please need it `true` - set that per repo; the baseline
  never loosens it.
- **Dry-run is the default**, and prints the full desired-vs-live diff
  before anything is written.

Read failures are never silently treated as drift or as "disabled": a
failed read renders `ERR`, counts toward a non-zero exit, and never
triggers a corrective write.

## Drift detection for a single repository

Running `uv run python scripts/audit.py OWNER/REPO` verifies that one
repository's live platform settings still match the baseline. Run it after any
settings change, or on a schedule.

A repository whose check aborts (bad name, auth failure, transient API
error) is rendered as a row of `ERR` cells with its output printed under the
matrix - never dropped from the report. A fleet audit therefore cannot exit
0 with a repository unaudited or half-audited.

## Scheduled audit (documented, not enabled)

A weekly GitHub Actions job could run the audit across the fleet and fail on drift.
It is NOT enabled because the workflow `GITHUB_TOKEN` is scoped to its own
repository and cannot read sibling repos. Enabling it requires an owner
action: create a fine-grained PAT (read-only: Administration, Code scanning,
Secret scanning, Dependabot alerts on the governed repos), store it as a
repository secret (for example `GOVERNANCE_AUDIT_TOKEN`), and add a small
scheduled workflow that checks out this repo and runs the audit with
`GH_TOKEN=${{ secrets.GOVERNANCE_AUDIT_TOKEN }}`. Prefer a GitHub App
installation for durable automation.

## Org-migration note

This baseline is Step 1 of the multi-repo enforcement path. On a personal
account it is a continuously *audited* desired state, not platform-enforced:
repository settings can still drift between audits. Under a GitHub Team
organization, the same content becomes actual enforcement objects:
organization rulesets targeting all repos (the two ruleset controls),
a default/enforced security configuration (the security controls), and an
organization Actions policy (the workflow-permissions control). At migration
time, `uv run python scripts/audit.py --all` is the acceptance test that the
org objects reproduce this baseline.

## Permanent test bed

`governance-canary` (public scratch repo under the owner) exists to exercise
bootstrap/audit changes end to end without touching real repos. Keep it, or
delete it and recreate it with `gh repo create governance-canary --public
--add-readme` (plus one committed Python file so CodeQL default setup has a
supported language) next time a live proof is needed.
